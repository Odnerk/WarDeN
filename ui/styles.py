"""Arch Linux / Powerlevel10k / neofetch terminal styling and XSS-safe HTML helpers for WarDeN.

Combines the WarDeN proposal wireframe layouts (Pages 7-10) with a Linux
terminal TUI aesthetic inspired by Arch Linux zsh (Powerlevel10k) + neofetch:
- Deep matte terminal canvas (#1B1D1E), elevated pane surface (#22252A),
  1px hairline borders (#353B45), Arch cyan (#1AC8E8), Powerline blue (#3584E4),
  emerald (#38D389), amber (#F5C211), and crimson (#E04040).
- Powerlevel10k segmented top status bar with angled chevrons.
- neofetch-style cyan key/value character sheet, ASCII class emblems, and ANSI
  color swatch strip.

Security contract:
- Uses ``st.html()`` exclusively for static CSS and structured stat/HP/TUI cards.
- Never enables raw HTML in markdown or JavaScript execution.
- Escapes EVERY dynamic value interpolated into HTML via ``html.escape(..., quote=True)``.
- Never accepts raw player input or AI narration text into any HTML template.
"""

from __future__ import annotations

import html
from typing import Any

import streamlit as st

STAGE_ORDER: tuple[str, ...] = (
    "Introduction",
    "Exploration",
    "Main Encounter",
    "Conclusion",
)

_MONO_STACK = (
    '"JetBrains Mono", "Fira Code", "Cascadia Code", '
    'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace'
)

_CLASS_ASCII_EMBLEMS: dict[str, str] = {
    "Warrior": (
        "   ,^.    /|\n"
        "  [===]  / |\n"
        "  |o_o| /  |\n"
        " /|###|\\/  |\n"
        "[+|###|]   |\n"
        "  |###|\n"
        "  /   \\"
    ),
    "Archer": (
        "   /^\\\n"
        "  (o_o)  )\\\n"
        " /|#|\\===>)\n"
        "  |###|  )/\n"
        "  /   \\\n"
        " /     \\"
    ),
    "Mage": (
        "   _*_    *\n"
        "  /o_o\\  /|\\\n"
        "  \\|#|--*-+\n"
        "  /|#|\\   |\n"
        "  /___\\   |\n"
        "  /   \\   |"
    ),
}

_CLASS_ASCII_COMPACT: dict[str, str] = {
    "Warrior": "  /\\\n  ||\n=[||]=\n  ||",
    "Archer": "  |\\\n--+->>\n  |/\n  '",
    "Mage": "  *\n /|\\\n--*--\n  |",
}

_ENEMY_ASCII_SPRITES: dict[str, str] = {
    "Hollow Guard": (
        "  \\___/   |\n"
        "  [x_x]  /|\\\n"
        " /|===|\\ |||\n"
        "[ |===| ]|||\n"
        "  |===|   |\n"
        "  /   \\"
    ),
    "Thorn Stalker": (
        "   /\\_/\\  *\n"
        "  ( >_< )\\|/\n"
        " */|###|\\*\n"
        "  / | | \\\n"
        " /  / \\  \\"
    ),
    "Cinder Wisp": (
        "    .~*.\n"
        "  ~( o o)~\n"
        "  ~|~~~~|~\n"
        "   ~\\/\\/~ \n"
        "    ~  ~"
    ),
    "Ashen Warden": (
        "  \\###/  /|\n"
        "  [>_<] / |\n"
        " /|###|\\/ |\n"
        "[ |###| ] |\n"
        "  |###|   |\n"
        "  /   \\"
    ),
    "Cinder Stalker": (
        "   /\\_/\\  ~\n"
        "  ( >_< )~ ~\n"
        " ~/|###|\\~\n"
        "  / | | \\\n"
        " /  / \\  \\"
    ),
    "Blight Wraith": (
        "    .--.\n"
        "   ( x x)\n"
        "  /|~~~~|\\\n"
        " ~ |~~~~| ~\n"
        "   ~\\/\\/~ \n"
        "    ~  ~"
    ),
    "Ironbound Marauder": (
        "  /###\\ ,==.\n"
        "  [>_<] |==|\n"
        " /|###|\\==||\n"
        "  |###|   ||\n"
        "  /   \\   ||"
    ),
}

_ANSI_PALETTE_HTML = (
    '<div class="t-ansi-bar" aria-hidden="true">'
    '<div class="t-ansi-row">'
    '<span style="background:#282A36;"></span>'
    '<span style="background:#C92A2A;"></span>'
    '<span style="background:#2BB673;"></span>'
    '<span style="background:#E5A50A;"></span>'
    '<span style="background:#2E7CF6;"></span>'
    '<span style="background:#9B51E0;"></span>'
    '<span style="background:#1793D1;"></span>'
    '<span style="background:#B8BDC7;"></span>'
    "</div>"
    '<div class="t-ansi-row">'
    '<span style="background:#555B68;"></span>'
    '<span style="background:#E04040;"></span>'
    '<span style="background:#38D389;"></span>'
    '<span style="background:#F5C211;"></span>'
    '<span style="background:#5CA4FF;"></span>'
    '<span style="background:#C061CB;"></span>'
    '<span style="background:#2AC3DE;"></span>'
    '<span style="background:#F0F2F5;"></span>'
    "</div>"
    "</div>"
)

