"""Regret / Optimal Lineup — points left on the bench, per team and per giornata.

regret = optimal_player_fv (best 11 you could have picked from your 25, any
         valid module) minus actual_player_fv (the 11 you actually used).

Bonuses (Modificatore difesa, Fattore campo) are excluded from both sides — they
cancel approximately and would distract from the like-for-like comparison.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from data import load_regret, load_team_season, require_data

st.set_page_config(page_title="Regret", layout="wide")
st.title("Regret / Optimal Lineup")

league, comp = require_data()
rg = load_regret(league, comp)
ts = load_team_season(league, comp)

# ---- per-team KPIs ----
teams = sorted(rg.team.unique())
sel_team = st.sidebar.selectbox("Focus team", teams)
team_rg = rg[rg.team == sel_team].sort_values("giornata")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total regret (season)", f"{team_rg.regret.sum():.1f}")
c2.metric("Avg regret / giornata", f"{team_rg.regret.mean():.2f}")
c3.metric("Worst giornata", f"g{int(team_rg.loc[team_rg.regret.idxmax(), 'giornata'])} "
                            f"({team_rg.regret.max():.1f})")
c4.metric("Perfect giornate", f"{int((team_rg.regret == 0).sum())} / {len(team_rg)}")

st.caption(
    "**How to read this:** *Total regret* is the fv you could have added by "
    "picking the best 11 from your own 25 each week. A *perfect giornata* "
    "means you already used the optimal lineup."
)

# ---- giornata-by-giornata table ----
st.subheader(f"{sel_team} — giornata-by-giornata")
view = team_rg[[
    "giornata", "actual_module", "actual_player_fv",
    "optimal_module", "optimal_player_fv", "regret", "module_matched",
]].rename(columns={
    "actual_module": "act_mod",
    "actual_player_fv": "act_fv",
    "optimal_module": "opt_mod",
    "optimal_player_fv": "opt_fv",
})
st.dataframe(
    view,
    width="stretch",
    hide_index=True,
    column_config={
        "act_fv": st.column_config.NumberColumn(format="%.1f"),
        "opt_fv": st.column_config.NumberColumn(format="%.1f"),
        "regret": st.column_config.NumberColumn(format="%.1f"),
        "module_matched": st.column_config.CheckboxColumn("module ok?"),
    },
)

# ---- trend chart: actual vs optimal over giornate ----
st.subheader("Actual vs optimal player FV over time")
trend = team_rg.set_index("giornata")[["actual_player_fv", "optimal_player_fv"]].rename(
    columns={"actual_player_fv": "actual", "optimal_player_fv": "optimal"})
st.line_chart(trend, height=380)

st.subheader("Regret per giornata")
st.bar_chart(team_rg.set_index("giornata")["regret"], height=300)

st.divider()

# ---- cross-team comparison ----
st.subheader("League-wide: who left the most on the bench?")
comparison = ts[["team", "points", "totale_sum", "regret_total", "regret_avg",
                 "regret_max", "regret_max_g", "perfect_giornate"]].sort_values(
    "regret_total", ascending=False
)
st.dataframe(
    comparison,
    width="stretch",
    hide_index=True,
    column_config={
        "regret_total": st.column_config.NumberColumn("Total regret", format="%.1f"),
        "regret_avg": st.column_config.NumberColumn("Avg / game", format="%.2f"),
        "regret_max": st.column_config.NumberColumn("Worst game", format="%.1f"),
        "perfect_giornate": st.column_config.NumberColumn("Perfect days", format="%d"),
    },
)
st.bar_chart(
    comparison.set_index("team")["regret_total"],
    height=350,
)
st.caption(
    "High regret + high points = a stacked squad you slightly under-used. "
    "Low regret + low points = used your squad efficiently but had less to work with."
)
