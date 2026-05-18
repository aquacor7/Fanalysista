"""
Minimal client for leghe.fantacalcio.it.

Reverse-engineered from the site's own JS:
  - login:                PUT  /api/v1/v1_utente/login?alias_lega={alias}
  - list rounds:          GET  /servizi/V1_LegheCalcolo/Giornate
  - formations excel:     GET  /servizi/V1_LegheFormazioni/excel
"""
from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://leghe.fantacalcio.it"
APP_KEY = "bZ2FAQDZYYBVEehhFuM9pAsJ3waL0Vsg"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# HTTP timeouts so the script can't hang silently when fantacalcio.it is slow.
# Without these, requests waits indefinitely.
API_TIMEOUT = 30        # seconds — login, page scrape, rounds endpoint
DOWNLOAD_TIMEOUT = 90   # seconds — xlsx blob downloads


@dataclass
class Competition:
    id: str
    name: str


@dataclass
class League:
    id: int
    alias: str
    name: str


class FantaClient:
    def __init__(self, league_alias: Optional[str] = None):
        self.league_alias = league_alias
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "app_key": APP_KEY,
        })
        self.user_info: Optional[dict] = None

    # ---------------- auth ----------------

    def login(self, username: str, password: str) -> dict:
        url = f"{BASE_URL}/api/v1/v1_utente/login"
        resp = self.session.put(
            url,
            params={"alias_lega": self.league_alias or ""},
            headers={"Content-Type": "application/json"},
            data=json.dumps({"username": username, "password": password}),
            timeout=API_TIMEOUT,
        )
        resp.raise_for_status()
        payload = resp.json()

        # The server wraps the real response in base64. Decode it the way the JS does:
        # __.d(payload.data) = JSON.parse(atob(data).replace('\r\n','\\r\\n').replace(NUL,''))
        decoded = base64.b64decode(payload["data"]).decode("utf-8", errors="replace")
        decoded = decoded.replace("\r\n", "\\r\\n").replace(chr(0), "")
        inner = json.loads(decoded)

        if not inner.get("success"):
            raise RuntimeError(f"Login failed: {inner.get('error_msgs') or inner}")

        self.user_info = inner["data"]
        return self.user_info

    # ---------------- league ----------------

    def list_leagues(self) -> list[League]:
        if not self.user_info:
            raise RuntimeError("login() first")
        return [
            League(id=l["id"], alias=l["alias"], name=l["nome"])
            for l in self.user_info.get("leghe", [])
        ]

    def set_league(self, name: str) -> League:
        """Find a league by display name (case-insensitive) and select it."""
        target = name.strip().lower()
        for lg in self.list_leagues():
            if lg.name.strip().lower() == target or lg.alias.strip().lower() == target:
                self.league_alias = lg.alias
                return lg
        available = [lg.name for lg in self.list_leagues()]
        raise LookupError(f"League {name!r} not found. Available: {available}")

    # ---------------- competitions ----------------

    def list_competitions(self) -> list[Competition]:
        """
        Scrape the formazioni page for the competition dropdown.

        Each item looks like:
            <li class='dropdown-item'>
              <a href='#' data-isin='true' data-id='380468'>
                <span class='competition-icon competition-icon-1'></span>Serie C
              </a>
            </li>
        """
        if not self.league_alias:
            raise RuntimeError("set_league() first")

        resp = self.session.get(
            f"{BASE_URL}/{self.league_alias}/formazioni/1",
            timeout=API_TIMEOUT,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        comps: list[Competition] = []
        menu = soup.find("ul", class_=re.compile(r"competition-list"))
        if menu:
            for a in menu.find_all("a", attrs={"data-id": True}):
                comp_id = a.get("data-id")
                name = a.get_text(strip=True)
                if comp_id and name:
                    comps.append(Competition(id=str(comp_id), name=name))
        return comps

    def find_competition(self, name: str) -> Competition:
        comps = self.list_competitions()
        target = name.strip().lower()
        for c in comps:
            if c.name.strip().lower() == target:
                return c
        raise LookupError(
            f"Competition {name!r} not found. Available: {[c.name for c in comps]}"
        )

    def get_competition_rounds(self, competition_id: str) -> list[int]:
        """Return the list of giornata numbers configured for the competition.

        This endpoint is **admin-only**: as a regular league member you'll get
        ``{"data": null, "error_msgs": [{"id": "AD01", ...}]}`` and an empty
        list back. Callers should fall back to probing the download endpoint
        (which non-admins can use) — see ``probe_rounds()`` and the
        ``download_all.py`` probe-mode code path.

        An empty list can therefore mean any of: not the admin, competition
        archived, or calendar truly not scheduled. The error_msgs field
        distinguishes them but the caller's recovery is the same.
        """
        if not self.league_alias:
            raise RuntimeError("set_league() first")
        resp = self.session.get(
            f"{BASE_URL}/servizi/V1_LegheCalcolo/Giornate",
            params={"alias_lega": self.league_alias, "id_competizione": competition_id},
            timeout=API_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json().get("data") or []
        return [g["g"] for g in data]

    # ---------------- download ----------------

    def download_formations(
        self,
        competition_id: str,
        round_: int,
        out_dir: Path = Path("downloads"),
    ) -> Path:
        if not self.league_alias:
            raise RuntimeError("set_league() first")
        params = {
            "alias_lega": self.league_alias,
            "id_competizione": competition_id,
            "giornata": round_,
            "nome_competizione": self.league_alias,
            "dummy": 5,
        }
        resp = self.session.get(
            f"{BASE_URL}/servizi/V1_LegheFormazioni/excel",
            params=params,
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=DOWNLOAD_TIMEOUT,
        )
        resp.raise_for_status()

        # Extract filename from Content-Disposition; fall back to a sensible name.
        disp = resp.headers.get("content-disposition", "")
        m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', disp)
        filename = (
            m.group(1)
            if m
            else f"formazioni_{self.league_alias}_comp{competition_id}_g{round_}.xlsx"
        )

        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / filename
        out_path.write_bytes(resp.content)
        return out_path
