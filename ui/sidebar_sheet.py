"""Right-Hand Character Sheet Panel (Proposal Wireframes Pages 8 & 9)."""

from __future__ import annotations

import re

import streamlit as st

from ui.mocks import (
    CampaignState,
    campaign_from_json,
    campaign_to_json,
    use_consumable_item,
)
from ui.styles import (
    render_ansi_swatches,
    render_character_sheet_header,
    render_equipment_card,
)


def _safe_filename_slug(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip()).strip("_").lower()
    return slug or "warden"


def _on_use_consumable(item_name: str) -> None:
    state: CampaignState | None = st.session_state.get("campaign_state")
    if state is None:
        return
    updated_state, feedback = use_consumable_item(state, item_name)
    st.session_state.campaign_state = updated_state
    st.session_state.sidebar_feedback = feedback


def _on_toggle_resume() -> None:
    st.session_state.show_sheet_resume = not st.session_state.get("show_sheet_resume", False)


@st.fragment
def render_sidebar_sheet() -> None:
    """Render the right-hand Character Sheet inside an isolated ``@st.fragment``.

    Using consumables, toggling Resume, or downloading a save updates only this
    Character Sheet panel without rerunning the main narration feed.
    """
    state: CampaignState | None = st.session_state.get("campaign_state")
    if state is None:
        return

    char = state.character
    buff_parts: list[str] = []
    if char.temp_attack_bonus > 0:
        buff_parts.append(f"+{char.temp_attack_bonus} Attack")
    if char.temp_defense_bonus > 0:
        buff_parts.append(f"+{char.temp_defense_bonus} Defense")
    active_buff_text = ", ".join(buff_parts)

    with st.container(border=True):
        # Header, Health Bar, and 2x2 Attributes Grid
        render_character_sheet_header(
            name=char.name,
            char_class=char.char_class,
            current_hp=char.current_hp,
            max_hp=char.max_hp,
            attack=char.attack,
            defense=char.defense,
            magic=char.magic,
            speed=char.speed,
            active_buff=active_buff_text,
        )

        # Equipment Slots
        render_equipment_card(
            weapon=char.equipment.weapon,
            armor=char.equipment.armor,
            accessory=char.equipment.accessory,
        )

        # Consumables Section
        st.html('<div class="t-eyebrow" style="margin-bottom:0.4rem;">CONSUMABLES</div>')
        is_locked = state.campaign_stage == "Conclusion" or char.current_hp <= 0

        for idx, item in enumerate(char.consumables):
            btn_label = f"{item.name} · ×{item.quantity}"
            st.button(
                btn_label,
                key=f"use_consumable_{idx}_{item.name}",
                disabled=is_locked or item.quantity <= 0,
                help=item.description,
                use_container_width=True,
                on_click=_on_use_consumable,
                args=(item.name,),
            )

        if len(char.consumables) < 3:
            st.html(
                '<div class="t-equip-line" style="color:#7D8590;padding:0.2rem 0.1rem;">'
                "<span>Empty slot</span><span>—</span></div>"
            )

        feedback_msg = st.session_state.get("sidebar_feedback", "")
        if feedback_msg:
            st.caption(feedback_msg)

        # Signature neofetch 16-color ANSI palette swatch bar
        render_ansi_swatches()
        st.html('<div style="border-top:1px dashed #353B45;margin:0.55rem 0;"></div>')

        # Bottom Save / Resume side-by-side buttons (matches Pages 8 & 9)
        save_payload = campaign_to_json(state)
        filename = f"warden_{_safe_filename_slug(char.name)}_turn{state.current_turn}.json"

        btn_save_col, btn_resume_col = st.columns(2, gap="small")
        with btn_save_col:
            st.download_button(
                label="Save",
                data=save_payload,
                file_name=filename,
                mime="application/json",
                use_container_width=True,
                key="save_campaign_download_btn",
            )
        with btn_resume_col:
            st.button(
                label="Resume",
                use_container_width=True,
                key="toggle_sheet_resume_btn",
                on_click=_on_toggle_resume,
            )

        if st.session_state.get("show_sheet_resume", False):
            uploaded = st.file_uploader(
                "Load save (.json)",
                type=["json"],
                accept_multiple_files=False,
                key="sheet_resume_uploader",
            )
            if uploaded is not None:
                if st.button(
                    "Apply Save File",
                    type="primary",
                    use_container_width=True,
                    key="sheet_apply_save_btn",
                ):
                    try:
                        restored = campaign_from_json(uploaded.getvalue())
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        st.session_state.campaign_state = restored
                        st.session_state.sidebar_feedback = "Campaign restored."
                        st.session_state.show_sheet_resume = False
                        st.rerun(scope="app")

            if st.button(
                "Start New Campaign",
                use_container_width=True,
                key="sheet_return_setup_btn",
            ):
                st.session_state.campaign_state = None
                st.session_state.sidebar_feedback = ""
                st.session_state.show_sheet_resume = False
                st.rerun(scope="app")
