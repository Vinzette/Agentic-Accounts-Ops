"""The briefing pipeline's node functions. Each returns only the keys it changed."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from langchain_openai import ChatOpenAI
from pydantic import ValidationError

import db
from models import AccountData, Briefing
from validation import check_briefing

PROMPTS_DIR = Path(__file__).parent / "prompts"
BRIEFING_PROMPT = PROMPTS_DIR / "briefing_prompt.md"
DATA_DIR = Path(__file__).parent / "data"
OUTPUTS_DIR = Path(__file__).parent / "outputs"
DEBUG_DIR = Path(__file__).parent / "debug"

MODEL = "gpt-5.1"

# Total generations, not retries. A model failing grounding twice rarely fixes
# itself on a third pass.
MAX_ATTEMPTS = 2

STATUS_EMOJI = {
    "Healthy": "🟢",
    "At-Risk": "🟡",
    "Stalled": "🔴",
}


def load_data(state: dict) -> dict:
    """Resolve the account data and validate it before any API call.

    The CLI names an account to read off disk; the web app passes data directly.
    Validation sits outside the branch so both paths get the same guard.
    """
    raw = state.get("account_data")
    source = "The account data"

    if raw is None:
        slug = state["account_slug"]
        data_path = DATA_DIR / f"{slug}.json"
        if not data_path.exists():
            raise FileNotFoundError(f"No data file for account '{slug}' at {data_path}")
        raw = json.loads(data_path.read_text())
        source = str(data_path)

    try:
        account = AccountData.model_validate(raw)
    except ValidationError as e:
        raise ValueError(f"{source} doesn't match the expected account data shape:\n{e}") from e

    return {
        # The model-facing form, so citations are checked against what it saw.
        "account_data": account.for_prompt(),
        "missing_fields": account.missing_fields(),
        "evidence_gaps": account.evidence_gaps(),
        "provisional": account.is_provisional(),
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
    }


def generate_briefing(state: dict) -> dict:
    """Call the model. On a retry, tell it exactly what failed last time."""
    system_prompt = BRIEFING_PROMPT.read_text()
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
    """Check the briefing; `graph.route_after_validation` decides what to do about it."""
    briefing: Briefing | None = state["briefing"]
    if briefing is None:
        raise ValueError("The model did not return a briefing matching the schema.")

    errors, warnings = check_briefing(briefing, state["account_data"])
    return {
        "validation_passed": not errors,
        "validation_errors": errors,
        "validation_warnings": warnings,
    }


def prompt_version() -> str:
    """Short hash of the system prompt, so a run can be traced to the prompt that made it."""
    return hashlib.sha256(BRIEFING_PROMPT.read_bytes()).hexdigest()[:12]


def persist_run(state: dict) -> dict:
    """Append this run to the audit log. `record_run` swallows its own failures."""
    briefing: Briefing = state["briefing"]
    run_id = db.record_run(
        account_id=state.get("account_id"),
        account_display_name=state["account_data"]["account_name"],
        input_source=state.get("input_source", "file"),
        model=MODEL,
        prompt_version=prompt_version(),
        input_data=state["account_data"],
        attempts=state.get("attempts", 1),
        validation_passed=state.get("validation_passed", False),
        validation_errors=state.get("validation_errors") or [],
        validation_warnings=state.get("validation_warnings") or [],
        raw_response=state.get("raw_response"),
        parsed_briefing=briefing.model_dump(mode="json"),
    )
    return {"run_id": run_id}


def save_briefing(state: dict) -> dict:
    """Render the briefing, and write it to disk only for CLI runs.

    `outputs/` and `debug/` exist so the repo shows results without running
    anything — a CLI concern. Web runs pass no slug: their filesystem is
    ephemeral and the markdown already travels in the response and the run log.
    """
    markdown = render_markdown(state)
    slug = state.get("account_slug")
    if not slug:
        return {"markdown": markdown}

    OUTPUTS_DIR.mkdir(exist_ok=True)
    output_path = OUTPUTS_DIR / f"{slug}_briefing.md"
    output_path.write_text(markdown)

    DEBUG_DIR.mkdir(exist_ok=True)
    (DEBUG_DIR / f"{slug}_reasoning.md").write_text(_render_reasoning(state))

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
    """Trust caveats, omitted entirely when there are none."""
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