_GLOBAL_CSS = f"""
<style>
:root {{
    --t-bg: #1B1D1E;
    --t-pane: #202327;
    --t-pane-alt: #262A30;
    --t-border: #353B45;
    --t-border-hi: #1AC8E8;
    --t-fg: #E6E8EC;
    --t-soft: #B4BCC8;
    --t-muted: #7D8590;
    --t-cyan: #1AC8E8;
    --t-blue: #3584E4;
    --t-green: #38D389;
    --t-yellow: #F5C211;
    --t-red: #E04040;
    --t-purple: #C061CB;
    --t-silver: #C5C8CE;
    --t-slate: #2B303A;
    --t-mono: {_MONO_STACK};
}}

html, body, [class*="css"], .stApp {{
    font-family: var(--t-mono) !important;
    background-color: var(--t-bg) !important;
    color: var(--t-fg) !important;
}}

.block-container {{
    padding-top: 1.25rem !important;
    padding-bottom: 2.5rem !important;
    max-width: 1240px !important;
}}

/* Terminal Pane Borders */
div[data-testid="stVerticalBlockBorderWrapper"] {{
    border: 1px solid var(--t-border) !important;
    border-radius: 2px !important;
    background-color: var(--t-pane) !important;
}}

/* Inputs & Selects styled like terminal fields */
input, textarea, div[data-baseweb="select"] > div {{
    background-color: #16181A !important;
    border-color: var(--t-border) !important;
    color: var(--t-fg) !important;
    border-radius: 2px !important;
    font-family: var(--t-mono) !important;
}}

input:focus, textarea:focus {{
    border-color: var(--t-cyan) !important;
    box-shadow: 0 0 0 1px rgba(26, 200, 232, 0.35) !important;
}}

/* Hide Streamlit's overlapping "Press Enter to submit form" / "0/280" hint */
div[data-testid="InputInstructions"] {{
    display: none !important;
}}

/* Primary & Secondary Terminal Buttons */
button[kind="primary"] {{
    background-color: #1793D1 !important;
    color: #0E1113 !important;
    border: 1px solid #2AC3DE !important;
    border-radius: 2px !important;
    font-family: var(--t-mono) !important;
    font-weight: 700 !important;
}}

button[kind="primary"]:hover {{
    background-color: #2AC3DE !important;
    border-color: #6EE0F5 !important;
}}

button[kind="secondary"] {{
    background-color: #22262C !important;
    color: var(--t-fg) !important;
    border: 1px solid var(--t-border) !important;
    border-radius: 2px !important;
    font-family: var(--t-mono) !important;
    font-weight: 500 !important;
}}

button[kind="secondary"]:hover {{
    background-color: #2B3038 !important;
    border-color: var(--t-cyan) !important;
    color: var(--t-cyan) !important;
}}

/* Native st.chat_message styled as terminal cards (strictly contained inside column) */
div[data-testid="stChatMessage"] {{
    box-sizing: border-box !important;
    max-width: 100% !important;
    background-color: #20242A !important;
    border: 1px solid var(--t-border) !important;
    border-left: 3px solid var(--t-cyan) !important;
    border-radius: 2px !important;
    padding: 0.72rem 0.95rem !important;
    margin-bottom: 0.6rem !important;
    overflow-wrap: anywhere !important;
}}

div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {{
    background-color: #1A222E !important;
    border: 1px solid #2F496B !important;
    border-left: 3px solid var(--t-blue) !important;
    margin-left: 10% !important;
    margin-right: 0 !important;
    width: calc(100% - 10%) !important;
    max-width: calc(100% - 10%) !important;
}}

div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) {{
    margin-left: 0 !important;
    margin-right: 6% !important;
    width: calc(100% - 6%) !important;
    max-width: calc(100% - 6%) !important;
}}

/* Prevent any card/box from overflowing its column */
.t-p10k-bar, .t-combat-strip, .t-class-card, .t-engine-strip, .t-panel-bar, .t-attr-grid {{
    box-sizing: border-box;
    max-width: 100%;
    overflow-wrap: anywhere;
}}

/* Powerlevel10k Top Prompt Bar */
.t-p10k-bar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.5rem;
    padding: 0.35rem 0 0.75rem 0;
    border-bottom: 1px solid var(--t-border);
    margin-bottom: 1.15rem;
    font-family: var(--t-mono);
}}

.t-p10k-left, .t-p10k-right {{
    display: flex;
    align-items: center;
    flex-wrap: wrap;
}}

.t-seg {{
    display: inline-flex;
    align-items: center;
    height: 26px;
    padding: 0 0.75rem 0 0.9rem;
    font-size: 0.78rem;
    font-weight: 700;
    line-height: 1;
    white-space: nowrap;
}}

.t-seg-silver {{
    background: var(--t-silver);
    color: #16181A;
    padding-left: 0.65rem;
    padding-right: 1.05rem;
    clip-path: polygon(0 0, calc(100% - 10px) 0, 100% 50%, calc(100% - 10px) 100%, 0 100%);
}}

.t-seg-blue {{
    background: var(--t-blue);
    color: #FFFFFF;
    margin-left: -8px;
    padding-left: 1.15rem;
    padding-right: 1.05rem;
    clip-path: polygon(0 0, calc(100% - 10px) 0, 100% 50%, calc(100% - 10px) 100%, 0 100%, 10px 50%);
}}

.t-cmd-echo {{
    margin-left: 0.65rem;
    font-size: 0.82rem;
    color: var(--t-soft);
}}

.t-cursor {{
    display: inline-block;
    width: 8px;
    height: 14px;
    background: var(--t-fg);
    vertical-align: middle;
    margin-left: 0.35rem;
}}

.t-seg-status {{
    background: var(--t-slate);
    color: var(--t-green);
    padding-left: 1.05rem;
    padding-right: 0.9rem;
    clip-path: polygon(10px 0, 100% 0, calc(100% - 10px) 50%, 100% 100%, 10px 100%, 0 50%);
}}

.t-seg-status-fail {{
    color: var(--t-red);
}}

.t-seg-right-silver {{
    background: var(--t-silver);
    color: #16181A;
    margin-left: -8px;
    padding-left: 1.1rem;
    padding-right: 0.7rem;
    clip-path: polygon(10px 0, 100% 0, 100% 100%, 10px 100%, 0 50%);
}}

/* Setup Header & neofetch banner */
.t-setup-hero {{
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    flex-wrap: wrap;
    gap: 1rem;
    margin-bottom: 1rem;
}}

.t-eyebrow {{
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--t-cyan);
    font-weight: 700;
    margin-bottom: 0.2rem;
}}

.t-setup-title {{
    margin: 0;
    font-size: 1.55rem;
    font-weight: 700;
    color: var(--t-fg);
}}

.t-setup-sub {{
    margin: 0.2rem 0 0 0;
    font-size: 0.84rem;
    color: var(--t-muted);
}}

.t-section-head {{
    display: flex;
    align-items: center;
    gap: 0.45rem;
    padding-bottom: 0.55rem;
    margin-bottom: 0.75rem;
    border-bottom: 1px dashed var(--t-border);
    font-size: 0.88rem;
}}

.t-section-num {{
    color: var(--t-cyan);
    font-weight: 700;
}}

.t-section-title {{
    color: var(--t-fg);
    font-weight: 700;
}}

/* Class Cards (Page 7 wired to neofetch aesthetic) */
.t-class-card {{
    border: 1px solid var(--t-border);
    border-radius: 2px;
    padding: 0.75rem 0.8rem;
    background: #181B1E;
    height: 395px;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    transition: border-color 0.15s ease, background 0.15s ease;
}}

[class*="st-key-class_card_wrap_"] {{
    position: relative !important;
}}

[class*="st-key-class_card_wrap_"] > div:has(button) {{
    position: absolute !important;
    top: 0 !important;
    left: 0 !important;
    right: 0 !important;
    bottom: 0 !important;
    width: 100% !important;
    height: 100% !important;
    z-index: 20 !important;
    margin: 0 !important;
}}

[class*="st-key-class_card_wrap_"] div[data-testid="stButton"],
[class*="st-key-class_card_wrap_"] div[data-testid="stButton"] > button {{
    width: 100% !important;
    height: 100% !important;
    min-height: 395px !important;
    opacity: 0 !important;
    cursor: pointer !important;
    margin: 0 !important;
    padding: 0 !important;
}}

[class*="st-key-class_card_wrap_"]:hover .t-class-card {{
    border-color: var(--t-cyan) !important;
}}

.t-class-card-selected {{
    border: 1px solid var(--t-cyan);
    box-shadow: inset 0 0 0 1px rgba(26, 200, 232, 0.25);
    background: #1B2127;
}}

.t-class-top {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 0.4rem;
    margin-bottom: 0.55rem;
}}

.t-ascii-box {{
    border: 1px solid var(--t-border);
    background: #131517;
    padding: 0.35rem 0.45rem;
    color: var(--t-cyan);
    font-size: 0.64rem;
    line-height: 1.12;
    white-space: pre;
    font-weight: 700;
    overflow: hidden;
    height: 6.4rem;
    flex: 1 1 auto;
    min-width: 0;
    box-sizing: border-box;
    display: flex;
    align-items: center;
    justify-content: center;
}}

.t-radio-tag {{
    white-space: nowrap;
    flex-shrink: 0;
    line-height: 1.2;
}}

.t-ascii-sprite {{
    margin: 0;
    padding: 0;
    background: transparent;
    border: none;
    font-family: var(--t-mono);
    font-size: 0.74rem;
    line-height: 1.15;
    white-space: pre;
    font-weight: 700;
}}

/* ASCII Battle Arena (Dedicated Combat Screen) */
.t-arena-box {{
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    align-items: center;
    gap: 0.75rem;
    border: 1px solid var(--t-border);
    border-radius: 2px;
    background: radial-gradient(circle at 50% 45%, #1F242C 0%, #141619 75%);
    padding: 0.8rem 1rem;
    margin-bottom: 0.8rem;
    box-sizing: border-box;
    max-width: 100%;
}}

.t-arena-side {{
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.35rem;
}}

.t-arena-hero {{
    color: var(--t-cyan);
}}

.t-arena-enemy {{
    color: var(--t-red);
}}

.t-arena-caption {{
    font-size: 0.72rem;
    color: var(--t-soft);
    text-align: center;
    font-weight: 600;
}}

.t-arena-vs {{
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.25rem;
    padding: 0.35rem 0.7rem;
    border: 1px dashed var(--t-border);
    background: #181A1D;
    border-radius: 2px;
}}

.t-arena-vs-title {{
    font-size: 0.82rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    color: var(--t-yellow);
}}

.t-arena-vs-sub {{
    font-size: 0.68rem;
    color: var(--t-muted);
    text-transform: uppercase;
}}

.t-radio-tag {{
    font-size: 0.76rem;
    color: var(--t-muted);
    font-weight: 700;
}}

.t-radio-tag-active {{
    color: var(--t-green);
}}

/* Live pure-CSS :has() highlight for class cards inside st.form (zero reruns, zero JS) */
.t-dot-on {{
    display: none;
}}

.t-dot-off {{
    display: inline;
}}

div[data-testid="stForm"]:has(div[data-testid="stRadio"] input[value="0"]:checked) .t-class-card-0,
div[data-testid="stForm"]:has(div[data-testid="stRadio"] input[value="1"]:checked) .t-class-card-1,
div[data-testid="stForm"]:has(div[data-testid="stRadio"] input[value="2"]:checked) .t-class-card-2 {{
    border: 1px solid var(--t-cyan) !important;
    box-shadow: inset 0 0 0 1px rgba(26, 200, 232, 0.28) !important;
    background: #1B2127 !important;
}}

div[data-testid="stForm"]:has(div[data-testid="stRadio"] input[value="0"]:checked) .t-class-card-0 .t-dot-on,
div[data-testid="stForm"]:has(div[data-testid="stRadio"] input[value="1"]:checked) .t-class-card-1 .t-dot-on,
div[data-testid="stForm"]:has(div[data-testid="stRadio"] input[value="2"]:checked) .t-class-card-2 .t-dot-on {{
    display: inline !important;
}}

div[data-testid="stForm"]:has(div[data-testid="stRadio"] input[value="0"]:checked) .t-class-card-0 .t-dot-off,
div[data-testid="stForm"]:has(div[data-testid="stRadio"] input[value="1"]:checked) .t-class-card-1 .t-dot-off,
div[data-testid="stForm"]:has(div[data-testid="stRadio"] input[value="2"]:checked) .t-class-card-2 .t-dot-off {{
    display: none !important;
}}

.t-class-name {{
    font-size: 0.98rem;
    font-weight: 700;
    color: var(--t-fg);
    padding-bottom: 0.4rem;
    margin-bottom: 0.45rem;
    border-bottom: 1px dashed var(--t-border);
}}

.t-kv-row {{
    display: flex;
    justify-content: space-between;
    font-size: 0.78rem;
    padding: 0.2rem 0;
    border-bottom: 1px solid #262A30;
}}

.t-kv-key {{
    color: var(--t-cyan);
    font-weight: 700;
}}

.t-kv-val {{
    color: var(--t-fg);
    font-weight: 600;
}}

.t-abilities-foot {{
    margin-top: 0.5rem;
}}

.t-abilities-text {{
    font-size: 0.73rem;
    color: var(--t-soft);
    margin-top: 0.15rem;
}}

/* Chapter Divider & Stage Stepper (Page 8) */
.t-mini-stepper {{
    display: flex;
    gap: 0.35rem;
    margin-bottom: 0.7rem;
    flex-wrap: wrap;
}}

.t-mini-step {{
    font-size: 0.72rem;
    padding: 0.14rem 0.5rem;
    border: 1px solid var(--t-border);
    border-radius: 2px;
    color: var(--t-muted);
    background: #181A1D;
}}

.t-mini-step-done {{
    color: var(--t-green);
    border-color: rgba(56, 211, 137, 0.45);
    background: rgba(56, 211, 137, 0.08);
}}

.t-mini-step-active {{
    color: #0E1113;
    background: var(--t-cyan);
    border-color: var(--t-cyan);
    font-weight: 700;
}}

.t-chapter-divider {{
    display: flex;
    align-items: center;
    gap: 0.65rem;
    margin: 0.15rem 0 0.85rem 0;
    color: var(--t-muted);
    font-size: 0.74rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}}

.t-chapter-line {{
    flex: 1;
    height: 1px;
    background: var(--t-border);
}}

/* Combat Status Strip (Page 9: 3-column htop/TUI bar) */
.t-combat-strip {{
    display: grid;
    grid-template-columns: 1.55fr 0.75fr 1.35fr;
    border: 1px solid var(--t-border);
    border-top: 2px solid var(--t-red);
    border-radius: 2px;
    background: #181A1D;
    margin-bottom: 0.9rem;
}}

.t-combat-cell {{
    padding: 0.7rem 0.85rem;
}}

.t-combat-cell + .t-combat-cell {{
    border-left: 1px solid var(--t-border);
}}

.t-combat-center {{
    text-align: center;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    background: #20242A;
}}

.t-d20-num {{
    font-size: 1.85rem;
    font-weight: 800;
    line-height: 1.1;
    color: var(--t-cyan);
    margin: 0.1rem 0;
}}

.t-d20-status {{
    font-size: 0.74rem;
    font-weight: 700;
    text-transform: uppercase;
    color: var(--t-muted);
}}

.t-d20-hit {{
    color: var(--t-green);
}}

.t-d20-crit {{
    color: var(--t-yellow);
}}

.t-d20-miss {{
    color: var(--t-red);
}}

.t-bar-track {{
    width: 100%;
    height: 8px;
    background: #111315;
    border: 1px solid var(--t-border);
    border-radius: 1px;
    overflow: hidden;
    margin-top: 0.35rem;
}}

.t-bar-fill {{
    height: 100%;
    transition: width 0.2s ease;
}}

.t-round-head {{
    margin: 0.25rem 0 0.6rem 0;
}}

.t-round-title {{
    margin: 0.1rem 0 0 0;
    font-size: 1rem;
    font-weight: 700;
    color: var(--t-fg);
}}

/* Dashed Deterministic Engine Log Strip (Page 9) */
.t-engine-strip {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
    border: 1px dashed #444C58;
    border-radius: 2px;
    padding: 0.42rem 0.7rem;
    margin: 0.35rem 0 0.65rem 0;
    background: #16181A;
    font-size: 0.76rem;
    color: var(--t-soft);
}}

.t-engine-tag {{
    color: var(--t-yellow);
    font-weight: 700;
}}

.t-engine-detail {{
    color: var(--t-cyan);
    font-weight: 700;
}}

/* Right-Hand neofetch Character Sheet Panel (Pages 8 & 9) */
.t-sheet-header {{
    display: flex;
    align-items: center;
    gap: 0.7rem;
    padding-bottom: 0.7rem;
    border-bottom: 1px dashed var(--t-border);
    margin-bottom: 0.7rem;
}}

.t-sheet-user {{
    font-size: 0.98rem;
    font-weight: 700;
    color: var(--t-cyan);
    line-height: 1.2;
}}

.t-sheet-user span {{
    color: var(--t-fg);
}}

.t-sheet-rule {{
    font-size: 0.72rem;
    color: var(--t-muted);
    letter-spacing: 0.02em;
}}

.t-sheet-sub {{
    font-size: 0.76rem;
    color: var(--t-soft);
    margin-top: 0.12rem;
}}

.t-sheet-section {{
    padding-bottom: 0.65rem;
    margin-bottom: 0.65rem;
    border-bottom: 1px dashed var(--t-border);
}}

.t-hp-row {{
    display: flex;
    justify-content: space-between;
    font-size: 0.79rem;
}}

.t-attr-grid {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.4rem;
    margin-top: 0.45rem;
}}

.t-attr-cell {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border: 1px solid var(--t-border);
    border-radius: 2px;
    padding: 0.34rem 0.5rem;
    background: #181A1D;
    font-size: 0.78rem;
}}

.t-equip-line {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.25rem 0;
    font-size: 0.79rem;
}}

.t-buff-pill {{
    margin-top: 0.45rem;
    padding: 0.26rem 0.5rem;
    border: 1px solid var(--t-yellow);
    border-radius: 2px;
    background: rgba(245, 194, 17, 0.1);
    font-size: 0.73rem;
    font-weight: 700;
    color: var(--t-yellow);
}}

/* neofetch 16-Color ANSI Swatch Strip */
.t-ansi-bar {{
    display: inline-flex;
    flex-direction: column;
    margin: 0.35rem 0;
    border: 1px solid #2C313A;
}}

.t-ansi-row {{
    display: flex;
}}

.t-ansi-row span {{
    width: 22px;
    height: 11px;
    display: block;
}}

/* Campaign Conclusion Screen (Page 10) */
.t-conclusion-hero {{
    text-align: center;
    padding: 0.55rem 0 1rem 0;
    border-bottom: 1px dashed var(--t-border);
    margin-bottom: 1.1rem;
}}

.t-conclusion-title {{
    margin: 0.25rem 0 0.25rem 0;
    font-size: 1.7rem;
    font-weight: 700;
    color: var(--t-fg);
}}

.t-conclusion-sub {{
    margin: 0;
    font-size: 0.84rem;
    color: var(--t-muted);
}}

.t-panel-bar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.45rem 0.8rem;
    background: #16181A;
    border: 1px solid var(--t-border);
    border-radius: 2px;
    font-size: 0.73rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--t-cyan);
    font-weight: 700;
    margin-bottom: 0.55rem;
}}

@media (max-width: 768px) {{
    .t-combat-strip {{
        grid-template-columns: 1fr;
    }}
    .t-combat-cell + .t-combat-cell {{
        border-left: none;
        border-top: 1px solid var(--t-border);
    }}
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]),
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) {{
        margin-left: 0 !important;
        margin-right: 0 !important;
        width: 100% !important;
        max-width: 100% !important;
    }}
}}
</style>
"""


