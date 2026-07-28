"""Market / Auction — purchase price, market value, and ROI.

Joins auction purchase price (Costo), season-end market quotations
(Qt.A / Qt.I / FVM), and actual fantasy contribution to answer: who drafted
the most efficient squad, which players were bargains vs flops, and whose
players gained or lost the most market value over the season.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import plotly.express as px
import streamlit as st

import i18n
from data import has_market, load_player_market, load_team_market, require_data
from i18n import t
from modals import maybe_open_player_modal, maybe_open_team_modal
from theme import POSITION_COLOR, POSITION_ORDER

league, comp = require_data()
st.title(t("market.title"))

if not has_market(league, comp):
    st.info(t("market.no_data"))
    st.stop()

pm = load_player_market(league, comp)
tm = load_team_market(league, comp)
budget = int(tm.budget.iloc[0]) if not tm.empty else 500

st.caption(t("market.intro", budget=budget))

# ============================================================
# 1. Squad economics — did spending buy success?
# ============================================================
st.subheader(t("market.econ_header"))

fig_e = px.scatter(
    tm, x="total_spent", y="total_active_fv",
    size="points", size_max=30, color="roi_active",
    color_continuous_scale="RdYlGn",
    text="team",
    custom_data=["team", "rank", "points", "roi_active", "squad_value_delta"],
    labels={"total_spent": t("market.econ_x"), "total_active_fv": t("market.econ_y")},
)
fig_e.update_traces(
    textposition="top center", textfont=dict(size=9),
    hovertemplate=(
        "<b>%{customdata[0]}</b>  ·  #%{customdata[1]}<br>"
        + t("market.econ_x") + ": %{x:.0f}<br>"
        + t("market.econ_y") + ": %{y:.0f}<br>"
        + i18n.col("roi_active") + ": %{customdata[3]:.2f}<br>"
        + i18n.col("points") + ": %{customdata[2]}<extra></extra>"
    ),
)
fig_e.update_layout(height=460, margin=dict(l=10, r=10, t=10, b=10),
                    coloraxis_colorbar_title=i18n.col("roi_active"))
ev_e = st.plotly_chart(fig_e, width="stretch", on_select="rerun",
                       selection_mode="points", key="mk_econ")
if ev_e.selection and ev_e.selection.points:
    cd = ev_e.selection.points[0].get("customdata") or []
    if cd:
        maybe_open_team_modal(league, comp, cd[0], key="mk_econ")
st.caption(t("market.econ_caption"))

econ = tm[["rank", "team", "total_spent", "credits_residui", "total_active_fv",
           "roi_active", "roi_total", "squad_value_delta", "points"]]
ev_et = st.dataframe(
    econ, width="stretch", hide_index=True,
    on_select="rerun", selection_mode="single-row", key="mk_econ_tbl",
    column_config=i18n.columns_config(
        econ,
        formats={"total_spent": "%d", "credits_residui": "%d", "total_active_fv": "%.1f",
                 "roi_active": "%.2f", "roi_total": "%.2f", "squad_value_delta": "%+d",
                 "points": "%d", "rank": "%d"},
    ),
)
if ev_et.selection.rows:
    maybe_open_team_modal(league, comp, econ.iloc[ev_et.selection.rows[0]].team, key="mk_econ_tbl")

# ============================================================
# 2. Player value — cost vs return
# ============================================================
st.subheader(t("market.quadrant_header"))
owned = pm[pm.costo > 0].copy()
fig_q = px.scatter(
    owned, x="costo", y="total_active_fv",
    color="role", size="apps_active", size_max=22,
    color_discrete_map=POSITION_COLOR, category_orders={"role": POSITION_ORDER},
    custom_data=["team", "player", "role", "roi_active", "roi_total",
                 "fvm_scaled", "auction_edge"],
    labels={"costo": t("market.quadrant_x"), "total_active_fv": t("market.quadrant_y"),
            "role": i18n.col("role")},
)
fig_q.update_traces(
    hovertemplate=(
        "<b>%{customdata[1]}</b>  ·  %{customdata[2]}  ·  %{customdata[0]}<br>"
        + i18n.col("costo") + ": %{x:.0f}  ·  " + i18n.col("total_active_fv") + ": %{y:.1f}<br>"
        + i18n.col("roi_active") + ": %{customdata[3]:.2f}  ·  "
        + i18n.col("roi_total") + ": %{customdata[4]:.2f}<br>"
        + i18n.col("fvm_scaled") + ": %{customdata[5]:.0f}  ·  "
        + i18n.col("auction_edge") + ": %{customdata[6]:+.0f}<extra></extra>"
    ),
)
fig_q.update_layout(height=480, margin=dict(l=10, r=10, t=10, b=10),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02,
                                xanchor="right", x=1))
ev_q = st.plotly_chart(fig_q, width="stretch", on_select="rerun",
                       selection_mode="points", key="mk_quad")
if ev_q.selection and ev_q.selection.points:
    cd = ev_q.selection.points[0].get("customdata") or []
    if len(cd) >= 2:
        maybe_open_player_modal(league, comp, cd[0], cd[1], key="mk_quad")
st.caption(t("market.quadrant_caption"))

# ---- best value & biggest flops (roi_active), meaningful sample only ----
col_bv, col_fl = st.columns(2)
_cols = ["team", "player", "role", "costo", "apps_active", "total_active_fv",
         "roi_active", "roi_total"]
_fmt = {"costo": "%d", "apps_active": "%d", "total_active_fv": "%.1f",
        "roi_active": "%.2f", "roi_total": "%.2f"}
with col_bv:
    st.markdown(t("market.best_value_header"))
    bv = (owned[(owned.costo >= 10) & (owned.apps_active >= 5)]
          .sort_values("roi_active", ascending=False).head(10)[_cols])
    st.dataframe(bv, width="stretch", hide_index=True,
                 column_config=i18n.columns_config(bv, formats=_fmt))
with col_fl:
    st.markdown(t("market.flops_header"))
    fl = (owned[owned.costo >= 25]
          .sort_values("roi_active").head(10)[_cols])
    st.dataframe(fl, width="stretch", hide_index=True,
                 column_config=i18n.columns_config(fl, formats=_fmt))

# ============================================================
# 3. Market movers — season value change (Qt.A − Qt.I)
# ============================================================
st.subheader(t("market.movers_header"))
mv_cols = ["team", "player", "role", "club", "qt_i", "qt_a", "val_diff", "costo"]
mv_fmt = {"qt_i": "%d", "qt_a": "%d", "val_diff": "%+d", "costo": "%d"}
movers = pm.dropna(subset=["val_diff"])
col_ri, col_fa = st.columns(2)
with col_ri:
    st.markdown(t("market.risers"))
    ri = movers.sort_values("val_diff", ascending=False).head(10)[mv_cols]
    st.dataframe(ri, width="stretch", hide_index=True,
                 column_config=i18n.columns_config(ri, formats=mv_fmt))
with col_fa:
    st.markdown(t("market.fallers"))
    fa = movers.sort_values("val_diff").head(10)[mv_cols]
    st.dataframe(fa, width="stretch", hide_index=True,
                 column_config=i18n.columns_config(fa, formats=mv_fmt))
st.caption(t("market.movers_caption"))

# ============================================================
# 4. Auction bargains vs overpays — market value vs price paid
# ============================================================
st.subheader(t("market.bargains_header"))
be_cols = ["team", "player", "role", "costo", "fvm_scaled", "auction_edge",
           "total_active_fv"]
be_fmt = {"costo": "%d", "fvm_scaled": "%.0f", "auction_edge": "%+.0f",
          "total_active_fv": "%.1f"}
edge = pm.dropna(subset=["auction_edge"])
col_ba, col_ov = st.columns(2)
with col_ba:
    st.markdown(t("market.bargains_sub"))
    ba = edge.sort_values("auction_edge", ascending=False).head(10)[be_cols]
    st.dataframe(ba, width="stretch", hide_index=True,
                 column_config=i18n.columns_config(ba, formats=be_fmt))
with col_ov:
    st.markdown(t("market.overpays_sub"))
    ov = edge.sort_values("auction_edge").head(10)[be_cols]
    st.dataframe(ov, width="stretch", hide_index=True,
                 column_config=i18n.columns_config(ov, formats=be_fmt))
st.caption(t("market.bargains_caption"))
