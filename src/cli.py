"""Shared CLI bootstrap: argparse + login + league/competition resolution."""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from fanta_client import Competition, FantaClient, League


# Default on-disk locations for each medallion layer. The data/ folder keeps the
# project root tidy; reports/ is presentation output (xlsx), not a data layer.
BRONZE_DEFAULT = "data/bronze"
SILVER_DEFAULT = "data/silver"
GOLD_DEFAULT = "data/gold"
REPORTS_DEFAULT = "reports"


def safe_slug(s: str) -> str:
    """Make a string safe for use as a folder name."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s.strip())


def _normalise(s: str) -> str:
    """Loose comparison: case-insensitive, treat -/_ as spaces, collapse spaces."""
    return re.sub(r"\s+", " ", re.sub(r"[-_]", " ", s.strip().lower()))


def resolve_layer_dir(
    root: Path,
    league: str,
    competition: str,
) -> tuple[Path, str, str]:
    """Find {root}/{league_alias}/{comp_slug}/ by fuzzy name match — no login needed.

    Returns (folder_path, league_alias, comp_slug) using the on-disk folder names.
    """
    if not root.is_dir():
        raise FileNotFoundError(f"{root} not found — run download_all first")

    league_target = _normalise(league)
    league_dir = next(
        (s for s in root.iterdir() if s.is_dir() and _normalise(s.name) == league_target),
        None,
    )
    if league_dir is None:
        avail = sorted(s.name for s in root.iterdir() if s.is_dir())
        raise LookupError(f"league {league!r} not found in {root}/. Available: {avail}")

    comp_target = _normalise(competition)
    comp_dir = next(
        (s for s in league_dir.iterdir() if s.is_dir() and _normalise(s.name) == comp_target),
        None,
    )
    if comp_dir is None:
        avail = sorted(s.name for s in league_dir.iterdir() if s.is_dir())
        raise LookupError(
            f"competition {competition!r} not found in {league_dir}/. Available: {avail}"
        )

    return comp_dir, league_dir.name, comp_dir.name


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-l", "--league", required=True,
        help='League name, case-insensitive (e.g. "My League")',
    )
    parser.add_argument(
        "-c", "--competition", required=True,
        help='Competition name, case-insensitive (e.g. "Serie C")',
    )
    parser.add_argument(
        "-t", "--team", default=None,
        help='Team name, case-insensitive (e.g. "My Team"). '
             "Not used for downloads — kept for downstream analysis.",
    )
    parser.add_argument(
        "--bronze", default=BRONZE_DEFAULT,
        help=f"Bronze (raw xlsx) root directory (default: {BRONZE_DEFAULT})",
    )


def login_and_select(args) -> tuple[FantaClient, League, Competition, Path]:
    """Read .env, log in, select league + competition, return ready-to-use objects."""
    load_dotenv()
    username = os.environ["FANTA_USERNAME"]
    password = os.environ["FANTA_PASSWORD"]

    print(f"[login] as {username} ...")
    client = FantaClient()
    client.login(username, password)
    print(f"        user id: {client.user_info.get('utente', {}).get('id')}")

    league = client.set_league(args.league)
    print(f"[league]     {league.name!r} -> alias={league.alias!r}, id={league.id}")

    comp = client.find_competition(args.competition)
    print(f"[competition] {comp.name!r} -> id_competizione={comp.id}")

    if args.team:
        print(f"[team]       {args.team!r} (validation deferred to analysis stage)")

    out_dir = Path(args.bronze) / league.alias / safe_slug(comp.name)
    return client, league, comp, out_dir
