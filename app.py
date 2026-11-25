"""WarDeN — Main Streamlit Entry Point & Screen Router (Member 3)."""

from __future__ import annotations

import streamlit as st

from ui.chat_view import render_chat_view
from ui.mocks import CampaignState
from ui.setup_view import render_setup_view
from ui.sidebar_sheet import render_sidebar_sheet
from ui.styles import inject_global_styles, render_top_bar


def _init_session_state() -> None:
    if "campaign_state" not in st.session_state:
        st.session_state.campaign_state = None
    if "sidebar_feedback" not in st.session_state:
        st.session_state.sidebar_feedback = ""
    if "show_sheet_resume" not in st.session_state:
        st.session_state.show_sheet_resume = False
    if "setup_selected_class" not in st.session_state:
        st.session_state.setup_selected_class = "Warrior"


def main() -> None:
    st.set_page_config(
        page_title="WarDeN — AI Dungeon Master",
        page_icon="⚔️",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    inject_global_styles()
    _init_session_state()

    state: CampaignState | None = st.session_state.campaign_state

    # Screen 1: Campaign Setup & Character Creation (Page 7)
    if state is None:
        render_setup_view()
        return

    # Shared Powerlevel10k Top Prompt Bar (Pages 8, 9, 10)
    render_top_bar(
        stage=state.campaign_stage,
        current_turn=state.current_turn,
        max_turns=state.max_turns,
        environment=state.environment,
        outcome=state.outcome,
    )

    # Screen 4: Campaign Conclusion (Page 10 — centered single column)
    if state.campaign_stage == "Conclusion":
        render_chat_view()
        return

    # Screens 2 & 3: Main Chat / Combat on Left + Character Sheet Panel on Right (Pages 8 & 9)
    col_chat, col_sheet = st.columns([2.55, 1.0], gap="medium")
    with col_chat:
        render_chat_view()
    with col_sheet:
        render_sidebar_sheet()


if __name__ == "__main__":
    main()
