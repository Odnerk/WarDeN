# WarDeN

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.x-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2-E92063?style=for-the-badge&logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![OpenAI SDK](https://img.shields.io/badge/OpenAI_SDK-Luna_6-412991?style=for-the-badge&logo=openai&logoColor=white)](https://platform.openai.com/docs/libraries)
[![python-statemachine](https://img.shields.io/badge/python--statemachine-FSM-1A7F37?style=for-the-badge)](https://python-statemachine.readthedocs.io/)
[![pytest](https://img.shields.io/badge/pytest-tested-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)](https://docs.pytest.org/)

**WarDeN** is a pure-Python, single-player fantasy tabletop RPG chatbot powered by **Luna 6** (`gpt-6-luna`) and **Streamlit**. A deterministic Python game engine owns all HP, stats, D20 dice rolls, inventory, enemy data, and the 4-stage campaign state machine (`Introduction -> Exploration -> Main Encounter -> Conclusion`), while the AI Dungeon Master handles vivid storytelling, NPC dialogue, and intent interpretation behind a 4-layer security pipeline.

## Team: Downeys

| Member | GitHub |
|---|---|
| Samuel Carillo | [@flurgerburger](https://github.com/flurgerburger) |
| Gabriel Elorde | [@maidenator](https://github.com/maidenator) |
| Kristian Enrico Ortiz | [@Odnerk](https://github.com/Odnerk) |
| John Erick Santizo | [@eitophetamine9](https://github.com/eitophetamine9) |

## Features

- **Campaign Setup & Class Selection:** Configure premise, adventure direction, difficulty, fantasy environment (8 presets), and choose **Warrior**, **Archer**, or **Mage**.
- **Deterministic Rules Engine:** Server-side D20 checks, combat damage, enemy encounters, consumable healing, and 6-to-11-turn pacing enforced by `python-statemachine`.
- **Luna 6 AI Dungeon Master:** Generates campaign openings, interprets free-text actions, voices story NPCs, and narrates outcomes in strict JSON validated against Pydantic v2 schemas.
- **4-Layer Security Pipeline:**
  1. Input sanitization (280-char cap, delimiter stripping, regex jailbreak/tampering blocklist)
  2. Sandwich Defense prompt hardening with `<untrusted_player_input>` XML isolation
  3. Strict Pydantic v2 `DMResponse` and authoritative `campaign_stage` validation
  4. Case-insensitive output leak filter with 1 controlled retry and fail-closed fallback
- **Save & Resume:** Export and reload full `CampaignState` JSON files.

## Project Structure

```text
WarDeN/
├── app.py                  # Main Streamlit entrypoint and screen router
├── requirements.txt        # Python dependencies
├── data/
│   ├── classes.json        # Warrior, Archer, and Mage presets
│   ├── enemies.json        # Predefined fantasy enemies
│   ├── environments.json   # 8 fantasy environment presets
│   └── items.json          # Weapons, armor, accessories, consumables
├── src/
│   ├── models.py           # Pydantic v2 domain models & DMResponse schema
│   ├── engine.py           # Deterministic D20 combat, exploration, and items
│   ├── fsm.py              # 4-stage campaign finite state machine
│   ├── storage.py          # JSON save/load persistence
│   ├── prompts.py          # Modular prompts & Sandwich Defense builder
│   ├── security.py         # 4-layer input/output defense pipeline
│   └── dm_client.py        # Cached OpenAI SDK client for Luna 6
├── ui/
│   ├── backend.py          # Adapter wiring Streamlit UI to engine & DM client
│   ├── setup_view.py       # Campaign setup & class selection view
│   ├── chat_view.py        # Exploration, combat, and conclusion views
│   ├── sidebar_sheet.py    # Character sheet, consumables, and save/resume
│   └── styles.py           # Terminal-inspired CSS & component renderers
└── tests/
    ├── test_engine.py      # Deterministic engine, FSM, and storage tests
    └── test_dm_mock.py     # Security pipeline tests & optional Luna 6 smoke test
```

## Setup & Installation

1. **Clone and switch to `dev`:**
   ```bash
   git clone https://github.com/Odnerk/WarDeN.git
   cd WarDeN
   git checkout dev
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure your Luna 6 API key:**
   Create `.streamlit/secrets.toml` (git-ignored):
   ```toml
   LUNA_API_KEY = "your-luna-api-key"
   ```
   Alternatively, export `LUNA_API_KEY` as an environment variable.

## Running the App & Tests

Start the Streamlit web application:
```bash
streamlit run app.py
```

Run the test suite:
```bash
pytest -v
```
