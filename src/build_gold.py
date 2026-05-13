"""
Silver (tidy CSVs) -> Gold (aggregated, business-ready CSVs).

Reads:
    silver/{league}/{comp}/appearances.csv
    silver/{league}/{comp}/matches.csv

Writes:
    gold/{league}/{comp}/player_season.csv      one row per (team, player)
    gold/{league}/{comp}/team_season.csv        one row per team (the league table)
    gold/{league}/{comp}/position_rollup.csv    one row per (team, position)

Usage:
    python build_gold.py -l My League -c "Serie C"
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from cli import GOLD_DEFAULT, SILVER_DEFAULT, resolve_layer_dir


# Valid fantacalcio modules expressed as (P, D, C, A) counts in the starting 11.
VALID_MODULES = [
    (1, 3, 4, 3),  # 343
    (1, 3, 5, 2),  # 352
    (1, 4, 3, 3),  # 433
    (1, 4, 4, 2),  # 442
    (1, 4, 5, 1),  # 451
    (1, 5, 3, 2),  # 532
    (1, 5, 4, 1),  # 541
]


# ----------------- per-player season -----------------

def build_player_season(ap: pd.DataFrame) -> pd.DataFrame:
    """One row per (team, player). Captures performance vs. contribution."""
    rows = []
    for (team, player), g in ap.groupby(["team", "player"], sort=False):
        active = g[g.active]
        missed = g[(~g.active) & g.fantavoto.notna()]

        n_squad = len(g)
        n_active = len(active)
        n_missed = len(missed)
        tot_active_fv = float(active.fantavoto.sum())
        tot_missed_fv = float(missed.fantavoto.sum())
        captureable = tot_active_fv + tot_missed_fv

        rows.append({
            "team": team,
            "player": player,
            "position": g.sort_values("giornata").position.iloc[0],
            "apps_in_squad": n_squad,
            "apps_with_voto": int(g.voto.notna().sum()),
            "apps_active": n_active,
            "apps_missed": n_missed,
            "pct_active_rate": round(n_active / n_squad, 4) if n_squad else None,
            "pct_fv_captured": round(tot_active_fv / captureable, 4) if captureable > 0 else None,
            "total_voto": round(float(g.voto.sum()), 2),
            "total_fv": round(float(g.fantavoto.sum()), 2),
            "total_active_fv": round(tot_active_fv, 2),
            "total_fv_missed": round(tot_missed_fv, 2),
            "avg_active_fv": round(tot_active_fv / n_active, 2) if n_active else None,
            "avg_fv_missed": round(tot_missed_fv / n_missed, 2) if n_missed else None,
            "best_active_fv": float(active.fantavoto.max()) if n_active else None,
            "worst_active_fv": float(active.fantavoto.min()) if n_active else None,
        })
    return (pd.DataFrame(rows)
              .sort_values(["team", "total_active_fv"], ascending=[True, False]))


# ----------------- regret / optimal lineup -----------------

def _best_lineup_fv(by_pos: dict[str, list[float]]) -> tuple[float, str]:
    """Try every valid module. Return (best_total_fv, module_str e.g. '343').

    `by_pos` maps P/D/C/A -> sorted-desc list of available fantavoto values.
    If no module's minimum counts can be met, falls back to a 'partial' best —
    up to 11 players, max 1 P and max 5 of every other position.
    """
    best_fv: float = float("-inf")
    best_mod: str = ""
    for p, d, c, a in VALID_MODULES:
        if (len(by_pos.get("P", [])) < p or len(by_pos.get("D", [])) < d
                or len(by_pos.get("C", [])) < c or len(by_pos.get("A", [])) < a):
            continue
        total = (sum(by_pos["P"][:p]) + sum(by_pos["D"][:d])
                 + sum(by_pos["C"][:c]) + sum(by_pos["A"][:a]))
        if total > best_fv:
            best_fv = total
            best_mod = f"{d}{c}{a}"
    if not best_mod:
        # Insufficient players for any module — take best ≤11 respecting position caps.
        bag: list[float] = []
        for pos, lst in by_pos.items():
            cap = 1 if pos == "P" else 5
            bag.extend(lst[:cap])
        bag.sort(reverse=True)
        best_fv = float(sum(bag[:11]))
        best_mod = "partial"
    return best_fv, best_mod


def build_regret(ap: pd.DataFrame, mt: pd.DataFrame) -> pd.DataFrame:
    """Per (team, giornata): actual player fv vs theoretical optimum from the same squad.

    'actual_player_fv' is the sum of fantavoto across active players — i.e., TOTALE
    *without* the Modificatore difesa / Fattore campo bonuses. The same bonuses
    would apply to the optimal lineup approximately equally, so they cancel out
    when comparing — we keep the comparison in player-only terms.
    """
    module_lookup = mt.set_index(["team", "giornata"])["module"].to_dict()

    rows = []
    for (team, g), sub in ap.groupby(["team", "giornata"], sort=False):
        with_voto = sub[sub.fantavoto.notna()]
        by_pos: dict[str, list[float]] = {
            pos: sorted(grp.fantavoto.tolist(), reverse=True)
            for pos, grp in with_voto.groupby("position")
        }
        optimal_fv, optimal_mod = _best_lineup_fv(by_pos)
        actual_fv = float(sub[sub.active].fantavoto.fillna(0).sum())
        actual_mod = module_lookup.get((team, int(g)))

        rows.append({
            "team": team,
            "giornata": int(g),
            "actual_module": str(int(actual_mod)) if actual_mod is not None else None,
            "actual_player_fv": round(actual_fv, 2),
            "optimal_module": optimal_mod,
            "optimal_player_fv": round(optimal_fv, 2),
            "regret": round(optimal_fv - actual_fv, 2),
            "module_matched": (
                optimal_mod != "partial"
                and actual_mod is not None
                and str(int(actual_mod)) == optimal_mod
            ),
        })
    return pd.DataFrame(rows).sort_values(["team", "giornata"])


# ----------------- team season -----------------

def build_team_season(mt: pd.DataFrame, regret_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per team — wins/draws/losses, points, totale stats, opponent comparison."""
    # Attach opponent's totale to each row by self-joining on (giornata, opponent==team)
    opp = mt[["giornata", "team", "totale"]].rename(
        columns={"team": "opponent", "totale": "opp_totale"})
    mt = mt.merge(opp, on=["giornata", "opponent"], how="left")

    rows = []
    for team, g in mt.groupby("team", sort=False):
        wins = int((g.result == "W").sum())
        draws = int((g.result == "D").sum())
        losses = int((g.result == "L").sum())
        max_row = g.loc[g.totale.idxmax()]
        min_row = g.loc[g.totale.idxmin()]
        rows.append({
            "team": team,
            "matches_played": len(g),
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "points": 3 * wins + draws,
            "goals_for": int(g.score_for.sum()),
            "goals_against": int(g.score_against.sum()),
            "goal_diff": int(g.score_for.sum() - g.score_against.sum()),
            "totale_sum": round(float(g.totale.sum()), 2),
            "totale_avg": round(float(g.totale.mean()), 2),
            "totale_max": round(float(g.totale.max()), 2),
            "totale_max_g": int(max_row.giornata),
            "totale_max_vs": str(max_row.opponent),
            "totale_min": round(float(g.totale.min()), 2),
            "totale_min_g": int(min_row.giornata),
            "totale_min_vs": str(min_row.opponent),
            "opp_totale_avg": round(float(g.opp_totale.mean()), 2),
            "totale_diff_avg": round(float((g.totale - g.opp_totale).mean()), 2),
            "fattore_campo_count": int(g.fattore_campo.notna().sum()),
            "modificatore_difesa_sum": round(float(g.modificatore_difesa.fillna(0).sum()), 2),
        })

    df = pd.DataFrame(rows)
    if regret_df is not None and not regret_df.empty:
        per_team = regret_df.groupby("team")
        agg_rows = []
        for team, rg in per_team:
            max_idx = rg.regret.idxmax()
            agg_rows.append({
                "team": team,
                "regret_total": round(float(rg.regret.sum()), 2),
                "regret_avg": round(float(rg.regret.mean()), 2),
                "regret_max": round(float(rg.regret.max()), 2),
                "regret_max_g": int(rg.loc[max_idx, "giornata"]),
                "perfect_giornate": int((rg.regret == 0).sum()),
            })
        df = df.merge(pd.DataFrame(agg_rows), on="team", how="left")

    return df.sort_values(["points", "goal_diff", "totale_sum"], ascending=False).reset_index(drop=True)


