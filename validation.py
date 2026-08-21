"""Semantic checks on a generated briefing: is what it says supported by the source data?

Pydantic already covers shape. These are pure functions — `nodes.validate_output`
wires them in. Run `python validation.py` for a self-check.
"""

import re

from models import NOT_RECORDED, AccountStatus, Briefing

PARENTHETICAL = re.compile(r"\(([^)]*)\)")

# Digits with optional separators, decimals and a %/M/K/B suffix. The negative
# lookahead stops "3 markets" being read as the figure "3 m".
FIGURE = re.compile(r"\d[\d,]*(?:\.\d+)?(?:\s*%|\s*[mkbMKB](?![a-zA-Z]))?")

# Crude by design, which is why hits are warnings rather than grounds to retry.
NEGATIVE_MARKERS = ("declin", "dropp", "left", "overrun", "unengaged", "churn", "stalled")


# What each check does and whether failing it costs a regeneration. Kept here so
# anything describing the checks describes the ones that actually run.
CHECKS = [
    {
        "name": "Citation grounding",
        "detail": "Every figure cited inside brackets must appear in the account data.",
        "on_failure": "regenerates",
    },
    {
        "name": "Snapshot ARR",
        "detail": "The ARR in the snapshot line must match the ARR on record.",
        "on_failure": "regenerates",
    },
    {
        "name": "Missing citation",
        "detail": "Every signal has to carry a parenthetical citation.",
        "on_failure": "regenerates",
    },
    {
        "name": "Status contradiction",
        "detail": (
            "A Healthy verdict whose own supporting signals read negative. Deliberately "
            "crude, so it never drives a retry."
        ),
        "on_failure": "warns",
    },
]


def normalise(text: str) -> str:
    """Strip formatting noise so "~$2,000" and "$2000" compare equal."""
    return re.sub(r"[\s,~$]", "", text).lower()


def flatten(account_data: dict) -> str:
    """Squash the account record into one searchable string.

    Keys are included: the model sees field names too, so "last_90_days" is a
    faithful citation and its "90" must not read as fabricated.
    """
    parts: list[str] = []
    for key, value in account_data.items():
        parts.append(str(key))
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif value is not None:
            parts.append(str(value))
    return " ".join(parts)


def ungrounded_figures(text: str, haystack: str) -> list[str]:
    """Figures in `text` absent from `haystack` (already normalised).

    Substring matching is lenient on purpose: catching invented figures matters,
    quibbling that "120" also occurs in "2,120" would only cause thrash.
    """
    return [figure for figure in FIGURE.findall(text) if normalise(figure) not in haystack]


def _check_citations(briefing: Briefing, haystack: str) -> list[str]:
    """Every figure cited inside brackets must exist in the source data.

    Scan the bracketed text only, never the whole signal — the sentence around
    the brackets may hold computed figures the source never contained.
    """
    errors: list[str] = []
    for signal in briefing.why:
        citations = PARENTHETICAL.findall(signal)
        if not citations:
            errors.append(f'Signal has no parenthetical citation: "{signal}"')
            continue
        for cited in citations:
            for figure in ungrounded_figures(cited, haystack):
                errors.append(
                    f'Signal cites "{figure.strip()}", which does not appear anywhere '
                    f'in the account data: "{signal}"'
                )
    return errors


def _check_snapshot(briefing: Briefing, account_data: dict) -> list[str]:
    """The ARR in the snapshot line must match the ARR on record."""
    arr = account_data.get("arr")
    if not arr or arr == NOT_RECORDED:
        return []

    haystack = normalise(str(arr))
    return [
        f'Snapshot cites ARR "{figure.strip()}", which does not match the '
        f'account data ARR ("{arr}")'
        for figure in ungrounded_figures(briefing.snapshot, haystack)
    ]


def _check_status_consistency(briefing: Briefing) -> list[str]:
    """Flag a Healthy verdict whose own evidence reads negative. Warning, never an error."""
    if briefing.status is not AccountStatus.HEALTHY:
        return []

    signals = " ".join(briefing.why).lower()
    hits = [marker for marker in NEGATIVE_MARKERS if marker in signals]
    if not hits:
        return []

    return [
        f"Status is Healthy but the supporting signals contain negative language "
        f"({', '.join(hits)}) — worth a second look."
    ]


def check_briefing(briefing: Briefing, account_data: dict) -> tuple[list[str], list[str]]:
    """Check a briefing against its source data.

    Returns `(errors, warnings)`: errors are worth regenerating for, warnings ship as-is.
    """
    haystack = normalise(flatten(account_data))
    errors = _check_citations(briefing, haystack) + _check_snapshot(briefing, account_data)
    return errors, _check_status_consistency(briefing)


def _self_check() -> None:
    nimbus = {
        "account_name": "Nimbus Confectionery",
        "arr": "$2.1M (up from $1.6M a year ago)",
        "adoption": "Daily active field users ~88% of licensed seats",
        "products_in_use": ["Image Recognition (rolled out in 2 of 5 markets)"],
        "nps": "9 — advocate",
    }

    def brief(**overrides) -> Briefing:
        base = dict(
            reasoning="…",
            status=AccountStatus.HEALTHY,
            snapshot="Nimbus Confectionery · Strategic · $2.1M ARR",
            why=[
                "ARR grew 31% year-over-year (from $1.6M to $2.1M)",
                "Adoption is strong (~88% of licensed seats are daily active users)",
            ],
            who_to_talk_to=["VP Sales"],
            next_actions=["Scope the rollout", "Book the QBR"],
            one_thing_to_watch="…",
        )
        return Briefing(**{**base, **overrides})

    # A correct briefing passes, including the computed "31%" outside the brackets.
    errors, warnings = check_briefing(brief(), nimbus)
    assert errors == [], errors
    assert warnings == [], warnings

    # An invented figure inside brackets is caught.
    errors, _ = check_briefing(brief(why=["ARR grew (from $1.6M to $3.2M)", "Fine (~88%)"]), nimbus)
    assert len(errors) == 1 and "3.2M" in errors[0], errors

    # A missing citation is caught.
    errors, _ = check_briefing(brief(why=["ARR is growing nicely", "Fine (~88%)"]), nimbus)
    assert len(errors) == 1 and "no parenthetical" in errors[0], errors

    # A snapshot that contradicts the ARR on record is caught.
    errors, _ = check_briefing(brief(snapshot="Nimbus · Strategic · $9.9M ARR"), nimbus)
    assert len(errors) == 1 and "9.9M" in errors[0], errors

    # Healthy plus negative language warns, but does not error.
    errors, warnings = check_briefing(
        brief(why=["Champion left (replacement not named)", "Adoption fine (~88%)"]), nimbus
    )
    assert errors == [], errors
    assert len(warnings) == 1 and "left" in warnings[0], warnings

    # Field names are part of the record: "last_90_days" must not make "90" look invented.
    errors, _ = check_briefing(
        brief(why=["Nothing on file (last_90_days: not recorded)", "Adoption fine (~88%)"]),
        {"account_name": "Thin Co", "last_90_days": [], "adoption": "~88% of seats"},
    )
    assert errors == [], errors

    # Sparse accounts skip the ARR check rather than failing it.
    errors, _ = check_briefing(brief(), {"account_name": "Thin Co", "arr": NOT_RECORDED})
    assert all("Snapshot" not in e for e in errors), errors

    print("validation self-check passed")


if __name__ == "__main__":
    _self_check()