def _esc(value: Any) -> str:
    """Strictly HTML-escape any interpolated value."""
    return html.escape(str(value), quote=True)


def _clamp_int(value: Any, minimum: int = 0, maximum: int = 9999) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = minimum
    return max(minimum, min(maximum, parsed))


def _bar_pct(current: int, maximum: int) -> int:
    safe_max = _clamp_int(maximum, minimum=1)
    safe_cur = _clamp_int(current, minimum=0, maximum=safe_max)
    return int(round((safe_cur / safe_max) * 100))


def _hp_color(pct: int, is_enemy: bool = False) -> str:
    if is_enemy:
        return "#E04040"
    if pct > 55:
        return "#38D389"
    if pct > 25:
        return "#F5C211"
    return "#E04040"


def inject_global_styles() -> None:
    """Inject the Linux terminal stylesheet via ``st.html``."""
    st.html(_GLOBAL_CSS)


def render_top_bar(
    stage: str | None = None,
    current_turn: int | None = None,
    max_turns: int = 11,
    environment: str | None = None,
    outcome: str | None = None,
) -> None:
    """Render the segmented terminal top bar with clean WarDeN labels."""
    location_label = environment if stage and environment else "Campaign Setup"

    is_defeat = str(outcome or "").lower() == "defeat"
    status_glyph = "✗" if is_defeat else "✓"
    status_cls = "t-seg t-seg-status t-seg-status-fail" if is_defeat else "t-seg t-seg-status"

    if stage:
        turn_part = (
            f" · Turn {_clamp_int(current_turn, 1, max_turns)}/{_clamp_int(max_turns, 1)}"
            if current_turn is not None
            else ""
        )
        right_label = f"Stage: {stage}{turn_part}"
    else:
        right_label = "Ready"

    st.html(
        '<div class="t-p10k-bar">'
        '<div class="t-p10k-left">'
        '<span class="t-seg t-seg-silver">WarDeN</span>'
        f'<span class="t-seg t-seg-blue">{_esc(location_label)}</span>'
        "</div>"
        '<div class="t-p10k-right">'
        f'<span class="{status_cls}">{status_glyph}</span>'
        f'<span class="t-seg t-seg-right-silver">{_esc(right_label)}</span>'
        "</div>"
        "</div>"
    )


