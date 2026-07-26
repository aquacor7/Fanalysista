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
DEFAULT_LANG = "en"

# language code -> display name (shown in the picker in the language's own
# script so users recognise it regardless of the current UI language).
LANGUAGES: dict[str, str] = {
    "en": "English",
    "zh": "中文（简体）",
}


@lru_cache(maxsize=8)
def _load(lang: str) -> dict[str, str]:
    path = I18N_DIR / f"{lang}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def get_lang() -> str:
    """Return the active language code, defaulting to English if unset/unknown."""
    lang = st.session_state.get("_lang", DEFAULT_LANG)
    return lang if lang in LANGUAGES else DEFAULT_LANG


def t(key: str, **fmt: object) -> str:
    """Translate ``key`` into the active language.

    Lookup order: active locale → English → the key itself. Placeholder
    substitution via ``str.format(**fmt)`` is applied when ``fmt`` is given
    and, on any formatting error, the unformatted string is returned rather
    than raising.
    """
    value = _load(get_lang()).get(key)
    if value is None:
        value = _load(DEFAULT_LANG).get(key, key)
    if fmt:
        try:
            return value.format(**fmt)
        except (KeyError, IndexError, ValueError):
            return value
    return value
