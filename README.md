# 🎲 AI Dungeon Master

A terminal-based fantasy RPG driven by a **local LLM** (via [Ollama](https://ollama.ai/) + [LlamaIndex](https://www.llamaindex.ai/)). The AI acts as a Dungeon Master — narrating the story, reacting to your actions, and describing combat outcomes — while a deterministic Python engine handles all dice rolls, HP, and game logic.

## Features

- Choose your class: **Warrior**, **Archer**, or **Mage**
- Choose your environment: Forest, Mountains, Swamp, Cave, Desert, or Snowfield
- 2-3 turns of free exploration before the main encounter
- Turn-based combat with D20 rolls against random enemies
- Fully local — no internet connection required at runtime

## Project Structure

```
AIDungeonMaster/
├── dm.py           # Main game loop + AI narration engine
├── main.py         # LlamaIndex RAG demo (index + query over ./data)
├── data/
│   └── sample.txt  # Sample document for the RAG pipeline
├── requirements.txt
├── .gitignore
└── README.md
```

## Requirements

- Python 3.10+
- [Ollama](https://ollama.ai/) running locally with `llama3` pulled:
  ```bash
  ollama pull llama3
  ```

## Installation

```bash
git clone https://github.com/Odnerk/AIDungeonMaster.git
cd AIDungeonMaster
pip install -r requirements.txt
```

## Usage

### Play the AI Dungeon Master game

```bash
python dm.py
```

Follow the prompts to pick a class and environment. Press **Enter** each turn to roll and attack during combat.

### Run the LlamaIndex RAG demo

```bash
python main.py
```

Indexes all files in `./data/` using a local HuggingFace embedding model and answers a sample query through Ollama.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                      dm.py                          │
│                                                     │
│  ┌──────────────┐        ┌──────────────────────┐   │
│  │  Game Engine │        │   AI Dungeon Master  │   │
│  │  (Python)    │───────▶│   narrate()          │   │
│  │              │        │   Ollama / llama3    │   │
│  │  dice rolls  │        │   2-3 vivid sentences│   │
│  │  HP tracking │        │   per game event     │   │
│  │  combat loop │        └──────────────────────┘   │
│  └──────────────┘                                   │
└─────────────────────────────────────────────────────┘
```

The engine **never** passes raw numbers to the LLM for computation — it always sends a plain-English description of the event and asks for narrative only.

## Configuration

| Variable | Location | Default | Description |
|---|---|---|---|
| `model` | `dm.py:4` | `llama3` | Ollama model name |
| `request_timeout` | `dm.py:4` | `360.0 s` | LLM timeout |
| `embed_model` | `main.py:7` | `BAAI/bge-small-en-v1.5` | HuggingFace embedding model |

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Commit with [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `chore:`
4. Open a pull request

## License

MIT
