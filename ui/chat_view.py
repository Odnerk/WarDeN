"""Main Chat (Page 8), Dedicated Combat View (Page 9), and Conclusion View (Page 10)."""

from __future__ import annotations

from dataclasses import asdict

import streamlit as st

from ui.backend import (
    MAX_INPUT_CHARS,
    CampaignState,
    ChatMessage,
    process_player_turn,
    use_consumable_item,
)
from ui.styles import (
    render_combat_arena,
    render_combat_header,
    render_conclusion_banner,
    render_engine_roll_strip,
    render_panel_bar,
    render_stage_progress,
)


def _render_message(msg: ChatMessage, player_name: str = "You") -> None:
    """Render a single chat turn strictly via native ``st.chat_message`` (XSS-safe)."""
    if msg.role == "user":
        with st.chat_message("user"):
            st.caption(player_name)
            st.text(msg.content)
        return

    # Display deterministic engine roll strips BEFORE combat narration.
    if msg.roll_detail:
        d20 = msg.roll_detail.get("d20_roll", 0)
        mod = msg.roll_detail.get("modifier", 0)
        tot = msg.roll_detail.get("total", 0)
        dc = msg.roll_detail.get("target_dc", 13)
        outcome = msg.roll_detail.get("outcome", "Miss")
        dmg = msg.roll_detail.get("damage", 0)
        action_label = msg.roll_detail.get("action_label", "Player attack")

        player_outcome = f"{outcome} (-{dmg} HP)" if dmg else str(outcome)
        render_engine_roll_strip(
            label=str(action_label),
            roll_detail=f"D20 {d20} (+{mod} = {tot}) vs. Defense {dc}",
            outcome_text=player_outcome,
        )

        enemy_roll = msg.roll_detail.get("enemy_roll_total", 0)
        if enemy_roll:
            player_dc = msg.roll_detail.get("player_dc", 13)
            e_hit = bool(msg.roll_detail.get("enemy_hit", False))
            e_dmg = msg.roll_detail.get("enemy_damage", 0)
            render_engine_roll_strip(
                label="Enemy attack",
                roll_detail=f"{enemy_roll} vs. Defense {player_dc}",
                outcome_text=f"Hit (-{e_dmg} HP)" if e_hit else "Miss",
            )

    with st.chat_message("assistant"):
        speaker_label = f"WarDeN · {msg.npc_speaker}" if msg.npc_speaker else "WarDeN"
        st.caption(speaker_label)
        # Default st.markdown auto-escapes raw HTML.
        st.markdown(msg.content)


def _dispatch_action(state: CampaignState, action_text: str, action_type: str) -> None:
    st.session_state.campaign_state = process_player_turn(
        state=state,
        action_text=action_text,
        action_type=action_type,
    )
    st.session_state.sidebar_feedback = ""
    st.rerun()


def _quick_use_combat_item(state: CampaignState) -> None:
    """Use the first available consumable when the player clicks ``Use Item`` in combat."""
    for item in state.character.consumables:
        if item.quantity > 0:
            updated, msg = use_consumable_item(state, item.name)
            st.session_state.campaign_state = updated
            st.session_state.sidebar_feedback = msg
            st.rerun()
            return
    st.session_state.sidebar_feedback = "No usable consumables remaining."
    st.rerun()


