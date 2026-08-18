from enum import Enum

from pydantic import BaseModel, Field


class AccountStatus(str, Enum):
    HEALTHY = "Healthy"
    AT_RISK = "At-Risk"
    STALLED = "Stalled"


class Briefing(BaseModel):
    reasoning: str = Field(description="Think step by step, before anything else: walk through the signals in the account data, weigh them against the Healthy/At-Risk/Stalled rubric, and explain which way they point and why. Write this first — the other fields should follow from this reasoning, not the other way around. Internal only, never shown to the account manager.")
    status: AccountStatus
    snapshot: str = Field(description="Account name, tier, and ARR, e.g. 'Nimbus Confectionery · Strategic · $2.1M ARR'")
    why: list[str] = Field(min_length=2, max_length=3, description="2-3 signals from the data that led to this status, each citing the exact data point in parentheses")
    who_to_talk_to: list[str] = Field(min_length=1, description="Key person(s) for the next conversation, with role and why they matter")
    next_actions: list[str] = Field(min_length=2, max_length=3, description="2-3 specific, concrete things the account manager should do next")
    one_thing_to_watch: str = Field(description="The single biggest risk or opportunity")
