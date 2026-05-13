"""Per-team breakdown of contribution by position (P/D/C/A)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from data import load_position_rollup, require_data

st.set_page_config(page_title="Position Rollup", layout="wide")
st.title("Position Rollup")

league, comp = require_data()
pr = load_position_rollup(league, comp)

POS_ORDER = ["P", "D", "C", "A"]

# ---- focus team ----
teams = sorted(pr.team.unique())
sel_team = st.sidebar.selectbox("Focus team", teams)

st.subheader(f"{sel_team} — by position")
team_view = pr[pr.team == sel_team].copy()
team_view["_o"] = team_view.position.map({p: i for i, p in enumerate(POS_ORDER)})
team_view = team_view.sort_values("_o").drop(columns="_o")
st.dataframe(
    team_view,
    width="stretch",
    hide_index=True,
    column_config={
        "pct_fv_captured": st.column_config.ProgressColumn(
            "% FV captured", min_value=0.0, max_value=1.0, format="percent",
        ),
        "total_active_fv": st.column_config.NumberColumn(format="%.1f"),
        "avg_active_fv": st.column_config.NumberColumn(format="%.2f"),
        "total_fv_missed": st.column_config.NumberColumn(format="%.1f"),
    },
)

# ---- cross-team stacked bar of total_active_fv by position ----
st.subheader("Where each team's points came from")
pivot = pr.pivot(index="team", columns="position", values="total_active_fv").fillna(0)
pivot = pivot.reindex(columns=[c for c in POS_ORDER if c in pivot.columns])
# Order rows by total descending so the chart reads naturally
pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).index]
st.bar_chart(pivot, height=450, stack=True)
st.caption("Stacked bars = total active FV per team, segmented by position.")