def _render_exploration_view(state: CampaignState) -> None:
    """Render Screen 2 — Main Chat / Exploration Screen (Proposal Wireframe Page 8)."""
    story_messages = [m for m in state.history if not m.is_combat]

    with st.container(border=True):
        render_stage_progress(
            current_stage=state.campaign_stage,
            current_turn=state.current_turn,
            max_turns=state.max_turns,
            chapter_title=state.chapter_title,
        )

        with st.container(height=440, border=True):
            for msg in story_messages:
                _render_message(msg, player_name=state.character.name)

        st.html('<div style="border-top:1px dashed #353B45;margin:0.75rem 0 0.65rem 0;"></div>')

        c1, c2, c3, _spacer = st.columns([0.95, 1.05, 0.95, 1.05], gap="small")
        with c1:
            if st.button(
                "Combat",
                use_container_width=True,
                key=f"quick_combat_t{state.current_turn}",
            ):
                _dispatch_action(
                    state,
                    "Advance with weapons drawn and confront the danger ahead",
                    action_type="Combat",
                )
        with c2:
            if st.button(
                "Exploration",
                use_container_width=True,
                key=f"quick_explore_t{state.current_turn}",
            ):
                _dispatch_action(
                    state,
                    f"Explore the {state.environment.lower()} carefully for tracks and clues",
                    action_type="Exploration",
                )
        with c3:
            if st.button(
                "Dialogue",
                use_container_width=True,
                key=f"quick_dialogue_t{state.current_turn}",
            ):
                _dispatch_action(
                    state,
                    "Speak with the nearby guide to learn what awaits ahead",
                    action_type="Dialogue",
                )

        if state.suggested_options:
            st.caption("Suggested choices")
            opt_cols = st.columns(len(state.suggested_options), gap="small")
            for idx, (col, option_text) in enumerate(zip(opt_cols, state.suggested_options)):
                with col:
                    if st.button(
                        option_text,
                        use_container_width=True,
                        key=f"dm_option_{idx}_t{state.current_turn}",
                    ):
                        _dispatch_action(state, option_text, action_type="Exploration")

        player_prompt = st.chat_input(
            "What do you do?",
            max_chars=MAX_INPUT_CHARS,
        )
        if player_prompt:
            _dispatch_action(state, player_prompt, action_type="Free Action")


def _render_combat_view(state: CampaignState) -> None:
    """Render Screen 3 — Dedicated Combat / Encounter View (Proposal Wireframe Page 9)."""
    assert state.active_enemy is not None
    enemy = state.active_enemy
    combat_messages = [m for m in state.history if m.is_combat]
    exploration_messages = [m for m in state.history if not m.is_combat]

    with st.container(border=True):
        # 1. Three-Column Combat Status Strip (Enemy | D20 Result | Your Health)
        render_combat_header(
            enemy_name=enemy.name,
            enemy_hp=enemy.current_hp,
            enemy_max_hp=enemy.max_hp,
            player_hp=state.character.current_hp,
            player_max_hp=state.character.max_hp,
            last_roll=asdict(state.last_roll) if state.last_roll else None,
            combat_round=max(1, state.combat_round),
        )

        # 2. ASCII Character vs. Enemy Battle Arena Visual
        render_combat_arena(
            player_name=state.character.name,
            player_class=state.character.char_class,
            enemy_name=enemy.name,
            enemy_title=enemy.title,
            combat_round=max(1, state.combat_round),
            last_roll=asdict(state.last_roll) if state.last_roll else None,
        )

        # 3. Dedicated Combat Narration Feed (isolated from Exploration turns)
        with st.container(height=300, border=True):
            if not combat_messages:
                with st.chat_message("assistant"):
                    st.caption("WarDeN")
                    st.markdown(f"A {enemy.name} blocks your path. Prepare for battle.")
            else:
                for msg in combat_messages:
                    _render_message(msg, player_name=state.character.name)

        st.html('<div style="border-top:1px dashed #353B45;margin:0.75rem 0 0.65rem 0;"></div>')

        # 4. Combat Action Controls (Attack / Class Skills / Use Item)
        primary_ab = state.character.abilities[0] if state.character.abilities else None
        secondary_ab = state.character.abilities[1] if len(state.character.abilities) > 1 else None
        primary_name = primary_ab.name if primary_ab else "Power Strike"
        primary_help = primary_ab.description if primary_ab else None

        if secondary_ab is not None:
            c1, c2, c3, c4 = st.columns([0.9, 1.15, 1.0, 0.95], gap="small")
        else:
            c1, c2, c4, _spacer = st.columns([0.9, 1.2, 0.95, 0.95], gap="small")
            c3 = None

        with c1:
            if st.button(
                "Attack",
                type="primary",
                use_container_width=True,
                key=f"quick_attack_t{state.current_turn}",
            ):
                _dispatch_action(
                    state,
                    f"Attack the {enemy.name} with {state.character.equipment.weapon}",
                    action_type="Attack",
                )
        with c2:
            if st.button(
                primary_name,
                help=primary_help,
                use_container_width=True,
                key=f"quick_ability_t{state.current_turn}",
            ):
                _dispatch_action(
                    state,
                    f"Use {primary_name} against the {enemy.name}",
                    action_type="Use Ability",
                )
        if c3 is not None and secondary_ab is not None:
            with c3:
                if st.button(
                    secondary_ab.name,
                    help=secondary_ab.description,
                    use_container_width=True,
                    key=f"quick_secondary_ability_t{state.current_turn}",
                ):
                    _dispatch_action(
                        state,
                        f"Use {secondary_ab.name} against the {enemy.name}",
                        action_type="Defend",
                    )
        with c4:
            has_items = any(it.quantity > 0 for it in state.character.consumables)
            if st.button(
                "Use Item",
                disabled=not has_items,
                use_container_width=True,
                key=f"quick_item_t{state.current_turn}",
            ):
                _quick_use_combat_item(state)

        if state.suggested_options:
            st.caption("Suggested combat actions")
            opt_cols = st.columns(len(state.suggested_options), gap="small")
            for idx, (col, option_text) in enumerate(zip(opt_cols, state.suggested_options)):
                with col:
                    if st.button(
                        option_text,
                        use_container_width=True,
                        key=f"dm_option_{idx}_t{state.current_turn}",
                    ):
                        _dispatch_action(state, option_text, action_type="Attack")

        player_prompt = st.chat_input(
            "Describe your combat action...",
            max_chars=MAX_INPUT_CHARS,
        )
        if player_prompt:
            _dispatch_action(state, player_prompt, action_type="Attack")

        if exploration_messages:
            with st.expander("Previous Exploration Log", expanded=False):
                for msg in exploration_messages:
                    _render_message(msg, player_name=state.character.name)


