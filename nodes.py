"""The briefing pipeline's node functions.

Each node takes the running state and returns only the keys it changed;
LangGraph merges the result. `graph.py` wires them together — including the
cycle from `validate_output` back to `generate_briefing`.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from models import AccountData, Briefing
from validation import check_briefing

PROMPTS_DIR = Path(__file__).parent / "prompts"
DATA_DIR = Path(__file__).parent / "data"
OUTPUTS_DIR = Path(__file__).parent / "outputs"
DEBUG_DIR = Path(__file__).parent / "debug"

MODEL = "gpt-5.1"

# How many times the model may generate before we ship what it produced. A
# model that fails grounding twice rarely fixes itself on a third pass, and a
# briefing carrying a visible warning beats a request that never terminates.
MAX_ATTEMPTS = 2

STATUS_EMOJI = {
    "Healthy": "🟢",
    "At-Risk": "🟡",
    "Stalled": "🔴",
}


def load_data(state: dict) -> dict:
    """Resolve the account data and validate it before anything is spent on it.

    The CLI names an account and we read it off disk; the web app hands the
    edited data in directly. Validation sits outside that branch so both entry
    points get the identical guard, and both get it before the API call.
    """
    raw = state.get("account_data")
    source = "The account data"

    if raw is None:
        account_name = state["account_name"]
        data_path = DATA_DIR / f"{account_name}.json"
        if not data_path.exists():
            raise FileNotFoundError(f"No data file for account '{account_name}' at {data_path}")
        raw = json.loads(data_path.read_text())
        source = str(data_path)

    try:
        account = AccountData.model_validate(raw)
    except ValidationError as e:
        raise ValueError(f"{source} doesn't match the expected account data shape:\n{e}") from e

    return {
        # Store the model-facing form, so what we later check citations against
        # is exactly what the model was shown.
        "account_data": account.for_prompt(),
        "missing_fields": account.missing_fields(),
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
    }


def generate_briefing(state: dict) -> dict:
    """Call the model. On a retry, tell it exactly what failed last time."""
    system_prompt = (PROMPTS_DIR / "briefing_prompt.md").read_text()
    messages = [
        ("system", system_prompt),
        ("user", json.dumps(state["account_data"], indent=2)),
    ]

    previous_errors = state.get("validation_errors") or []
    if previous_errors:
        messages.append(("user", _correction_request(previous_errors)))

    llm = ChatOpenAI(model=MODEL, temperature=0)
    result = llm.with_structured_output(Briefing, include_raw=True).invoke(messages)

    return {
        "briefing": result["parsed"],
        "raw_response": result["raw"].content,
        "attempts": state.get("attempts", 0) + 1,
    }


def _correction_request(errors: list[str]) -> str:
    """The follow-up turn that drives a regeneration."""
    listed = "\n".join(f"- {error}" for error in errors)
    return (
        "Your previous briefing failed validation on these points:\n\n"
        f"{listed}\n\n"
        "Every figure inside a parenthetical citation must appear in the account data "
        "above, quoted or closely paraphrased. Fix these specific problems and return "
        "the complete briefing again — all fields, not only the corrected ones."
    )


def validate_output(state: dict) -> dict:
    """Check the briefing against its source data.

    Returns the verdict rather than acting on it — `graph.route_after_validation`
    decides whether that means regenerating or shipping.
    """
    briefing: Briefing | None = state["briefing"]
    if briefing is None:
        raise ValueError("The model did not return a briefing matching the schema.")

    errors, warnings = check_briefing(briefing, state["account_data"])
    return {
        "validation_passed": not errors,
        "validation_errors": errors,
        "validation_warnings": warnings,
    }


def save_briefing(state: dict) -> dict:
    """Write the briefing and its reasoning trace to disk."""
    account_name = state["account_name"]
    markdown = render_markdown(state)

    OUTPUTS_DIR.mkdir(exist_ok=True)
    output_path = OUTPUTS_DIR / f"{account_name}_briefing.md"
    output_path.write_text(markdown)

    DEBUG_DIR.mkdir(exist_ok=True)
    reasoning_path = DEBUG_DIR / f"{account_name}_reasoning.md"
    reasoning_path.write_text(_render_reasoning(state))

    return {"markdown": markdown, "output_path": str(output_path)}


def render_markdown(state: dict) -> str:
    """Render the account-manager-facing briefing. Shared with the web API's download."""
    briefing: Briefing = state["briefing"]
    emoji = STATUS_EMOJI.get(briefing.status.value, "")

    why_lines = "\n".join(f"- {item}" for item in briefing.why)
    who_lines = "\n".join(f"- {item}" for item in briefing.who_to_talk_to)
    action_lines = "\n".join(
        f"{i}. {item}" for i, item in enumerate(briefing.next_actions, start=1)
    )

    markdown = f"""# Pre-Call Briefing: {state["account_data"]["account_name"]}

**Generated:** {state.get("generated_at", "")}

---

## {emoji} Status: {briefing.status.value}

**Snapshot:** {briefing.snapshot}

### Why
{why_lines}

### Who to Talk To
{who_lines}

### Next Actions
{action_lines}

### ⚠️ One Thing to Watch
{briefing.one_thing_to_watch}
"""
    caveats = _render_caveats(state)
    return markdown + caveats if caveats else markdown


def _render_caveats(state: dict) -> str:
    """Anything the reader should know about how far to trust this briefing.

    Absent entirely when there's nothing to say, so a clean briefing stays clean.
    """
    sections: list[str] = []

    if missing := state.get("missing_fields"):
        sections.append(
            "**Built from partial data.** No record of: " + ", ".join(missing).replace("_", " ")
        )

    if errors := state.get("validation_errors"):
        listed = "\n".join(f"- {error}" for error in errors)
        sections.append(
            f"**⚠️ Unverified signals.** These citations could not be matched against "
            f"the account data, and the model did not correct them within "
            f"{MAX_ATTEMPTS} attempts:\n{listed}"
        )

    if warnings := state.get("validation_warnings"):
        listed = "\n".join(f"- {warning}" for warning in warnings)
        sections.append(f"**Worth a second look.**\n{listed}")

    if not sections:
        return ""
    return "\n---\n\n### Checks\n\n" + "\n\n".join(sections) + "\n"


def _render_reasoning(state: dict) -> str:
    """The internal trace — kept out of the briefing the account manager reads."""
    briefing: Briefing = state["briefing"]
    attempts = state.get("attempts", 1)
    attempt_note = (
        "" if attempts == 1 else f"\nRegenerated after failing validation ({attempts} attempts).\n"
    )

    return (
        f"# Reasoning trace: {state['account_data']['account_name']}\n\n"
        f"**Generated:** {state.get('generated_at', '')}\n"
        f"{attempt_note}\n"
        "Internal only — not shown to the account manager. Kept for debugging a wrong "
        "classification or a weird output.\n\n---\n\n"
        f"{briefing.reasoning}\n"
    )
