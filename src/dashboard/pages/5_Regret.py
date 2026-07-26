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
import plotly.express as px
import streamlit as st

import i18n
from data import load_regret, load_team_season, persist_sidebar_selectbox, require_data
from i18n import t
from theme import SUBJECT_COLOR, WHATIF_COLOR

st.set_page_config(page_title="Regret", layout="wide")

league, comp = require_data()
st.title(t("regret.title"))
rg = load_regret(league, comp)
ts = load_team_season(league, comp)

# ---- shared focus team selector ----
teams = sorted(rg.team.unique())
sel_team = persist_sidebar_selectbox(
    t("sidebar.focus_team"), teams, widget_key="selected_team", canon_key="_canon_team",
)
team_rg = rg[rg.team == sel_team].sort_values("giornata")

c1, c2, c3, c4 = st.columns(4)
c1.metric(t("regret.total_season"), f"{team_rg.regret.sum():.1f}")
c2.metric(t("regret.avg_giornata"), f"{team_rg.regret.mean():.2f}")
c3.metric(t("regret.worst_giornata"), f"g{int(team_rg.loc[team_rg.regret.idxmax(), 'giornata'])} "
                            f"({team_rg.regret.max():.1f})")
c4.metric(t("regret.perfect_giornate"), f"{int((team_rg.regret == 0).sum())} / {len(team_rg)}")

st.caption(t("regret.intro_caption"))

# ---- giornata-by-giornata table ----
st.subheader(t("regret.table_header", team=sel_team))
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
    column_config=i18n.columns_config(
        view,
        formats={"act_fv": "%.1f", "opt_fv": "%.1f", "regret": "%.1f"},
        checkbox={"module_matched"},
    ),
)

# ---- trend chart: actual (dark blue) vs optimal (light blue) — same hue: what-if comparison ----
st.subheader(t("regret.trend_header"))
trend = team_rg[["giornata", "actual_player_fv", "optimal_player_fv"]].melt(
    id_vars="giornata", var_name="kind", value_name="value",
)
_actual = t("regret.trend_actual")
_optimal = t("regret.trend_optimal")
trend["kind"] = trend["kind"].map(
    {"actual_player_fv": _actual, "optimal_player_fv": _optimal}
)
fig_trend = px.line(
    trend, x="giornata", y="value", color="kind", markers=True,
    color_discrete_map={_actual: SUBJECT_COLOR, _optimal: WHATIF_COLOR},
    labels={"value": t("regret.trend_axis"), "giornata": i18n.col("giornata"), "kind": ""},
)
fig_trend.update_layout(
    height=380, hovermode="x unified",
    margin=dict(l=10, r=10, t=10, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig_trend, width="stretch")
st.caption(t("regret.trend_caption"))

st.subheader(t("regret.per_giornata_header"))
st.bar_chart(team_rg.set_index("giornata")["regret"], height=300, color=SUBJECT_COLOR)

st.divider()

# ---- cross-team comparison ----
st.subheader(t("regret.comparison_header"))
comparison = ts[["team", "points", "totale_sum", "regret_total", "regret_avg",
                 "regret_max", "regret_max_g", "perfect_giornate"]].sort_values(
    "regret_total", ascending=False
)
st.dataframe(
    comparison,
    width="stretch",
    hide_index=True,
    column_config=i18n.columns_config(
        comparison,
        formats={"totale_sum": "%.1f", "regret_total": "%.1f",
                 "regret_avg": "%.2f", "regret_max": "%.1f", "perfect_giornate": "%d"},
    ),
)
st.bar_chart(
    comparison.set_index("team")["regret_total"],
    height=350,
    color=SUBJECT_COLOR,
)
st.caption(t("regret.comparison_caption"))
