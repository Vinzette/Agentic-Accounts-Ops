# FieldAssist Agentic Accounts Ops — Pre-Call Briefing Agent

Reads a FieldAssist account's raw data and produces a short pre-call briefing for the account manager: status, snapshot, why, who to talk to, next actions, and one thing to watch.

## Setup

```bash
uv sync
cp .env.example .env   # then fill in OPENAI_API_KEY
```

## Run

```bash
uv run python main.py --account nimbus
uv run python main.py --account corner_beverages zephyr   # one or more accounts in a single run
```

Each run prints the briefing to the console and saves it to `outputs/{account}_briefing.md`. Pre-generated outputs for all three accounts are already committed in `outputs/`.

## How it works

`main.py` runs a 4-node LangGraph `StateGraph`: `load_data` → `generate_briefing` → `validate_output` → `save_and_display`. Only `generate_briefing` calls an LLM (GPT-4o via structured output bound to the `Briefing` Pydantic model in `models.py`); the other three nodes are plain data plumbing. The system prompt — including the classification rubric and citation rule — lives in `prompts/briefing_prompt.md`, separate from the code. `--account` accepts multiple names and loops the same compiled graph per account sequentially.

## Project structure

```
main.py       # CLI entry point
graph.py      # LangGraph StateGraph definition
nodes.py      # Node functions (load, generate, validate, save)
models.py     # Pydantic models (Briefing, AccountStatus)
prompts/      # System prompt (rubric + output template)
data/         # Mock account JSON
outputs/      # Generated briefings
```
