import json
from datetime import datetime, timezone
from pathlib import Path

from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from models import AccountData, Briefing

PROMPTS_DIR = Path(__file__).parent / "prompts"
DATA_DIR = Path(__file__).parent / "data"
OUTPUTS_DIR = Path(__file__).parent / "outputs"
DEBUG_DIR = Path(__file__).parent / "debug"

STATUS_EMOJI = {
    "Healthy": "🟢",
    "At-Risk": "🟡",
    "Stalled": "🔴",
}


def load_data(state: dict) -> dict:
    account_name = state["account_name"]
    data_path = DATA_DIR / f"{account_name}.json"
    if not data_path.exists():
        raise FileNotFoundError(
            f"No data file for account '{account_name}' at {data_path}"
        )
    raw = json.loads(data_path.read_text())

    try:
        AccountData.model_validate(raw)
    except ValidationError as e:
        raise ValueError(
            f"{data_path} doesn't match the expected account data shape:\n{e}"
        ) from e

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return {"account_data": raw, "generated_at": generated_at}


def generate_briefing(state: dict) -> dict:
    system_prompt = (PROMPTS_DIR / "briefing_prompt.md").read_text()
    account_json = json.dumps(state["account_data"], indent=2)

    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    structured_llm = llm.with_structured_output(Briefing, include_raw=True)

    result = structured_llm.invoke(
        [
            ("system", system_prompt),
            ("user", account_json),
        ]
    )

    briefing: Briefing = result["parsed"]
    raw_response = result["raw"].content

    return {"briefing": briefing, "raw_response": raw_response}


def validate_output(state: dict) -> dict:
    briefing: Briefing = state["briefing"]
    if briefing is None:
        raise ValueError("LLM did not return a briefing that matched the schema.")

    warnings = []
    for signal in briefing.why:
        if "(" not in signal or ")" not in signal:
            warnings.append(f"Signal missing a parenthetical citation: '{signal}'")

    if warnings:
        print("⚠️  Validation warnings:")
        for w in warnings:
            print(f"   - {w}")

    return {}


def save_and_display(state: dict) -> dict:
    briefing: Briefing = state["briefing"]
    account_name = state["account_name"]
    emoji = STATUS_EMOJI.get(briefing.status.value, "")
    timestamp = state.get("generated_at", "")

    why_lines = "\n".join(f"- {item}" for item in briefing.why)
    who_lines = "\n".join(f"- {item}" for item in briefing.who_to_talk_to)
    actions_lines = "\n".join(
        f"{i}. {item}" for i, item in enumerate(briefing.next_actions, start=1)
    )

    markdown = f"""# Pre-Call Briefing: {state["account_data"]["account_name"]}

**Generated:** {timestamp}

---

## {emoji} Status: {briefing.status.value}

**Snapshot:** {briefing.snapshot}

### Why
{why_lines}

### Who to Talk To
{who_lines}

### Next Actions
{actions_lines}

### ⚠️ One Thing to Watch
{briefing.one_thing_to_watch}
"""

    OUTPUTS_DIR.mkdir(exist_ok=True)
    output_path = OUTPUTS_DIR / f"{account_name}_briefing.md"
    output_path.write_text(markdown)

    DEBUG_DIR.mkdir(exist_ok=True)
    reasoning_path = DEBUG_DIR / f"{account_name}_reasoning.md"
    reasoning_path.write_text(
        f"# Reasoning trace: {state['account_data']['account_name']}\n\n"
        f"**Generated:** {timestamp}\n\n"
        f"Internal only — not shown to the account manager. Kept for debugging "
        f"a wrong classification or a weird output.\n\n---\n\n{briefing.reasoning}\n"
    )

    print(markdown)
    print(f"\nSaved to {output_path}")
    print(f"Reasoning saved to {reasoning_path}")

    return {"output_path": str(output_path)}
