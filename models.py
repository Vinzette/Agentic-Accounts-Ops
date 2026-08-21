"""Pydantic contracts for the data crossing into and out of the agent."""

from enum import StrEnum

from pydantic import BaseModel, Field

NOT_RECORDED = "not recorded"


class AccountStatus(StrEnum):
    HEALTHY = "Healthy"
    AT_RISK = "At-Risk"
    STALLED = "Stalled"


class AccountData(BaseModel):
    """One account's raw data. Only `account_name` is required; real records are patchy."""

    account_name: str = Field(min_length=1)
    industry: str | None = None
    tier: str | None = None
    arr: str | None = None
    products_in_use: list[str] = Field(default_factory=list)
    adoption: str | None = None
    key_people: list[str] = Field(default_factory=list)
    last_90_days: list[str] = Field(default_factory=list)
    open_issues: str | None = None
    renewal: str | None = None
    nps: str | None = None

    def missing_fields(self) -> list[str]:
        """Fields with nothing in them, for the completeness note on the briefing."""
        return [name for name in AccountData.model_fields if not getattr(self, name)]

    def for_prompt(self) -> dict[str, str | list[str]]:
        """Serialise for the LLM, marking absent fields so absence isn't read as zero."""
        return {name: (getattr(self, name) or NOT_RECORDED) for name in AccountData.model_fields}


class Briefing(BaseModel):
    """The six-field pre-call briefing, plus the reasoning that produced it."""

    reasoning: str = Field(
        description=(
            "Think step by step, before anything else: walk through the signals in "
            "the account data, weigh them against the Healthy/At-Risk/Stalled rubric, "
            "and explain which way they point and why. Write this first — the other "
            "fields should follow from this reasoning, not the other way around. "
            "Internal only, never shown to the account manager."
        )
    )
    status: AccountStatus
    snapshot: str = Field(
        # Descriptions reach the model inside the JSON schema, so examples here
        # are live few-shot examples. Keep them invented, never a real account.
        description="Account name, tier, and ARR, e.g. 'Alder Snacks · Growth · $920K ARR'"
    )
    why: list[str] = Field(
        min_length=2,
        max_length=3,
        description=(
            "2-3 signals from the data that led to this status, each citing the "
            "exact data point in parentheses"
        ),
    )
    who_to_talk_to: list[str] = Field(
        min_length=1,
        description=("Key person(s) for the next conversation, with role and why they matter"),
    )
    next_actions: list[str] = Field(
        min_length=2,
        max_length=3,
        description="2-3 specific, concrete things the account manager should do next",
    )
    one_thing_to_watch: str = Field(description="The single biggest risk or opportunity")


class PortfolioBrief(BaseModel):
    """A brief across every account one manager owns."""

    reasoning: str = Field(
        description=(
            "Think step by step, before anything else: compare the accounts against "
            "each other, note where they rhyme and where they diverge, and work out "
            "where this manager's week should actually go. Write this first. "
            "Internal only, never shown to the account manager."
        )
    )
    headline: str = Field(
        description=(
            "One line on the state of the book, e.g. '2 of 3 accounts need attention this week'"
        )
    )
    priority_order: list[str] = Field(
        min_length=1,
        description=(
            "The accounts ranked by how urgently they need this manager, each with "
            "one line on why it sits there. Lead with the most urgent."
        ),
    )
    cross_account_patterns: list[str] = Field(
        default_factory=list,
        description=(
            "Things true across two or more accounts that no single briefing could "
            "see — a product bought but never rolled out at several, the same missing "
            "role, a shared renewal crunch. Name the accounts involved. Return an "
            "empty list if there genuinely isn't one; do not invent a pattern to fill "
            "this field."
        ),
    )
    where_your_week_goes: list[str] = Field(
        min_length=2,
        max_length=3,
        description=(
            "2-3 concrete things to do across the whole book this week, in priority order"
        ),
    )
    portfolio_risk: str = Field(
        description="The single biggest risk across all accounts taken together"
    )