# ----------------- position rollup -----------------

def build_position_rollup(ap: pd.DataFrame) -> pd.DataFrame:
    """One row per (team, position) — where each team's points came from."""
    rows = []
    for (team, pos), g in ap.groupby(["team", "position"], sort=False):
        active = g[g.active]
        missed = g[(~g.active) & g.fantavoto.notna()]
        tot_active = float(active.fantavoto.sum())
        tot_missed = float(missed.fantavoto.sum())
        captureable = tot_active + tot_missed
        rows.append({
            "team": team,
            "position": pos,
            "players_used": g.player.nunique(),
            "apps_active": len(active),
            "apps_missed": len(missed),
            "total_active_fv": round(tot_active, 2),
            "avg_active_fv": round(tot_active / len(active), 2) if len(active) else None,
            "total_fv_missed": round(tot_missed, 2),
            "pct_fv_captured": round(tot_active / captureable, 4) if captureable > 0 else None,
        })
    pos_order = {"P": 0, "D": 1, "C": 2, "A": 3}
    df = pd.DataFrame(rows)
    df["_pos_order"] = df.position.map(pos_order)
    return df.sort_values(["team", "_pos_order"]).drop(columns="_pos_order")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-l", "--league", required=True)
    parser.add_argument("-c", "--competition", required=True)
    parser.add_argument("--silver", default=SILVER_DEFAULT)
    parser.add_argument("--gold", default=GOLD_DEFAULT)
    args = parser.parse_args()

    silver_dir, league_alias, comp_slug = resolve_layer_dir(
        Path(args.silver), args.league, args.competition,
    )
    print(f"[silver] {silver_dir}/")

    appearances = pd.read_csv(silver_dir / "appearances.csv")
    matches = pd.read_csv(silver_dir / "matches.csv")
    print(f"         appearances={len(appearances)} matches={len(matches)}")

    gold_dir = Path(args.gold) / league_alias / comp_slug
    gold_dir.mkdir(parents=True, exist_ok=True)

    player_season = build_player_season(appearances)
    regret = build_regret(appearances, matches)
    team_season = build_team_season(matches, regret)
    position_rollup = build_position_rollup(appearances)

    p1 = gold_dir / "player_season.csv"
    p2 = gold_dir / "team_season.csv"
    p3 = gold_dir / "position_rollup.csv"
    p4 = gold_dir / "regret.csv"
    player_season.to_csv(p1, index=False)
    team_season.to_csv(p2, index=False)
    position_rollup.to_csv(p3, index=False)
    regret.to_csv(p4, index=False)

    print(f"[gold]   {p1}  ({len(player_season)} rows)")
    print(f"         {p2}  ({len(team_season)} rows)")
    print(f"         {p3}  ({len(position_rollup)} rows)")
    print(f"         {p4}  ({len(regret)} rows)")


if __name__ == "__main__":
    main()
