"""The briefing pipeline, wired as a LangGraph StateGraph.

    load_data → generate_briefing → validate_output → save_briefing
                       ▲                   │
                       └─── regenerate ────┘

The cycle is the point. A briefing whose citations don't hold up goes back to
the model with the specific failures attached, rather than reaching an account
manager unchecked.
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from models import Briefing
from nodes import (
    MAX_ATTEMPTS,
    generate_briefing,
    load_data,
    save_briefing,
    validate_output,
)


class GraphState(TypedDict, total=False):
    """Everything the pipeline accumulates. `total=False` so nodes can fill it in stages."""

    # Input — one of these two is supplied by the caller.
    account_name: str
    account_data: dict

    # Set by load_data.
    missing_fields: list[str]
    generated_at: str

    # Set by generate_briefing, and overwritten on each retry.
    briefing: Briefing | None
    raw_response: str
    attempts: int

    # Set by validate_output.
    validation_passed: bool
    validation_errors: list[str]
    validation_warnings: list[str]

    # Set by save_briefing.
    markdown: str
    output_path: str


def route_after_validation(state: GraphState) -> str:
    """Ship it, or send it back to the model with the failures attached.

    Giving up after MAX_ATTEMPTS is deliberate: the briefing ships carrying a
    visible "unverified" note. This is advisory work with a human owner, so a
    flagged answer is more useful than no answer.
    """
    if state.get("validation_passed"):
        return "save_briefing"
    if state.get("attempts", 0) < MAX_ATTEMPTS:
        return "generate_briefing"
    return "save_briefing"


def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("load_data", load_data)
    graph.add_node("generate_briefing", generate_briefing)
    graph.add_node("validate_output", validate_output)
    graph.add_node("save_briefing", save_briefing)

    graph.add_edge(START, "load_data")
    graph.add_edge("load_data", "generate_briefing")
    graph.add_edge("generate_briefing", "validate_output")
    graph.add_conditional_edges(
        "validate_output",
        route_after_validation,
        ["generate_briefing", "save_briefing"],
    )
    graph.add_edge("save_briefing", END)

    return graph.compile()