def render_setup_header() -> None:
    """Render the Campaign Setup header with terminal color swatch bar."""
    st.html(
        '<div class="t-setup-hero">'
        "<div>"
        '<div class="t-eyebrow">CAMPAIGN SETUP</div>'
        '<h1 class="t-setup-title">Create your adventure</h1>'
        '<p class="t-setup-sub">Define the world, then choose a character class.</p>'
        "</div>"
        f"<div>{_ANSI_PALETTE_HTML}</div>"
        "</div>"
    )


def render_section_header(number: str, title: str) -> None:
    """Render TUI pane headers like ``[01] Campaign details`` / ``[02] Choose a class``."""
    st.html(
        '<div class="t-section-head">'
        f'<span class="t-section-num">[{_esc(number)}]</span>'
        f'<span class="t-section-title">{_esc(title)}</span>'
        "</div>"
    )


def render_class_card(
    class_info: dict[str, Any],
    selected: bool = False,
    card_index: int = 0,
) -> None:
    """Render a vertical class selection card with ASCII crest & live CSS selection state."""
    raw_name = str(class_info.get("name", "Warrior"))
    name = _esc(raw_name)
    ascii_art = _esc(_CLASS_ASCII_EMBLEMS.get(raw_name, "  *\n /|\\\n  |"))
    max_hp = _clamp_int(class_info.get("max_hp", 10), minimum=1)
    attack = _clamp_int(class_info.get("attack", 1))
    defense = _clamp_int(class_info.get("defense", 1))
    magic = _clamp_int(class_info.get("magic", 1))
    speed = _clamp_int(class_info.get("speed", 4))
    safe_idx = _clamp_int(card_index, minimum=0, maximum=10)

    abilities_raw = class_info.get("abilities", [])
    ability_names = [
        str(ab.get("name", ab) if isinstance(ab, dict) else ab)
        for ab in abilities_raw
    ]
    abilities_line = _esc(" · ".join(ability_names)) if ability_names else "—"

    card_cls = (
        f"t-class-card t-class-card-{safe_idx} t-class-card-selected"
        if selected
        else f"t-class-card t-class-card-{safe_idx}"
    )
    if selected:
        radio_html = '<span class="t-radio-tag t-radio-tag-active">[●]</span>'
    else:
        radio_html = '<span class="t-radio-tag">[ ]</span>'

    st.html(
        f'<div class="{card_cls}">'
        '<div class="t-class-top">'
        f'<div class="t-ascii-box">{ascii_art}</div>'
        f"{radio_html}"
        "</div>"
        '<div class="t-eyebrow">CLASS</div>'
        f'<div class="t-class-name">{name}</div>'
        f'<div class="t-kv-row"><span class="t-kv-key">HP:</span><span class="t-kv-val">{max_hp}</span></div>'
        f'<div class="t-kv-row"><span class="t-kv-key">Attack:</span><span class="t-kv-val">{attack}</span></div>'
        f'<div class="t-kv-row"><span class="t-kv-key">Defense:</span><span class="t-kv-val">{defense}</span></div>'
        f'<div class="t-kv-row"><span class="t-kv-key">Magic:</span><span class="t-kv-val">{magic}</span></div>'
        f'<div class="t-kv-row"><span class="t-kv-key">Speed:</span><span class="t-kv-val">{speed}</span></div>'
        '<div class="t-abilities-foot" style="margin-top:auto;">'
        '<div class="t-eyebrow" style="margin-bottom:0.1rem;">ABILITIES</div>'
        f'<div class="t-abilities-text">{abilities_line}</div>'
        "</div>"
        "</div>"
    )


