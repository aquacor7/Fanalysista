"""Centralized colour theme.

Two principles keep the palette legible:
1. Same concept = same colour across all pages.
2. Two kinds of comparison get different visual treatments:
     - Subject vs another real entity (team vs opponent, player vs player)
       → high contrast (SUBJECT_COLOR vs OPPONENT_COLOR — blue vs red).
     - Subject vs hypothetical / what-if (actual vs optimal lineup)
       → same hue, different shade (SUBJECT_COLOR vs WHATIF_COLOR — dark vs light blue).
"""
from __future__ import annotations

# ---- player position (Italian football convention: P=gold, D=green, C=blue, A=red) ----
POSITION_COLOR = {
    "P": "#FFC107",   # gold     — Portiere (goalkeeper)
    "D": "#43A047",   # green    — Difensore
    "C": "#1E88E5",   # blue     — Centrocampista
    "A": "#E53935",   # red      — Attaccante
}
POSITION_ORDER = ["P", "D", "C", "A"]

# ---- appearance category (Player Detail, Team Detail squad views) ----
CATEGORY_COLOR = {
    "Starter":    "#2E7D32",   # dark green
    "Substitute": "#81C784",   # light green
    "Benched":    "#EF6C00",   # orange
    "No voto":    "#9E9E9E",   # grey
}
CATEGORY_ORDER = ["Starter", "Substitute", "Benched", "No voto"]

# ---- captured vs missed contribution (Squad Composition stacked bars) ----
ACTIVE_COLOR  = CATEGORY_COLOR["Starter"]     # dark green — counted toward TOTALE
MISSED_COLOR  = CATEGORY_COLOR["Benched"]     # orange     — had voto but didn't count

# ---- comparison palette ----
# A real-vs-real comparison (high contrast):
SUBJECT_COLOR  = "#1565C0"   # dark blue — the focus entity
OPPONENT_COLOR = "#D32F2F"   # red       — the other side
# A real-vs-hypothetical comparison (same-hue shading):
WHATIF_COLOR   = "#90CAF9"   # light blue — optimal / counterfactual / shadow of subject
