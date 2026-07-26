"""Reusable @st.dialog modals for clicking-to-peek at teams and players.

Two design points:
    - The modal is a *digest*, not the full page. It shows the headline numbers
      and one small chart. A primary button at the bottom escalates to the
      corresponding full Detail page if the user wants to dig deeper.
    - Each click handler in a page calls `maybe_open_team_modal()` /
      `maybe_open_player_modal()`. Those helpers compare the new selection
      against `st.session_state` so the modal only opens on a transition,
      preventing the dialog from re-opening on every rerun while a row stays
      selected.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

import i18n
from data import (
    load_appearances,
    load_matches,
    load_player_season,
    load_team_season,
)
from i18n import t
from theme import (
    ACTIVE_COLOR,
    MISSED_COLOR,
    OPPONENT_COLOR,
    SUBJECT_COLOR,
)


# --------------- internal: transition guards ---------------
#
# We use TWO levels of guard to prevent modal-open misfires:
#
# 1. Per-widget "last selection" guard (keyed by caller's `key`). This
#    stops the modal from re-opening on every rerun while a chart/table row
#    stays selected, AND lets the SAME team/player be opened from DIFFERENT
#    widgets (the previous global guards blocked this — see issue 1).
#
# 2. Per-run "already opened a dialog" flag. Streamlit forbids two
#    `@st.dialog` calls in the same script run (duplicate element ID). When
#    multiple widgets on the page each have a persisted selection, both
#    handlers fire on a rerun — we let only the first one through (see
#    issue 2). The flag is reset at the top of each script run by
#    `require_data()` in `data.py`.

_DIALOG_OPENED_THIS_RUN = "_modal_opened_this_run"


def _last_sel_key(prefix: str, key: str) -> str:
    return f"_last_{prefix}_modal_sel_{key}"


def reset_per_run_modal_state() -> None:
    """Called by require_data() at the start of every page render."""
    st.session_state[_DIALOG_OPENED_THIS_RUN] = False


def maybe_open_team_modal(league: str, comp: str, team: str, *, key: str) -> None:
    """Open the team modal if `team` is a fresh selection from this widget.

    `key` must be the caller widget's unique identifier (the same string
    passed to ``st.dataframe(..., key=...)`` or ``st.plotly_chart(..., key=...)``).
    """
    if not team:
        return
    if st.session_state.get(_DIALOG_OPENED_THIS_RUN):
        return
    sel_key = _last_sel_key("team", key)
    if st.session_state.get(sel_key) == team:
        return
    st.session_state[sel_key] = team
    st.session_state[_DIALOG_OPENED_THIS_RUN] = True
    _team_modal(league, comp, team)


def maybe_open_player_modal(
    league: str, comp: str, team: str, player: str, *, key: str,
) -> None:
    if not team or not player:
        return
    if st.session_state.get(_DIALOG_OPENED_THIS_RUN):
        return
    sel_key = _last_sel_key("player", key)
    selection = (team, player)
    if st.session_state.get(sel_key) == selection:
        return
    st.session_state[sel_key] = selection
    st.session_state[_DIALOG_OPENED_THIS_RUN] = True
    _player_modal(league, comp, team, player)


# --------------- the modals ---------------

def _team_modal(league: str, comp: str, team: str) -> None:
    # The dialog title is defined at decoration time, so we build the dialog
    # inline each call — that way the title reflects the current language.
    @st.dialog(t("modal.team_title"), width="large")
    def _dialog() -> None:
        ts = load_team_season(league, comp)
        mt = load_matches(league, comp)
        ps = load_player_season(league, comp)

        row = ts[ts.team == team].iloc[0]
        st.markdown(f"### {team}")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(t("common.wdl"), f"{int(row.wins)} / {int(row.draws)} / {int(row.losses)}")
        c2.metric(t("common.points"), int(row.points))
        c3.metric(t("common.avg_totale"), f"{row.totale_avg:.2f}")
        c4.metric(t("common.goal_diff"), f"{int(row.goal_diff):+d}")

        if "regret_total" in ts.columns and pd.notna(row.get("regret_total")):
            st.caption(t("modal.season_regret",
                         regret=f"{row.regret_total:.1f}",
                         perfect=int(row.get('perfect_giornate', 0))))

        # Mini TOTALE-vs-opp trend
        opp = mt[["giornata", "team", "totale"]].rename(
            columns={"team": "opponent", "totale": "opp_totale"})
        s = mt[mt.team == team].merge(opp, on=["giornata", "opponent"], how="left").sort_values("giornata")
        trend = s[["giornata", "totale", "opp_totale"]].melt(
            id_vars="giornata", var_name="who", value_name="value")
        opponent_label = t("team_detail.opponent")
        trend["who"] = trend["who"].map({"totale": team, "opp_totale": opponent_label})
        fig = px.line(
            trend, x="giornata", y="value", color="who", markers=False,
            color_discrete_map={team: SUBJECT_COLOR, opponent_label: OPPONENT_COLOR},
            labels={"value": i18n.col("totale"), "giornata": i18n.col("giornata"), "who": ""},
        )
        fig.update_layout(
            height=220, hovermode="x unified",
            margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, width="stretch", key=f"team_modal_trend_{team}")

        # Top contributors
        st.markdown(t("modal.top5"))
        top = (ps[ps.team == team]
                  .sort_values("total_active_fv", ascending=False)
                  .head(5))
        top_view = top[["position", "player", "apps_active", "total_active_fv",
                        "avg_active_fv", "pct_fv_captured"]]
        st.dataframe(
            top_view,
            width="stretch", hide_index=True,
            column_config=i18n.columns_config(
                top_view,
                formats={"total_active_fv": "%.1f", "avg_active_fv": "%.2f"},
                progress={"pct_fv_captured"},
            ),
        )

        if st.button(t("modal.open_team", team=team),
                     width="stretch", type="primary"):
            # Persist the full context. We write BOTH the widget keys (some of
            # which Streamlit may preserve directly across nav) and the
            # canonical keys (which require_data / persist_sidebar_selectbox
            # use to restore the widget when its state has been GC'd).
            st.session_state["_canon_league"] = league
            st.session_state["_canon_competition"] = comp
            st.session_state["_canon_team"] = team
            st.session_state["selected_league"] = league
            st.session_state["selected_competition"] = comp
            st.session_state["selected_team"] = team
            st.switch_page("views/team_detail.py")

    _dialog()


def _player_modal(league: str, comp: str, team: str, player: str) -> None:
    @st.dialog(t("modal.player_title"), width="large")
    def _dialog() -> None:
        ps = load_player_season(league, comp)
        ap = load_appearances(league, comp)

        rows = ps[(ps.team == team) & (ps.player == player)]
        if rows.empty:
            st.error(t("modal.player_not_found", player=player, team=team))
            return
        row = rows.iloc[0]

        st.markdown(f"### {player}  ·  {row.position}  ·  {team}")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(t("modal.apps_active"), int(row.apps_active))
        c2.metric(t("modal.total_active_fv"), f"{row.total_active_fv:.1f}")
        c3.metric(
            t("modal.avg_active_fv"),
            f"{row.avg_active_fv:.2f}" if pd.notna(row.avg_active_fv) else "—",
        )
        c4.metric(
            t("modal.pct_fv_captured"),
            f"{row.pct_fv_captured*100:.1f}%" if pd.notna(row.pct_fv_captured) else "—",
        )

        # Manager-usage verdict
        if pd.notna(row.avg_active_fv) and pd.notna(row.avg_fv_missed):
            delta = row.avg_active_fv - row.avg_fv_missed
            d = f"{delta:+.2f}"
            if delta > 0.3:
                color = "#2E7D32"
                label = t("modal.verdict_well_title")
                text = t("modal.verdict_well_text", player=player, delta=d)
            elif delta < -0.3:
                color = "#C62828"
                label = t("modal.verdict_under_title")
                text = t("modal.verdict_under_text", player=player, delta=d)
            else:
                color = "#777"
                label = t("modal.verdict_balanced_title")
                text = t("modal.verdict_balanced_text", delta=d)
            st.markdown(
                f"<div style='padding:8px;border-left:4px solid {color};"
                f"background:#f7f7f7;margin:6px 0;'><b>{label}.</b> {text}</div>",
                unsafe_allow_html=True,
            )

        # Mini bar chart of fantavoto over time, coloured by active state
        me = ap[(ap.team == team) & (ap.player == player) & ap.fantavoto.notna()].copy()
        if not me.empty:
            _mini_active = t("modal.mini_active")
            _mini_missed = t("modal.mini_missed")
            me["bucket"] = me.active.map({True: _mini_active, False: _mini_missed})
            fig = px.bar(
                me, x="giornata", y="fantavoto", color="bucket",
                color_discrete_map={_mini_active: ACTIVE_COLOR, _mini_missed: MISSED_COLOR},
                labels={"fantavoto": i18n.col("fantavoto"), "giornata": i18n.col("giornata"), "bucket": ""},
            )
            fig.update_layout(
                height=220, margin=dict(l=10, r=10, t=10, b=10),
                xaxis=dict(dtick=2),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig, width="stretch", key=f"player_modal_bars_{team}_{player}")

        if st.button(t("modal.open_player", player=player),
                     width="stretch", type="primary"):
            # See _team_modal — both canonical and widget keys for resilience.
            st.session_state["_canon_league"] = league
            st.session_state["_canon_competition"] = comp
            st.session_state["_canon_team"] = team
            st.session_state["_canon_player"] = player
            st.session_state["selected_league"] = league
            st.session_state["selected_competition"] = comp
            st.session_state["selected_team"] = team
            st.session_state["selected_player"] = player
            st.switch_page("views/player_detail.py")

    _dialog()