def render_stage_progress(
    current_stage: str,
    current_turn: int,
    max_turns: int = 11,
    chapter_title: str = "CHAPTER 01 · THE OLD ROAD",
) -> None:
    """Render the terminal stage pills + centered chapter rule."""
    try:
        active_idx = STAGE_ORDER.index(current_stage)
    except ValueError:
        active_idx = 0

    pills: list[str] = []
    for idx, stage_name in enumerate(STAGE_ORDER):
        if idx < active_idx:
            cls = "t-mini-step t-mini-step-done"
            prefix = "✓ "
        elif idx == active_idx:
            cls = "t-mini-step t-mini-step-active"
            prefix = "▸ "
        else:
            cls = "t-mini-step"
            prefix = "  "
        pills.append(f'<span class="{cls}">{prefix}{_esc(stage_name)}</span>')

    st.html(
        f'<div class="t-mini-stepper">{"".join(pills)}</div>'
        '<div class="t-chapter-divider">'
        '<span class="t-chapter-line"></span>'
        f"<span>[ {_esc(chapter_title)} ]</span>"
        '<span class="t-chapter-line"></span>'
        "</div>"
    )


def render_combat_header(
    enemy_name: str,
    enemy_hp: int,
    enemy_max_hp: int,
    player_hp: int,
    player_max_hp: int,
    last_roll: dict[str, Any] | None = None,
    combat_round: int = 1,
) -> None:
    """Render the 3-column Combat TUI Strip (Enemy | D20 Result | Your Health)."""
    e_cur = _clamp_int(enemy_hp, 0, max(1, enemy_max_hp))
    e_max = _clamp_int(enemy_max_hp, 1)
    e_pct = _bar_pct(e_cur, e_max)

    p_cur = _clamp_int(player_hp, 0, max(1, player_max_hp))
    p_max = _clamp_int(player_max_hp, 1)
    p_pct = _bar_pct(p_cur, p_max)
    p_color = _hp_color(p_pct, is_enemy=False)

    if last_roll:
        d20 = _clamp_int(last_roll.get("d20_roll", 0), 0, 20)
        outcome = str(last_roll.get("outcome", "Miss"))
        if "Crit" in outcome:
            status_label = "CRITICAL"
            status_cls = "t-d20-status t-d20-crit"
        elif outcome == "Hit":
            status_label = "SUCCESS"
            status_cls = "t-d20-status t-d20-hit"
        else:
            status_label = "MISS"
            status_cls = "t-d20-status t-d20-miss"
        d20_display = str(d20)
    else:
        d20_display = "--"
        status_label = "READY"
        status_cls = "t-d20-status"

    round_num = _clamp_int(combat_round, 1, 99)

    st.html(
        '<div class="t-combat-strip">'
        # Column 1: Enemy
        '<div class="t-combat-cell">'
        '<div class="t-eyebrow" style="color:#E04040;">ENEMY</div>'
        f'<div style="font-size:1.02rem;font-weight:700;color:#E6E8EC;">{_esc(enemy_name)}</div>'
        f'<div style="font-size:0.78rem;color:#B4BCC8;margin-top:0.15rem;">{e_cur} / {e_max} HP</div>'
        f'<div class="t-bar-track"><div class="t-bar-fill" style="width:{e_pct}%;background:#E04040;"></div></div>'
        "</div>"
        # Column 2: D20 Result
        '<div class="t-combat-cell t-combat-center">'
        '<div class="t-eyebrow">D20 RESULT</div>'
        f'<div class="t-d20-num">{_esc(d20_display)}</div>'
        f'<div class="{status_cls}">{_esc(status_label)}</div>'
        "</div>"
        # Column 3: Your Health
        '<div class="t-combat-cell">'
        '<div class="t-eyebrow" style="color:#38D389;">YOUR HEALTH</div>'
        f'<div style="font-size:1.02rem;font-weight:700;color:#E6E8EC;">{p_cur} / {p_max} HP</div>'
        '<div style="font-size:0.76rem;color:#7D8590;margin-top:0.15rem;">Current HP</div>'
        f'<div class="t-bar-track"><div class="t-bar-fill" style="width:{p_pct}%;background:{p_color};"></div></div>'
        "</div>"
        "</div>"
        '<div class="t-round-head">'
        f'<div class="t-eyebrow">ROUND {round_num:02d}</div>'
        '<h3 class="t-round-title">Combat narration</h3>'
        "</div>"
    )


