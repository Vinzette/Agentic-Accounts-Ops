"""The briefing pipeline as a LangGraph StateGraph.

load_data → generate_briefing → validate_output → persist_run → save_briefing
                   ▲                   │
                   └─── regenerate ────┘
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from models import Briefing
from nodes import (
    MAX_ATTEMPTS,
    generate_briefing,
    load_data,
    persist_run,
    save_briefing,
    validate_output,
)


class GraphState(TypedDict, total=False):
    """Everything the pipeline accumulates. `total=False` so nodes can fill it in stages."""

    # Input. The CLI supplies account_slug (names the file to read, and the
    # files to write); the web path supplies account_data directly and no slug.
    account_slug: str
    account_data: dict
    account_id: int | None
    input_source: str

    # Set by load_data.
    missing_fields: list[str]
    evidence_gaps: list[str]
    provisional: bool
    generated_at: str

    # Set by generate_briefing, and overwritten on each retry.
    briefing: Briefing | None
    raw_response: str
    attempts: int

    # Set by validate_output.
    validation_passed: bool
    validation_errors: list[str]
    validation_warnings: list[str]

    # Set by persist_run and save_briefing.
    run_id: int | None
    markdown: str
    output_path: str


def route_after_validation(state: GraphState) -> str:
    """Ship it, or send it back with the failures attached.

    After MAX_ATTEMPTS it ships anyway, flagged — a caveated answer beats none.
    """
    if state.get("validation_passed"):
        return "persist_run"
    if state.get("attempts", 0) < MAX_ATTEMPTS:
        return "generate_briefing"
    return "persist_run"


def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("load_data", load_data)
    graph.add_node("generate_briefing", generate_briefing)
    graph.add_node("validate_output", validate_output)
    graph.add_node("persist_run", persist_run)
    graph.add_node("save_briefing", save_briefing)

    graph.add_edge(START, "load_data")
    graph.add_edge("load_data", "generate_briefing")
    graph.add_edge("generate_briefing", "validate_output")
    graph.add_conditional_edges(
        "validate_output",
        route_after_validation,
        ["generate_briefing", "persist_run"],
    )
    graph.add_edge("persist_run", "save_briefing")
    graph.add_edge("save_briefing", END)

    return graph.compile()
