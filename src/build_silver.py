"""
Bronze (raw xlsx) -> Silver (tidy CSVs).

Reads bronze/{league}/{comp}/Formazioni_*_giornata.xlsx and writes:
  silver/{league}/{comp}/appearances.csv   one row per player-giornata
  silver/{league}/{comp}/matches.csv       one row per team-giornata

No login required — works entirely off the bronze folder.

Usage:
    python build_silver.py -l My League -c "Serie C"
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from cli import BRONZE_DEFAULT, SILVER_DEFAULT, resolve_layer_dir
from parse_formations import GIORNATA_RE, Match, parse_all_matches


def collect_matches(bronze_dir: Path) -> list[Match]:
    files = sorted(
        bronze_dir.glob("Formazioni_*_giornata.xlsx"),
        key=lambda p: int(GIORNATA_RE.search(p.name).group(1)),
    )
    out: list[Match] = []
    for p in files:
        out.extend(parse_all_matches(p))
    return out


def matches_to_dataframes(matches: list[Match]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Flatten Match records into (appearances_df, matches_df).

    matches_df has TWO rows per match — one per team — with result/score from
    that team's POV. This keeps queries like 'all of one team's games' a
    simple WHERE team=... .
    """
    appearance_rows = []
    match_rows = []

    for m in matches:
        sf_l, sa_l = m.score_left, m.score_right
        sf_r, sa_r = m.score_right, m.score_left

        def result(sf, sa):
            if sf is None or sa is None:
                return None
            if sf > sa:
                return "W"
            if sf < sa:
                return "L"
            return "D"

        for tf, opp, sf, sa in (
            (m.left,  m.right.team, sf_l, sa_l),
            (m.right, m.left.team,  sf_r, sa_r),
        ):
            match_rows.append({
                "giornata": m.giornata,
                "team": tf.team,
                "opponent": opp,
                "side": tf.side,
                "score_for": sf,
                "score_against": sa,
                "result": result(sf, sa),
                "totale": tf.totale,
                "module": tf.module,
                "modificatore_difesa": tf.modificatore_difesa,
                "fattore_campo": tf.fattore_campo,
            })
            for p in tf.players:
                appearance_rows.append({
                    "giornata": m.giornata,
                    "team": tf.team,
                    "player": p.name,
                    "position": p.position,
                    "voto": p.voto,
                    "fantavoto": p.fantavoto,
                    "active": p.active,
                    "on_bench": p.on_bench,
                })

    appearances = pd.DataFrame(appearance_rows)
    matches_df = pd.DataFrame(match_rows)
    return appearances, matches_df


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-l", "--league", required=True)
    parser.add_argument("-c", "--competition", required=True)
    parser.add_argument("--bronze", default=BRONZE_DEFAULT)
    parser.add_argument("--silver", default=SILVER_DEFAULT)
    args = parser.parse_args()

    bronze_dir, league_alias, comp_slug = resolve_layer_dir(
        Path(args.bronze), args.league, args.competition,
    )
    print(f"[bronze] {bronze_dir}/")

    matches = collect_matches(bronze_dir)
    print(f"[parse]  {len(matches)} matches from {len({m.giornata for m in matches})} giornate")

    appearances_df, matches_df = matches_to_dataframes(matches)
    silver_dir = Path(args.silver) / league_alias / comp_slug
    silver_dir.mkdir(parents=True, exist_ok=True)

    apps_path = silver_dir / "appearances.csv"
    matches_path = silver_dir / "matches.csv"
    appearances_df.to_csv(apps_path, index=False)
    matches_df.to_csv(matches_path, index=False)

    print(f"[silver] {apps_path}  ({len(appearances_df)} rows)")
    print(f"         {matches_path}  ({len(matches_df)} rows)")


if __name__ == "__main__":
    main()
