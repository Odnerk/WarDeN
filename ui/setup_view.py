"""Campaign Setup & Character Creation Screen (Proposal Wireframe Page 7)."""

from __future__ import annotations

import streamlit as st

from ui.mocks import (
    DIFFICULTY_OPTIONS,
    MAX_INPUT_CHARS,
    campaign_from_json,
    create_new_campaign,
    load_classes_data,
    load_environments_data,
)
from ui.styles import (
    render_class_card,
    render_section_header,
    render_setup_header,
    render_top_bar,
)


def render_setup_view() -> None:
    """Render Page 7's 2-column Campaign Setup & Class Selection screen."""
    classes = load_classes_data()
    environments = load_environments_data()

    class_names = list(classes.keys())
    env_names = [env["name"] for env in environments]

    render_top_bar()
    render_setup_header()

    # Single st.form prevents premature reruns while configuring campaign & class.
    with st.form("campaign_setup_form", border=False, enter_to_submit=False):
        left_col, right_col = st.columns([1.05, 1.0], gap="medium")

        # 01 Campaign details card
        with left_col:
            with st.container(border=True):
                render_section_header("01", "Campaign details")

                r1_c1, r1_c2 = st.columns(2, gap="small")
                with r1_c1:
                    premise = st.text_input(
                        "Premise",
                        value="",
                        max_chars=MAX_INPUT_CHARS,
                        placeholder="Describe the central conflict or quest...",
                    )
                with r1_c2:
                    adventure_direction = st.text_input(
                        "Adventure Direction",
                        value="",
                        max_chars=MAX_INPUT_CHARS,
                        placeholder="Where should the story lead?",
                    )

                r2_c1, r2_c2 = st.columns(2, gap="small")
                with r2_c1:
                    difficulty = st.selectbox(
                        "Difficulty",
                        options=list(DIFFICULTY_OPTIONS),
                        index=0,
                    )
                with r2_c2:
                    environment = st.selectbox(
                        "Environment",
                        options=env_names,
                        index=0,
                    )

                character_name = st.text_input(
                    "Character Name",
                    value="",
                    max_chars=40,
                    placeholder="Rowan",
                )

                custom_instructions = st.text_area(
                    "Custom Instructions (optional)",
                    value="",
                    max_chars=MAX_INPUT_CHARS,
                    height=95,
                    placeholder="Add tone, rules, themes, or other guidance...",
                )

        # 02 Choose a class card
        with right_col:
            with st.container(border=True):
                render_section_header("02", "Choose a class")

                card_cols = st.columns(len(class_names), gap="small")
                default_selected = st.session_state.get("setup_selected_class", class_names[0])
                for idx, (col, cls_name) in enumerate(zip(card_cols, class_names)):
                    with col:
                        render_class_card(
                            classes[cls_name],
                            selected=(cls_name == default_selected),
                            card_index=idx,
                        )

                selected_class = st.radio(
                    "Select your class",
                    options=class_names,
                    horizontal=True,
                    index=class_names.index(default_selected) if default_selected in class_names else 0,
                    format_func=lambda c: f"{c} ({classes[c].get('max_hp', '?')} HP)",
                    label_visibility="collapsed",
                )

            # Bottom-right Start Campaign CTA button (matches Page 7 placement)
            _, cta_col = st.columns([1.25, 0.75])
            with cta_col:
                submitted = st.form_submit_button(
                    "Start Campaign",
                    type="primary",
                    use_container_width=True,
                )

    if submitted:
        st.session_state.setup_selected_class = selected_class
        chosen_name = character_name.strip() or "Rowan"
        st.session_state.campaign_state = create_new_campaign(
            character_name=chosen_name,
            char_class=selected_class,
            environment=environment,
            premise=premise,
            adventure_direction=adventure_direction,
            difficulty=difficulty,
            custom_instructions=custom_instructions,
        )
        st.session_state.sidebar_feedback = ""
        st.session_state.show_sheet_resume = False
        st.rerun()

    # External save-file uploader kept outside st.form for clean upload handling.
    with st.expander("Resume Saved Campaign (.json)", expanded=False):
        st.caption("Upload a WarDeN JSON save file to continue an unfinished campaign.")
        uploaded_file = st.file_uploader(
            "Upload WarDeN Save (.json)",
            type=["json"],
            accept_multiple_files=False,
            key="resume_campaign_uploader",
            label_visibility="collapsed",
        )
        if uploaded_file is not None:
            if st.button(
                "Load Saved Campaign",
                type="primary",
                key="load_saved_campaign_btn",
            ):
                try:
                    restored_state = campaign_from_json(uploaded_file.getvalue())
                except ValueError as exc:
                    st.error(f"Could not load save file: {exc}")
                else:
                    st.session_state.campaign_state = restored_state
                    st.session_state.sidebar_feedback = "Campaign restored from save file."
                    st.session_state.show_sheet_resume = False
                    st.rerun()
