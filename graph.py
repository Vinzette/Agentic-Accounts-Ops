from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from models import Briefing
from nodes import generate_briefing, load_data, save_and_display, validate_output


class GraphState(TypedDict, total=False):
    account_name: str
    account_data: dict
    generated_at: str
    raw_response: str
    briefing: Briefing | None
    output_path: str


def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("load_data", load_data)
    graph.add_node("generate_briefing", generate_briefing)
    graph.add_node("validate_output", validate_output)
    graph.add_node("save_and_display", save_and_display)

    graph.add_edge(START, "load_data")
    graph.add_edge("load_data", "generate_briefing")
    graph.add_edge("generate_briefing", "validate_output")
    graph.add_edge("validate_output", "save_and_display")
    graph.add_edge("save_and_display", END)

    return graph.compile()
