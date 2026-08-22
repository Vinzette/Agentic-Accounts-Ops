"""Portfolio agent: one brief across every account a manager owns.

Fans the briefing pipeline out across the book in parallel, then synthesises the
results. The fan-out is the one thing here a single call can't express — each
account gets its own grounded, audited briefing before anything is compared.

    START ─┬─> brief_one (account 1) ─┐
           ├─> brief_one (account 2) ─┼─> synthesize ─> END
           └─> brief_one (account N) ─┘
"""

import json
import operator
from functools import lru_cache
from typing import Annotated, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from graph import build_graph
from models import PortfolioBrief
from nodes import MODEL, PROMPTS_DIR

PORTFOLIO_PROMPT = PROMPTS_DIR / "portfolio_prompt.md"


class PortfolioState(TypedDict, total=False):
    manager_name: str
    accounts: list[dict]
    # Parallel branches each return one briefing; the reducer merges them.
    briefings: Annotated[list[dict], operator.add]
    portfolio_brief: PortfolioBrief | None


@lru_cache(maxsize=1)
def _briefing_graph():
    return build_graph()


def fan_out(state: PortfolioState) -> list[Send]:
    """Dispatch one briefing run per account, in parallel."""
    return [
        Send("brief_one", {"account_data": account.get("data", account), "account": account})
        for account in state["accounts"]
    ]


def brief_one(state: dict) -> dict:
    """Run the full briefing pipeline for one account, cycle and audit log included."""
    account = state["account"]
    result = _briefing_graph().invoke(
        {
            "account_data": state["account_data"],
            "account_id": account.get("id"),
            "input_source": "portfolio",
        }
    )
    briefing = result["briefing"]

    return {
        "briefings": [
            {
                "account_name": result["account_data"]["account_name"],
                "status": briefing.status.value,
                "provisional": result.get("provisional", False),
                "reasoning": briefing.reasoning,
                "snapshot": briefing.snapshot,
                "why": briefing.why,
                "who_to_talk_to": briefing.who_to_talk_to,
                "next_actions": briefing.next_actions,
                "one_thing_to_watch": briefing.one_thing_to_watch,
                "attempts": result.get("attempts", 1),
                "validation_passed": result.get("validation_passed", False),
                "run_id": result.get("run_id"),
            }
        ]
    }


def synthesize(state: PortfolioState) -> dict:
    """One call over the whole book. Reads the briefings, not the raw accounts."""
    # Sort for a stable prompt: parallel branches finish in arbitrary order.
    briefings = sorted(state["briefings"], key=lambda b: b["account_name"])
    payload = {
        "account_manager": state.get("manager_name", "the account manager"),
        "briefings": [
            {
                k: v
                for k, v in b.items()
                if k not in {"attempts", "run_id", "reasoning"}
            }
            for b in briefings
        ],
    }

    llm = ChatOpenAI(model=MODEL, temperature=0)
    brief = llm.with_structured_output(PortfolioBrief).invoke(
        [
            ("system", PORTFOLIO_PROMPT.read_text()),
            ("user", json.dumps(payload, indent=2)),
        ]
    )
    return {"portfolio_brief": brief}


def build_portfolio_graph():
    graph = StateGraph(PortfolioState)

    graph.add_node("brief_one", brief_one)
    graph.add_node("synthesize", synthesize)

    graph.add_conditional_edges(START, fan_out, ["brief_one"])
    graph.add_edge("brief_one", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()