def render_combat_arena(
    player_name: str,
    player_class: str,
    enemy_name: str,
    enemy_title: str = "",
    combat_round: int = 1,
    last_roll: dict[str, Any] | None = None,
) -> None:
    """Render side-by-side ASCII art character vs. enemy battle visual on the Combat Screen."""
    hero_art = _esc(_CLASS_ASCII_EMBLEMS.get(player_class, _CLASS_ASCII_EMBLEMS["Warrior"]))
    enemy_art = _esc(_ENEMY_ASCII_SPRITES.get(enemy_name, _ENEMY_ASCII_SPRITES["Hollow Guard"]))
    round_num = _clamp_int(combat_round, 1, 99)

    if last_roll:
        outcome = str(last_roll.get("outcome", "Miss"))
        dmg = _clamp_int(last_roll.get("damage", 0), 0)
        clash_sub = f"{outcome} · -{dmg} HP" if dmg > 0 else outcome
    else:
        clash_sub = f"Round {round_num:02d}"

    enemy_sub = f"{enemy_name} ({enemy_title})" if enemy_title else enemy_name

    st.html(
        '<div class="t-arena-box">'
        '<div class="t-arena-side">'
        f'<pre class="t-ascii-sprite t-arena-hero">{hero_art}</pre>'
        f'<div class="t-arena-caption">{_esc(player_name)} · {_esc(player_class)}</div>'
        "</div>"
        '<div class="t-arena-vs">'
        '<div class="t-arena-vs-title">VS</div>'
        f'<div class="t-arena-vs-sub">{_esc(clash_sub)}</div>'
        "</div>"
        '<div class="t-arena-side">'
        f'<pre class="t-ascii-sprite t-arena-enemy">{enemy_art}</pre>'
        f'<div class="t-arena-caption">{_esc(enemy_sub)}</div>'
        "</div>"
        "</div>"
    )


