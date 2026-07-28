"""Cached data loaders and the shared sidebar league/competition selector."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
GOLD_ROOT = ROOT / "data" / "gold"
SILVER_ROOT = ROOT / "data" / "silver"


@st.cache_data
def list_available() -> dict[str, list[str]]:
    """Discover {league_alias: [comp_slug, ...]} from the gold/ folder."""
    if not GOLD_ROOT.is_dir():
        return {}
    out: dict[str, list[str]] = {}
    for ld in sorted(GOLD_ROOT.iterdir()):
        if not ld.is_dir():
            continue
        comps = sorted(
            c.name for c in ld.iterdir()
            if c.is_dir() and (c / "team_season.csv").exists()
        )
        if comps:
            out[ld.name] = comps
    return out


def require_data() -> tuple[str, str]:
    """Render the sidebar league/competition selector. Stops if gold is empty."""
    # Every page calls require_data() first, so this is a reliable hook for
    # resetting per-script-run state. The modal helpers use this flag to
    # ensure at most one @st.dialog is opened per run (Streamlit otherwise
    # raises StreamlitDuplicateElementId).
    from modals import reset_per_run_modal_state
    reset_per_run_modal_state()

    # The language toggle is rendered by the app.py router (after the active
    # page runs, so it sits at the bottom of the sidebar). Here we only need
    # the translator for the selector labels below.
    from i18n import t

    available = list_available()
    if not available:
        st.error(
            "No gold tables found.\n\nRun:\n"
            "```\n"
            "python build_silver.py -l <league> -c <competition>\n"
            "python build_gold.py   -l <league> -c <competition>\n"
            "```"
        )
        st.stop()

    leagues = list(available.keys())
    league = persist_sidebar_selectbox(
        t("sidebar.league"), leagues,
        widget_key="selected_league", canon_key="_canon_league",
    )

    comps = available[league]
    comp = persist_sidebar_selectbox(
        t("sidebar.competition"), comps,
        widget_key="selected_competition", canon_key="_canon_competition",
    )

    st.sidebar.caption(f"{league}  /  {comp.replace('_', ' ')}")
    return league, comp


def persist_sidebar_selectbox(
    label: str,
    options: list[str],
    *,
    widget_key: str,
    canon_key: str,
    format_func=None,
) -> str:
    """Sidebar selectbox whose value survives page navigation.

    Streamlit 1.57 garbage-collects most widget state across multipage
    navigation (verified empirically: after clicking a page link, the
    widget key is *missing* from session_state). To survive that, we mirror
    every user interaction into a non-widget canonical key (``_canon_*``)
    via an ``on_change`` callback. On every page-render, if the widget key
    is missing or stale (i.e., not in the current options list), we restore
    it from the canonical key *before* the widget is instantiated.

    NOTE: we only seed the widget when its value is *not in options*. Inside
    a single page, after the user picks a value, ``selected_X`` is set by
    Streamlit AND ``_canon_X`` is set by ``on_change`` — both equal the
    user's choice — so we don't clobber the live interaction.
    """
    def _on_change():
        # Fires only for user interactions. Mirror the new choice into canon
        # so canon always reflects the user's most recent intent.
        st.session_state[canon_key] = st.session_state[widget_key]

    # ALWAYS force the widget value from canon before it renders. Streamlit
    # 1.57's sidebar widgets sometimes reset themselves across page nav even
    # when session_state[widget_key] is set — verified empirically by dumping
    # state at require_data START vs END. Forcing the value every render is
    # safe because on_change keeps canon in sync with the user's choice, so
    # overwriting session_state[widget_key] = canon simply re-asserts the
    # user's last pick.
    canon = st.session_state.get(canon_key)
    if canon not in options:
        canon = options[0]
    st.session_state[widget_key] = canon
    # Keep canon valid too (e.g., a stale comp value after league switch).
    st.session_state[canon_key] = canon

    kwargs = {} if format_func is None else {"format_func": format_func}
    value = st.sidebar.selectbox(
        label, options, key=widget_key, on_change=_on_change, **kwargs,
    )
    return value


@st.cache_data
def load_player_season(league: str, comp: str) -> pd.DataFrame:
    return pd.read_csv(GOLD_ROOT / league / comp / "player_season.csv")


@st.cache_data
def load_team_season(league: str, comp: str) -> pd.DataFrame:
    return pd.read_csv(GOLD_ROOT / league / comp / "team_season.csv")


_SIDE_NORMALIZE = {"left": "home", "right": "away"}


@st.cache_data
def load_matches(league: str, comp: str) -> pd.DataFrame:
    df = pd.read_csv(SILVER_ROOT / league / comp / "matches.csv")
    # Backward-compat: older silver CSVs use 'left'/'right' instead of 'home'/'away'.
    if "side" in df.columns:
        df["side"] = df["side"].replace(_SIDE_NORMALIZE)
    return df


@st.cache_data
def load_appearances(league: str, comp: str) -> pd.DataFrame:
    return pd.read_csv(SILVER_ROOT / league / comp / "appearances.csv")


@st.cache_data
def load_regret(league: str, comp: str) -> pd.DataFrame:
    return pd.read_csv(GOLD_ROOT / league / comp / "regret.csv")


@st.cache_data
def load_player_market(league: str, comp: str) -> pd.DataFrame:
    """Per owned player: cost, quotations, FVM, season perf + ROI/edge.

    Returns an empty DataFrame if the market layer hasn't been built for this
    competition (build_market.py), so pages can degrade gracefully.
    """
    path = GOLD_ROOT / league / comp / "player_market.csv"
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


@st.cache_data
def load_team_market(league: str, comp: str) -> pd.DataFrame:
    """Per participant: spend, return, ROI, squad value change, spend-by-role."""
    path = GOLD_ROOT / league / comp / "team_market.csv"
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def has_market(league: str, comp: str) -> bool:
    return (GOLD_ROOT / league / comp / "player_market.csv").exists()
