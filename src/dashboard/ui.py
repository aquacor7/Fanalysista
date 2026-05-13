"""Shared UI helpers — breadcrumbs and other small reusable layout bits."""
from __future__ import annotations

import streamlit as st


def breadcrumbs(*steps: tuple[str, str | None]) -> None:
    """Render a horizontal breadcrumb trail at the top of a page.

    Each step is a ``(label, page_path)`` tuple:
        - if ``page_path`` is a string, the label becomes a clickable link
          (uses ``st.page_link`` so it integrates with Streamlit's router)
        - if ``page_path`` is ``None``, the label is the current location and
          renders bold without a link

    Example for the Player Detail page:

        breadcrumbs(
            ("League Table", "pages/1_League_Table.py"),
            (team_name,      "pages/2_Team_Detail.py"),
            (player_name,    None),
        )

    Receiving pages should set ``st.session_state.selected_team`` /
    ``selected_player`` before the click happens so the linked page lands
    on the right entity.
    """
    if not steps:
        return

    # Interleave step columns with thin separator columns:
    # [step, sep, step, sep, ..., step]
    n = len(steps)
    widths: list[float] = []
    for i in range(n):
        widths.append(3)
        if i < n - 1:
            widths.append(0.3)

    cols = st.columns(widths, gap="small", vertical_alignment="center")

    for i, (label, path) in enumerate(steps):
        with cols[i * 2]:
            if path:
                st.page_link(path, label=label)
            else:
                st.markdown(f"**{label}**")
        if i < n - 1:
            with cols[i * 2 + 1]:
                st.markdown("›")