def render_engine_roll_strip(
    label: str,
    roll_detail: str,
    outcome_text: str,
) -> None:
    """Render deterministic engine roll check line BEFORE narration."""
    st.html(
        '<div class="t-engine-strip">'
        f"<span>{_esc(label)}</span>"
        f'<span><span class="t-engine-detail">{_esc(roll_detail)}</span> · {_esc(outcome_text)}</span>'
        "</div>"
    )


def render_character_sheet_header(
    name: str,
    char_class: str,
    current_hp: int,
    max_hp: int,
    attack: int,
    defense: int,
    magic: int,
    speed: int,
    active_buff: str = "",
) -> None:
    """Render terminal-styled right-panel Character Sheet header, HP bar, and 2x2 Attributes."""
    cur = _clamp_int(current_hp, 0, max(1, max_hp))
    mx = _clamp_int(max_hp, 1)
    pct = _bar_pct(cur, mx)
    bar_col = _hp_color(pct, is_enemy=False)
    ascii_art = _esc(_CLASS_ASCII_COMPACT.get(char_class, "  *\n /|\\\n  |"))
    display_name = _esc(name.strip() or "Rowan")

    buff_html = (
        f'<div class="t-buff-pill">Active Boon: {_esc(active_buff)}</div>'
        if active_buff
        else ""
    )

    st.html(
        '<div class="t-sheet-header">'
        f'<div class="t-ascii-box">{ascii_art}</div>'
        "<div>"
        '<div class="t-eyebrow" style="margin-bottom:0.1rem;">CHARACTER SHEET</div>'
        f'<div class="t-sheet-user">{display_name}</div>'
        '<div class="t-sheet-rule">-----------------</div>'
        f'<div class="t-sheet-sub"><span class="t-kv-key">Class:</span> Level 1 {_esc(char_class)}</div>'
        "</div>"
        "</div>"
        '<div class="t-sheet-section">'
        '<div class="t-hp-row">'
        '<span class="t-kv-key">Health:</span>'
        f'<span class="t-kv-val">{cur} / {mx} HP</span>'
        "</div>"
        f'<div class="t-bar-track"><div class="t-bar-fill" style="width:{pct}%;background:{bar_col};"></div></div>'
        "</div>"
        '<div class="t-sheet-section">'
        '<div class="t-eyebrow">ATTRIBUTES</div>'
        '<div class="t-attr-grid">'
        f'<div class="t-attr-cell"><span class="t-kv-key">Attack:</span><span class="t-kv-val">{_clamp_int(attack)}</span></div>'
        f'<div class="t-attr-cell"><span class="t-kv-key">Defense:</span><span class="t-kv-val">{_clamp_int(defense)}</span></div>'
        f'<div class="t-attr-cell"><span class="t-kv-key">Magic:</span><span class="t-kv-val">{_clamp_int(magic)}</span></div>'
        f'<div class="t-attr-cell"><span class="t-kv-key">Speed:</span><span class="t-kv-val">{_clamp_int(speed)}</span></div>'
        "</div>"
        f"{buff_html}"
        "</div>"
    )


