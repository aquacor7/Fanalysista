"""Lightweight internationalisation (i18n) for the dashboard.

Design principles:
    - **UI strings only.** Data values — team names, player names, competition
      names, position codes (P/D/C/A) — are NEVER translated. They come from
      fantacalcio.it and stay exactly as printed.
    - Translations live in ``i18n/{lang}.json`` as flat ``{key: string}`` maps.
    - ``t(key, **fmt)`` looks up the key in the active locale, falling back to
      English, then to the key itself (so a missing key shows up visibly in the
      UI as its dotted name rather than crashing). ``**fmt`` values are
      substituted via ``str.format`` when present.
    - The active language code lives in ``st.session_state["_lang"]`` (e.g.
      "en" / "zh"), set by the sidebar picker rendered in
      ``data.require_data()``. Reading happens through ``get_lang()``.

To add a language: drop an ``i18n/{code}.json`` next to en.json and add the
code → display-name entry to ``LANGUAGES`` below. To add a string: add the key
to en.json (the source of truth) and each translation file.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import streamlit as st

I18N_DIR = Path(__file__).resolve().parent / "i18n"

# The language a fresh visitor sees before touching the picker. The audience is
# a Chinese-speaking fanta group, so Chinese is the default.
DEFAULT_LANG = "zh"
# The source-of-truth locale used to fill in any key missing from the active
# locale. en.json is kept complete, so this must stay "en".
FALLBACK_LANG = "en"

# language code -> display name (shown in the picker in the language's own
# script so users recognise it regardless of the current UI language).
LANGUAGES: dict[str, str] = {
    "en": "English",
    "zh": "中文（简体）",
}
# Short labels for the compact bottom-of-sidebar toggle.
LANGUAGE_SHORT: dict[str, str] = {
    "en": "EN",
    "zh": "中文",
}


@lru_cache(maxsize=8)
def _load(lang: str) -> dict[str, str]:
    path = I18N_DIR / f"{lang}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def get_lang() -> str:
    """Return the active language code, defaulting to DEFAULT_LANG if unset/unknown."""
    lang = st.session_state.get("_lang", DEFAULT_LANG)
    return lang if lang in LANGUAGES else DEFAULT_LANG


def col(name: str) -> str:
    """Translated header for a data column, falling back to the raw column name.

    Unlike ``t()``, a missing ``col.<name>`` key returns the untranslated column
    name (e.g. ``"totale_max_vs"``) rather than the dotted key — so obscure
    columns without a translation still read sensibly.
    """
    key = f"col.{name}"
    value = _load(get_lang()).get(key)
    if value is None:
        value = _load(FALLBACK_LANG).get(key)
    return value if value is not None else name


def cat(name: str) -> str:
    """Translated label for an appearance category, falling back to the raw name.

    Categories (``Starter`` / ``Substitute`` / ``Benched`` / ``No voto``) are
    used internally as keys (colour maps, groupby); use this only at display
    points, and rekey any Plotly colour/order maps to the translated labels.
    """
    key = f"cat.{name}"
    value = _load(get_lang()).get(key)
    if value is None:
        value = _load(FALLBACK_LANG).get(key)
    return value if value is not None else name


def columns_config(
    df,
    *,
    formats: dict[str, str] | None = None,
    progress: "set[str] | list[str] | None" = None,
    checkbox: "set[str] | list[str] | None" = None,
) -> dict:
    """Build a Streamlit ``column_config`` translating every column header.

    Every column's label comes from ``col()``. Types are inferred:
    ``formats`` maps a column to a NumberColumn format string; ``progress``
    columns render as 0..1 percent ProgressColumns; ``checkbox`` columns as
    CheckboxColumns; remaining numeric columns get a default NumberColumn and
    everything else a TextColumn — so formatting/alignment is preserved while
    headers get localised.
    """
    import pandas as pd

    formats = formats or {}
    progress = set(progress or [])
    checkbox = set(checkbox or [])
    cfg: dict = {}
    for c in df.columns:
        label = col(c)
        if c in progress:
            cfg[c] = st.column_config.ProgressColumn(
                label, min_value=0.0, max_value=1.0, format="percent")
        elif c in checkbox:
            cfg[c] = st.column_config.CheckboxColumn(label)
        elif c in formats:
            cfg[c] = st.column_config.NumberColumn(label, format=formats[c])
        elif pd.api.types.is_numeric_dtype(df[c]):
            cfg[c] = st.column_config.NumberColumn(label)
        else:
            cfg[c] = st.column_config.TextColumn(label)
    return cfg


def t(key: str, **fmt: object) -> str:
    """Translate ``key`` into the active language.

    Lookup order: active locale → FALLBACK_LANG (English source of truth) →
    the key itself (so a missing key shows up visibly rather than crashing).
    Placeholder substitution via ``str.format(**fmt)`` is applied when ``fmt``
    is given; on any formatting error the unformatted string is returned.
    """
    value = _load(get_lang()).get(key)
    if value is None:
        value = _load(FALLBACK_LANG).get(key, key)
    if fmt:
        try:
            return value.format(**fmt)
        except (KeyError, IndexError, ValueError):
            return value
    return value


def render_language_toggle() -> None:
    """Render a compact language toggle at the bottom of the sidebar.

    Meant to be called *last* in the entry script (after the active page has
    run), so it naturally sits below the page's own sidebar selectors with no
    positioning CSS. A horizontal radio guarantees exactly one selection (no
    accidental deselection); the value persists in ``st.session_state["_lang"]``
    — the canonical key ``get_lang()`` reads — and is force-seeded each run so
    it survives navigation.
    """
    codes = list(LANGUAGES.keys())
    if st.session_state.get("_lang") not in codes:
        st.session_state["_lang"] = DEFAULT_LANG

    def _on_change() -> None:
        st.session_state["_lang"] = st.session_state["_lang_widget"]

    st.session_state["_lang_widget"] = st.session_state["_lang"]
    st.sidebar.divider()
    st.sidebar.radio(
        t("sidebar.language"),
        options=codes,
        format_func=lambda c: LANGUAGE_SHORT[c],
        key="_lang_widget",
        on_change=_on_change,
        horizontal=True,
    )
