"""Campaign Setup & Character Creation Screen (Proposal Wireframe Page 7)."""

from __future__ import annotations

import streamlit as st

from ui.backend import (
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


def _select_class(cls_name: str) -> None:
    """Sync class selection between clickable class cards and the radio control."""
    st.session_state.setup_selected_class = cls_name
    st.session_state.setup_class_radio = cls_name


def _on_radio_change() -> None:
    """Sync radio selection back to setup_selected_class."""
    st.session_state.setup_selected_class = st.session_state.setup_class_radio


def render_setup_view() -> None:
    """Render Page 7's 2-column Campaign Setup & Class Selection screen."""
    classes = load_classes_data()
    environments = load_environments_data()

    class_names = list(classes.keys())
    env_names = [env["name"] for env in environments]

    if st.session_state.get("setup_selected_class") not in class_names:
        st.session_state.setup_selected_class = class_names[0]
    if st.session_state.get("setup_class_radio") not in class_names:
        st.session_state.setup_class_radio = st.session_state.setup_selected_class

    render_top_bar()
    render_setup_header()

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
                    key="setup_premise",
                )
            with r1_c2:
                adventure_direction = st.text_input(
                    "Adventure Direction",
                    value="",
                    max_chars=MAX_INPUT_CHARS,
                    placeholder="Where should the story lead?",
                    key="setup_direction",
                )

            r2_c1, r2_c2 = st.columns(2, gap="small")
            with r2_c1:
                difficulty = st.selectbox(
                    "Difficulty",
                    options=list(DIFFICULTY_OPTIONS),
                    index=0,
                    key="setup_difficulty",
                )
            with r2_c2:
                environment = st.selectbox(
                    "Environment",
                    options=env_names,
                    index=0,
                    key="setup_environment",
                )

            character_name = st.text_input(
                "Character Name",
                value="",
                max_chars=40,
                placeholder="Rowan",
                key="setup_character_name",
            )

            custom_instructions = st.text_area(
                "Custom Instructions (optional)",
                value="",
                max_chars=MAX_INPUT_CHARS,
                height=95,
                placeholder="Add tone, rules, themes, or other guidance...",
                key="setup_custom_instructions",
            )

    # 02 Choose a class card
    with right_col:
        with st.container(border=True):
            render_section_header("02", "Choose a class")

            card_cols = st.columns(len(class_names), gap="small")
            selected_class = st.session_state.setup_selected_class
            for idx, (col, cls_name) in enumerate(zip(card_cols, class_names)):
                with col:
                    with st.container(key=f"class_card_wrap_{idx}"):
                        render_class_card(
                            classes[cls_name],
                            selected=(cls_name == selected_class),
                            card_index=idx,
                        )
                        st.button(
                            f"Select {cls_name}",
                            key=f"class_card_btn_{cls_name}",
                            on_click=_select_class,
                            args=(cls_name,),
                            use_container_width=True,
                        )

            selected_class = st.radio(
                "Select your class",
                options=class_names,
                horizontal=True,
                key="setup_class_radio",
                on_change=_on_radio_change,
                format_func=lambda c: f"{c} ({classes[c].get('max_hp', '?')} HP)",
                label_visibility="collapsed",
            )

        # Bottom-right Start Campaign CTA button (matches Page 7 placement)
        _, cta_col = st.columns([1.25, 0.75])
        with cta_col:
            submitted = st.button(
                "Start Campaign",
                type="primary",
                use_container_width=True,
                key="start_campaign_submit_btn",
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