def render_equipment_card(weapon: str, armor: str, accessory: str) -> None:
    """Render neofetch-style Equipment key/value section."""
    st.html(
        '<div class="t-sheet-section">'
        '<div class="t-eyebrow" style="margin-bottom:0.3rem;">EQUIPMENT</div>'
        '<div class="t-equip-line">'
        '<span class="t-kv-key">Weapon:</span>'
        f'<span class="t-kv-val">{_esc(weapon or "Empty")}</span>'
        "</div>"
        '<div class="t-equip-line">'
        '<span class="t-kv-key">Armor:</span>'
        f'<span class="t-kv-val">{_esc(armor or "Empty")}</span>'
        "</div>"
        '<div class="t-equip-line">'
        '<span class="t-kv-key">Accessory:</span>'
        f'<span class="t-kv-val">{_esc(accessory or "Empty")}</span>'
        "</div>"
        "</div>"
    )


def render_ansi_swatches() -> None:
    """Render the signature neofetch 16-color ANSI palette bar."""
    st.html(f'<div style="margin:0.45rem 0 0.2rem 0;">{_ANSI_PALETTE_HTML}</div>')


def render_conclusion_banner(
    campaign_title: str,
    outcome: str,
    character_name: str,
    char_class: str,
    turns_taken: int,
    environment: str,
) -> None:
    """Render the centered Campaign Conclusion header."""
    is_victory = str(outcome).lower() == "victory"
    status_color = "#38D389" if is_victory else "#E04040"
    eyebrow = "CAMPAIGN COMPLETE · VICTORY" if is_victory else "CAMPAIGN COMPLETE · DEFEAT"
    subtitle = (
        f"Your adventure has reached its end · {character_name} ({char_class}) · "
        f"{environment} · {_clamp_int(turns_taken, 1, 11)} turns"
    )

    hero_art = _esc(_CLASS_ASCII_EMBLEMS.get(char_class, _CLASS_ASCII_EMBLEMS["Warrior"]))
    art_color = "#1AC8E8" if is_victory else "#7D8590"

    st.html(
        '<div class="t-conclusion-hero">'
        f'<div style="display:flex;justify-content:center;margin-bottom:0.55rem;"><pre class="t-ascii-sprite" style="color:{art_color};">{hero_art}</pre></div>'
        f'<div class="t-eyebrow" style="color:{status_color};">{_esc(eyebrow)}</div>'
        f'<h1 class="t-conclusion-title">{_esc(campaign_title)}</h1>'
        f'<p class="t-conclusion-sub">{_esc(subtitle)}</p>'
        f'<div style="margin-top:0.65rem;">{_ANSI_PALETTE_HTML}</div>'
        "</div>"
    )


def render_panel_bar(left_label: str, right_label: str = "") -> None:
    """Render a terminal header bar for Conclusion panels."""
    st.html(
        '<div class="t-panel-bar">'
        f"<span>{_esc(left_label)}</span>"
        f"<span>{_esc(right_label)}</span>"
        "</div>"
    )
