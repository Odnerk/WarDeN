import random
from llama_index.llms.ollama import Ollama

llm = Ollama(model="llama3", request_timeout=360.0)

# ---------- GAME DATA (the engine owns all numbers) ----------
CLASSES = {
    "Warrior": {"hp": 30, "attack": 4, "defense": 4, "weapon": "sword"},
    "Archer":  {"hp": 24, "attack": 5, "defense": 2, "weapon": "bow"},
    "Mage":    {"hp": 20, "attack": 6, "defense": 1, "weapon": "staff"},
}
ENEMIES = {
    "Goblin":   {"hp": 12, "damage": (2, 5), "defense": 10},
    "Wolf":     {"hp": 14, "damage": (3, 6), "defense": 11},
    "Skeleton": {"hp": 16, "damage": (3, 7), "defense": 12},
}
ENVIRONMENTS = ["Forest", "Mountains", "Swamp", "Cave", "Desert", "Snowfield"]

# ---------- THE AI DUNGEON MASTER ----------
def narrate(state, instruction):
    prompt = (
        "You are a fantasy Dungeon Master. Write 2-3 vivid sentences. "
        "Never invent stats, HP or dice results. Only describe the facts given.\n"
        f"Player: a {state['class']} in a {state['environment']}.\n"
        f"Story so far: {' '.join(state['log'][-3:])}\n"
        f"Narrate this: {instruction}"
    )
    text = str(llm.complete(prompt)).strip()
    state["log"].append(text)
    print("\nDM:", text, "\n")

# ---------- THE GAME ENGINE ----------
def combat(state, enemy_name):
    enemy = dict(ENEMIES[enemy_name])
    narrate(state, f"A {enemy_name} appears and attacks the player.")
    while enemy["hp"] > 0 and state["hp"] > 0:
        input("[Press Enter to attack]")
        roll = random.randint(1, 20)
        if roll + state["attack"] >= enemy["defense"]:
            dmg = random.randint(3, 8)
            enemy["hp"] -= dmg
            result = f"The player rolled {roll} and hit the {enemy_name} for {dmg} damage."
        else:
            result = f"The player rolled {roll} and missed the {enemy_name}."
        print(f"[ENGINE] {result}  Enemy HP: {max(enemy['hp'], 0)}")

        if enemy["hp"] > 0:
            eroll = random.randint(1, 20)
            if eroll + 3 >= 10 + state["defense"]:
                edmg = random.randint(*enemy["damage"])
                state["hp"] -= edmg
                result += f" The {enemy_name} hit back for {edmg} damage."
            else:
                result += f" The {enemy_name} attacked but missed."
            print(f"[ENGINE] Your HP: {max(state['hp'], 0)}")
        narrate(state, result)
    return state["hp"] > 0

def main():
    cls = input(f"Choose a class {list(CLASSES)}: ").strip().title()
    while cls not in CLASSES:
        cls = input("Pick Warrior, Archer, or Mage: ").strip().title()
    env = input(f"Choose a setting {ENVIRONMENTS}: ").strip().title()
    while env not in ENVIRONMENTS:
        env = input("Pick one from the list: ").strip().title()

    state = {"class": cls, "environment": env, "log": [], **CLASSES[cls]}

    # Stage 1: Introduction
    narrate(state, "Introduce the start of a short adventure and give the player a quest.")
    # Stage 2: Exploration (free text)
    for _ in range(2):
        action = input("What do you do? ")
        narrate(state, f"The player does this: '{action}'. Describe what they find. No combat yet.")
    # Stage 3: Main encounter
    won = combat(state, random.choice(list(ENEMIES)))
    # Stage 4: Conclusion
    if won:
        narrate(state, "The player won the fight. Write a satisfying ending to the adventure.")
    else:
        narrate(state, "The player was defeated. Write a sad ending to the adventure.")
    print("THE END")

main()