def _render_conclusion_view(state: CampaignState) -> None:
    """Render Screen 4 — Campaign Conclusion Screen (Proposal Wireframe Page 10)."""
    _, center, _ = st.columns([0.1, 0.8, 0.1])
    with center:
        render_conclusion_banner(
            campaign_title=state.campaign_title,
            outcome=state.outcome or "Victory",
            character_name=state.character.name,
            char_class=state.character.char_class,
            turns_taken=state.current_turn,
            environment=state.environment,
        )

        # Card 1: FINAL NARRATION | ENDING 01
        ending_code = "ENDING 01" if state.outcome == "Victory" else "ENDING 02"
        with st.container(border=True):
            render_panel_bar("FINAL NARRATION", ending_code)
            assistant_msgs = [m for m in state.history if m.role == "assistant"]
            if assistant_msgs:
                with st.chat_message("assistant"):
                    st.caption("WarDeN")
                    st.markdown(assistant_msgs[-1].content)

        # Card 2: SUMMARY / Key decisions (Page 10 two-column layout)
        with st.container(border=True):
            sum_left, sum_right = st.columns([0.32, 0.68], gap="medium")
            with sum_left:
                st.html(
                    '<div class="t-eyebrow">SUMMARY</div>'
                    '<div style="font-size:1rem;font-weight:700;color:#E6E8EC;">Key decisions</div>'
                )
            with sum_right:
                decisions = state.key_decisions[:4]
                if not decisions:
                    st.text("01  Your adventure concluded swiftly.")
                else:
                    for idx, decision in enumerate(decisions, start=1):
                        st.text(f"{idx:02d}  {decision}")

        with st.expander("Full Campaign Chronicle", expanded=False):
            for msg in state.history:
                _render_message(msg, player_name=state.character.name)

        st.html('<div style="height:0.65rem;"></div>')
        _, btn_col, _ = st.columns([1.0, 1.0, 1.0])
        with btn_col:
            if st.button(
                "Start New Campaign",
                type="primary",
                use_container_width=True,
                key="conclusion_start_new_btn",
            ):
                st.session_state.campaign_state = None
                st.session_state.sidebar_feedback = ""
                st.session_state.show_sheet_resume = False
                st.rerun()


def render_chat_view() -> None:
    """Route between Exploration Screen (Page 8), Dedicated Combat Screen (Page 9), and Conclusion (Page 10)."""
    state: CampaignState | None = st.session_state.get("campaign_state")
    if state is None:
        return

    if state.campaign_stage == "Conclusion":
        _render_conclusion_view(state)
        return

    if state.campaign_stage == "Main Encounter" and state.active_enemy is not None:
        _render_combat_view(state)
        return

    _render_exploration_view(state)
