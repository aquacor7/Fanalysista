"""
Auction / market layer: join purchase prices (Rose) + market quotations
(Quotazioni) + season performance (gold/player_season) into market tables.

Silver:
  data/silver/quotazioni.csv                one row per footballer (season-global)
  data/silver/{league}/rosters.csv          one row per (participant, player)

Gold (per league + competition):
  data/gold/{league}/{comp}/player_market.csv   one row per owned player
  data/gold/{league}/{comp}/team_market.csv     one row per participant

Participants are mapped to a competition by matching their name (case-insensitive)
against that competition's team_season. A participant belongs to exactly one
competition, so the mapping is unambiguous.

FVM (FantaValore di Mercato) is quoted on a 1000-credit budget. Leagues may use
a different budget, so we also emit `fvm_scaled` = FVM × (league budget / 1000)
to make "what the market says they're worth" comparable to what was actually
paid. The league budget is inferred per participant as spent + credits_residui.

Usage:
    python build_market.py                 # every league found under data/gold
    python build_market.py -l husky        # one league
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from cli import GOLD_DEFAULT, SILVER_DEFAULT
from parse_market import parse_quotazioni, parse_rosters

BRONZE = Path("data/bronze")
_ROLE_ORDER = ["P", "D", "C", "A"]


def _discover_leagues(gold_root: Path) -> list[str]:
    return sorted(d.name for d in gold_root.iterdir()
                  if d.is_dir() and any(d.iterdir()))


def _load_gold(gold_root: Path, league: str, comp: str, name: str) -> pd.DataFrame:
    return pd.read_csv(gold_root / league / comp / f"{name}.csv")


def build_league(
    league: str, quot: pd.DataFrame, silver_root: Path, gold_root: Path,
) -> None:
    rose_path = BRONZE / f"Rose_{league}.xlsx"
    if not rose_path.exists():
        print(f"[skip]   {league}: no {rose_path.name}")
        return

    rosters = parse_rosters(rose_path)
    rosters = rosters[rosters.participant.notna() & rosters.player.astype(bool)].copy()

    silver_dir = silver_root / league
    silver_dir.mkdir(parents=True, exist_ok=True)
    rosters.to_csv(silver_dir / "rosters.csv", index=False)
    print(f"[silver] {silver_dir / 'rosters.csv'}  ({len(rosters)} rows)")

    comps = sorted(c.name for c in (gold_root / league).iterdir() if c.is_dir())

    # participant (upper) -> (comp, canonical team name)
    part_map: dict[str, tuple[str, str]] = {}
    for comp in comps:
        ts = _load_gold(gold_root, league, comp, "team_season")
        for team in ts.team:
            part_map[team.upper()] = (comp, team)

    rosters["_key"] = rosters.participant.str.upper()
    rosters["comp"] = rosters["_key"].map(lambda k: part_map[k][0] if k in part_map else None)
    rosters["team"] = rosters["_key"].map(lambda k: part_map[k][1] if k in part_map else None)
    active = rosters[rosters.comp.notna()].copy()

    unmapped = sorted(set(rosters.participant[rosters.comp.isna()]))
    if unmapped:
        print(f"         note: {len(unmapped)} participants not in any competition "
              f"(registered but not fielded) — skipped")

    # Infer league budget: the common (spent + residui) per participant.
    spend = active.groupby("team")["costo"].sum()
    resid = active.groupby("team")["credits_residui"].first()
    # spent + residui approximates the starting budget, but mid-season trading
    # (players bought/sold) leaves it a bit off a round number — so snap the
    # median to the nearest 100 (e.g. 465/511/483 → 500).
    budget_series = (spend + resid).dropna()
    raw_budget = float(budget_series.median()) if not budget_series.empty else 1000.0
    budget = int(round(raw_budget / 100.0) * 100) or 1000
    print(f"         inferred budget: {budget} credits (raw median {raw_budget:.0f})")

    q = quot.drop_duplicates(subset=["player"])[
        ["player", "club", "qt_a", "qt_i", "val_diff", "fvm"]
    ].rename(columns={"club": "club_full"})

    for comp in comps:
        comp_r = active[active.comp == comp].copy()
        if comp_r.empty:
            continue
        ps = _load_gold(gold_root, league, comp, "player_season")
        ts = _load_gold(gold_root, league, comp, "team_season")

        pm = comp_r.merge(
            ps[["team", "player", "position", "apps_active",
                "total_active_fv", "total_fv", "avg_active_fv", "pct_fv_captured"]],
            on=["team", "player"], how="left",
        ).merge(q, on="player", how="left")

        pm["fvm_scaled"] = pm["fvm"] * (budget / 1000.0)
        cost = pm["costo"].where(pm["costo"] > 0)
        pm["roi_active"] = pm["total_active_fv"] / cost
        pm["roi_total"] = pm["total_fv"] / cost
        pm["auction_edge"] = pm["fvm_scaled"] - pm["costo"]

        pm = pm[[
            "team", "player", "role", "club_full", "costo",
            "qt_a", "qt_i", "val_diff", "fvm", "fvm_scaled", "auction_edge",
            "apps_active", "total_active_fv", "total_fv", "avg_active_fv",
            "pct_fv_captured", "roi_active", "roi_total",
        ]].rename(columns={"club_full": "club"})

        out_dir = gold_root / league / comp
        pm.to_csv(out_dir / "player_market.csv", index=False)

        # ---- team_market: one row per participant ----
        g = pm.groupby("team")
        tm = pd.DataFrame({
            "n_players": g.size(),
            "total_spent": g["costo"].sum(),
            "total_active_fv": g["total_active_fv"].sum(min_count=1),
            "total_fv": g["total_fv"].sum(min_count=1),
            "squad_value_delta": g["val_diff"].sum(min_count=1),
            "squad_fvm_scaled": g["fvm_scaled"].sum(min_count=1),
        }).reset_index()
        tm["credits_residui"] = tm.team.map(resid)
        tm["budget"] = budget
        tm["roi_active"] = tm.total_active_fv / tm.total_spent.where(tm.total_spent > 0)
        tm["roi_total"] = tm.total_fv / tm.total_spent.where(tm.total_spent > 0)
        # spend by role
        for role in _ROLE_ORDER:
            tm[f"spend_{role}"] = tm.team.map(
                pm[pm.role == role].groupby("team")["costo"].sum())
        # standings context
        ts_rank = ts.sort_values("points", ascending=False).reset_index(drop=True)
        rank_map = {t: i + 1 for i, t in enumerate(ts_rank.team)}
        tm["points"] = tm.team.map(ts.set_index("team")["points"])
        tm["rank"] = tm.team.map(rank_map)
        tm = tm.sort_values("rank")
        tm.to_csv(out_dir / "team_market.csv", index=False)

        print(f"[gold]   {league}/{comp}: player_market ({len(pm)}), "
              f"team_market ({len(tm)})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-l", "--league", default=None,
                        help="League alias (folder name). Omit to build all.")
    parser.add_argument("--silver", default=SILVER_DEFAULT)
    parser.add_argument("--gold", default=GOLD_DEFAULT)
    args = parser.parse_args()

    silver_root, gold_root = Path(args.silver), Path(args.gold)

    quot_files = sorted(BRONZE.glob("Quotazioni_*.xlsx"))
    if not quot_files:
        raise FileNotFoundError(f"no Quotazioni_*.xlsx in {BRONZE}/")
    quot = parse_quotazioni(quot_files[-1])
    silver_root.mkdir(parents=True, exist_ok=True)
    quot.to_csv(silver_root / "quotazioni.csv", index=False)
    print(f"[silver] {silver_root / 'quotazioni.csv'}  ({len(quot)} players)")

    leagues = [args.league] if args.league else _discover_leagues(gold_root)
    for league in leagues:
        build_league(league, quot, silver_root, gold_root)


if __name__ == "__main__":
    main()
