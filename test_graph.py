"""Offline check that the validation cycle loops and terminates.

No API calls and no file writes: the model call, the semantic checks and the
save step are all stubbed, so this exercises the wiring in `graph.py` and
nothing else. Run it with `python test_graph.py`.
"""

import graph as graph_module
import nodes
from models import AccountStatus, Briefing

ACCOUNT = {"account_name": "Test Co", "arr": "$1M"}

GROUNDING_FAILURE = ['Signal cites "$9.9M", which does not appear anywhere in the account data']


def _briefing() -> Briefing:
    return Briefing(
        reasoning="stub",
        status=AccountStatus.HEALTHY,
        snapshot="Test Co · Growth · $1M ARR",
        why=["Signal one (from $1M)", "Signal two (from $1M)"],
        who_to_talk_to=["Someone"],
        next_actions=["Do a thing", "Do another thing"],
        one_thing_to_watch="stub",
    )


def _stub_briefing(state: dict) -> dict:
    """Stand in for the LLM call, counting attempts the way the real node does."""
    return {"briefing": _briefing(), "raw_response": "", "attempts": state.get("attempts", 0) + 1}


def _build_with(check_briefing) -> object:
    """Compile a graph whose model call and save step are stubbed out."""
    graph_module.generate_briefing = _stub_briefing
    graph_module.persist_run = lambda state: {"run_id": None}
    graph_module.save_briefing = lambda state: {"markdown": "", "output_path": ""}
    nodes.check_briefing = check_briefing
    return graph_module.build_graph()


def test_recovers_after_one_failure() -> None:
    """A briefing that fails once should be regenerated and then ship clean."""
    calls = {"n": 0}

    def fails_once(briefing, account_data):
        calls["n"] += 1
        return (GROUNDING_FAILURE, []) if calls["n"] == 1 else ([], [])

    result = _build_with(fails_once).invoke({"account_data": ACCOUNT})

    assert result["attempts"] == 2, result["attempts"]
    assert result["validation_passed"] is True
    assert result["validation_errors"] == []


def test_gives_up_and_ships_flagged() -> None:
    """A briefing that never grounds should stop at MAX_ATTEMPTS, carrying its errors."""
    result = _build_with(lambda b, d: (GROUNDING_FAILURE, [])).invoke({"account_data": ACCOUNT})

    assert result["attempts"] == nodes.MAX_ATTEMPTS, result["attempts"]
    assert result["validation_passed"] is False
    assert result["validation_errors"] == GROUNDING_FAILURE


def test_warnings_do_not_trigger_a_retry() -> None:
    """Warnings are advisory — they ship with the briefing, they don't cost a call."""
    result = _build_with(lambda b, d: ([], ["worth a second look"])).invoke(
        {"account_data": ACCOUNT}
    )

    assert result["attempts"] == 1, result["attempts"]
    assert result["validation_passed"] is True
    assert result["validation_warnings"] == ["worth a second look"]


def test_web_path_writes_no_files() -> None:
    """No slug means no CLI artifact. Web runs must render markdown but touch no disk."""
    result = nodes.save_briefing(
        {
            "briefing": _briefing(),
            "account_data": {"account_name": "Nimbus Confectionery"},
            "generated_at": "",
        }
    )

    assert result["markdown"], "markdown is still needed for the streamed result"
    assert "output_path" not in result, "a web run must not write into outputs/"


if __name__ == "__main__":
    test_recovers_after_one_failure()
    test_gives_up_and_ships_flagged()
    test_warnings_do_not_trigger_a_retry()
    test_web_path_writes_no_files()
    print("graph cycle self-check passed")
