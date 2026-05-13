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
    league = st.sidebar.selectbox("League", leagues, key="league")
    comp = st.sidebar.selectbox("Competition", available[league], key="competition")
    st.sidebar.caption(f"{league}  /  {comp.replace('_', ' ')}")
    return league, comp


@st.cache_data
def load_player_season(league: str, comp: str) -> pd.DataFrame:
    return pd.read_csv(GOLD_ROOT / league / comp / "player_season.csv")


@st.cache_data
def load_team_season(league: str, comp: str) -> pd.DataFrame:
    return pd.read_csv(GOLD_ROOT / league / comp / "team_season.csv")


@st.cache_data
def load_position_rollup(league: str, comp: str) -> pd.DataFrame:
    return pd.read_csv(GOLD_ROOT / league / comp / "position_rollup.csv")


@st.cache_data
def load_matches(league: str, comp: str) -> pd.DataFrame:
    return pd.read_csv(SILVER_ROOT / league / comp / "matches.csv")


@st.cache_data
def load_appearances(league: str, comp: str) -> pd.DataFrame:
    return pd.read_csv(SILVER_ROOT / league / comp / "appearances.csv")


@st.cache_data
def load_regret(league: str, comp: str) -> pd.DataFrame:
    return pd.read_csv(GOLD_ROOT / league / comp / "regret.csv")
