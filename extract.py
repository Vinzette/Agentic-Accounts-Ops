"""Turn messy account notes into a structured AccountData draft.

One model call, not an agent — it has its own prompt and schema but no state
and no branching. The result is handed back for a human to review before any
briefing is generated from it.
"""

from langchain_openai import ChatOpenAI

from models import AccountData
from nodes import MODEL, PROMPTS_DIR

EXTRACTION_PROMPT = PROMPTS_DIR / "extraction_prompt.md"


def extract_account(notes: str) -> AccountData:
    llm = ChatOpenAI(model=MODEL, temperature=0)
    return llm.with_structured_output(AccountData).invoke(
        [
            ("system", EXTRACTION_PROMPT.read_text()),
            ("user", notes),
        ]
    )
