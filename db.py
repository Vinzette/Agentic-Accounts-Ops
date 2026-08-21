"""Storage for managers, accounts, and the briefing run log.

Imports nothing else from this project, so anything may depend on it.
`DATABASE_URL` picks the backend: SQLite by default, Postgres in deployment.
"""

import hashlib
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine

log = logging.getLogger(__name__)

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
DEFAULT_URL = f"sqlite:///{ROOT / 'agentops.db'}"

metadata = MetaData()

account_managers = Table(
    "account_managers",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(120), nullable=False, unique=True),
    Column("region", String(120)),
)

accounts = Table(
    "accounts",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("manager_id", Integer, ForeignKey("account_managers.id"), nullable=False),
    Column("slug", String(120), nullable=False, unique=True),
    Column("display_name", String(200), nullable=False),
    Column("data", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), default=lambda: datetime.now(UTC)),
    Column("updated_at", DateTime(timezone=True), default=lambda: datetime.now(UTC)),
)

runs = Table(
    "runs",
    metadata,
    Column("id", Integer, primary_key=True),
    # Null for a briefing generated from data typed into the UI and never saved.
    Column("account_id", Integer, ForeignKey("accounts.id")),
    Column("account_display_name", String(200), nullable=False),
    Column("created_at", DateTime(timezone=True), default=lambda: datetime.now(UTC)),
    Column("input_source", String(20), nullable=False),
    Column("model", String(60), nullable=False),
    Column("prompt_version", String(12), nullable=False),
    # Accounts are edited in place, so a run keeps its own copy of its input.
    # input_hash makes identical inputs with differing outputs visible.
    Column("input_data", JSON, nullable=False),
    Column("input_hash", String(12), nullable=False),
    Column("attempts", Integer, nullable=False),
    Column("validation_passed", Boolean, nullable=False),
    Column("validation_errors", JSON, nullable=False),
    Column("validation_warnings", JSON, nullable=False),
    Column("raw_response", Text),
    Column("parsed_briefing", JSON, nullable=False),
)

SEED_MANAGERS = [
    {"name": "Adit Chauhan", "region": "International Markets & Global Accounts"},
    {"name": "Arjun Rao", "region": "APAC"},
]

_engine: Engine | None = None


def content_hash(value: Any) -> str:
    """Short stable hash of any JSON-serialisable value."""
    blob = json.dumps(value, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()[:12]


def engine() -> Engine:
    """The process-wide engine, built on first use."""
    global _engine
    if _engine is None:
        url = os.getenv("DATABASE_URL", DEFAULT_URL)
        options: dict[str, Any] = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            # FastAPI serves from a thread pool, which SQLite rejects by default.
            options["connect_args"] = {"check_same_thread": False}
        _engine = create_engine(url, **options)
    return _engine


def init_db() -> None:
    """Create tables if absent and seed a starting book of accounts."""
    metadata.create_all(engine())
    _seed_if_empty()


def _seed_if_empty() -> None:
    with engine().begin() as conn:
        if conn.execute(select(func.count()).select_from(account_managers)).scalar():
            return

        manager_ids = [
            conn.execute(insert(account_managers).values(**manager)).inserted_primary_key[0]
            for manager in SEED_MANAGERS
        ]

        # Sample accounts all sit with the first manager so the portfolio brief
        # has a real book to compare across. The second starts empty on purpose.
        for path in sorted(DATA_DIR.glob("*.json")):
            data = json.loads(path.read_text())
            conn.execute(
                insert(accounts).values(
                    manager_id=manager_ids[0],
                    slug=path.stem,
                    display_name=data.get("account_name", path.stem),
                    data=data,
                )
            )


def list_managers() -> list[dict]:
    """Every manager, with how many accounts each owns."""
    query = (
        select(
            account_managers.c.id,
            account_managers.c.name,
            account_managers.c.region,
            func.count(accounts.c.id).label("account_count"),
        )
        .select_from(account_managers.outerjoin(accounts))
        .group_by(account_managers.c.id)
        .order_by(account_managers.c.id)
    )
    with engine().connect() as conn:
        return [row._asdict() for row in conn.execute(query)]


def create_manager(name: str, region: str | None = None) -> dict:
    """Add a manager. Raises ValueError if the name is already taken."""
    with engine().begin() as conn:
        taken = conn.execute(
            select(account_managers.c.id).where(account_managers.c.name == name)
        ).first()
        if taken:
            raise ValueError(f"There is already a manager called {name}.")

        conn.execute(insert(account_managers).values(name=name, region=region))

    return next(m for m in list_managers() if m["name"] == name)


def list_accounts(manager_id: int | None = None) -> list[dict]:
    query = select(accounts).order_by(accounts.c.display_name)
    if manager_id is not None:
        query = query.where(accounts.c.manager_id == manager_id)
    with engine().connect() as conn:
        return [row._asdict() for row in conn.execute(query)]


def get_account(account_id: int) -> dict | None:
    with engine().connect() as conn:
        row = conn.execute(select(accounts).where(accounts.c.id == account_id)).first()
    return row._asdict() if row else None


def save_account(manager_id: int, slug: str, data: dict) -> int:
    """Create the account, or update it in place if the slug exists."""
    display_name = data.get("account_name", slug)

    with engine().begin() as conn:
        existing = conn.execute(select(accounts.c.id).where(accounts.c.slug == slug)).first()
        if existing:
            conn.execute(
                update(accounts)
                .where(accounts.c.id == existing.id)
                .values(
                    manager_id=manager_id,
                    display_name=display_name,
                    data=data,
                    updated_at=datetime.now(UTC),
                )
            )
            return existing.id

        return conn.execute(
            insert(accounts).values(
                manager_id=manager_id,
                slug=slug,
                display_name=display_name,
                data=data,
            )
        ).inserted_primary_key[0]


def record_run(**fields: Any) -> int | None:
    """Append one run to the audit log. Never raises."""
    try:
        fields.setdefault("input_hash", content_hash(fields.get("input_data")))
        with engine().begin() as conn:
            return conn.execute(insert(runs).values(**fields)).inserted_primary_key[0]
    except Exception:
        log.exception("Could not record run to the audit log; continuing without it")
        return None


def list_runs(limit: int = 50) -> list[dict]:
    """Recent runs, newest first, without the bulky raw response or input."""
    query = (
        select(
            runs.c.id,
            runs.c.account_id,
            runs.c.account_display_name,
            runs.c.created_at,
            runs.c.input_source,
            runs.c.model,
            runs.c.prompt_version,
            runs.c.input_hash,
            runs.c.attempts,
            runs.c.validation_passed,
            runs.c.validation_errors,
            runs.c.validation_warnings,
        )
        .order_by(runs.c.id.desc())
        .limit(limit)
    )
    with engine().connect() as conn:
        return [row._asdict() for row in conn.execute(query)]


def get_run(run_id: int) -> dict | None:
    """One run in full, including the raw model response and the input it ran on."""
    with engine().connect() as conn:
        row = conn.execute(select(runs).where(runs.c.id == run_id)).first()
    return row._asdict() if row else None


def _self_check() -> None:
    import tempfile

    global _engine
    with tempfile.TemporaryDirectory() as tmp:
        _engine = None
        os.environ["DATABASE_URL"] = f"sqlite:///{Path(tmp) / 'check.db'}"

        init_db()
        init_db()  # idempotent: must not double-seed

        managers = list_managers()
        assert len(managers) == len(SEED_MANAGERS), managers

        added = create_manager("Test Manager", "Nowhere")
        assert added["account_count"] == 0 and added["region"] == "Nowhere", added
        assert len(list_managers()) == len(SEED_MANAGERS) + 1
        try:
            create_manager("Test Manager")
            raise AssertionError("duplicate manager name should raise")
        except ValueError as e:
            assert "already a manager" in str(e), e

        assert [m["account_count"] for m in managers] == [3, 0], managers

        owned = list_accounts(managers[0]["id"])
        assert len(owned) == 3, owned

        # Saving an existing slug updates rather than duplicating.
        account_id = save_account(managers[0]["id"], "nimbus", {"account_name": "Renamed"})
        assert len(list_accounts()) == 3
        assert get_account(account_id)["display_name"] == "Renamed"

        fields = dict(
            account_id=account_id,
            account_display_name="Renamed",
            input_source="form",
            model="gpt-5.1",
            prompt_version="abc123def456",
            input_data={"account_name": "Renamed", "arr": "$1M"},
            attempts=2,
            validation_passed=False,
            validation_errors=["cited $9.9M"],
            validation_warnings=[],
            raw_response='{"status": "Healthy"}',
            parsed_briefing={"status": "Healthy"},
        )
        run_id = record_run(**fields)
        assert run_id is not None
        assert record_run(**fields) != run_id, "runs must append, never overwrite"

        listing = list_runs()
        assert len(listing) == 2, listing
        assert listing[0]["id"] > listing[1]["id"], "newest first"
        assert "raw_response" not in listing[0], "listing stays light"
        assert listing[0]["input_hash"] == listing[1]["input_hash"], "same input, same hash"

        full = get_run(run_id)
        assert full["raw_response"] == '{"status": "Healthy"}'
        assert full["input_data"]["arr"] == "$1M", "run keeps its own copy of the input"

        # Editing the account must not rewrite what an earlier run ran on.
        save_account(managers[0]["id"], "nimbus", {"account_name": "Renamed", "arr": "$2M"})
        assert get_run(run_id)["input_data"]["arr"] == "$1M"

        # A broken database must not take a briefing down with it.
        _engine = None
        os.environ["DATABASE_URL"] = "sqlite:////nonexistent-dir/nope.db"
        assert record_run(**fields) is None, "a failed write must be swallowed"

        print("db self-check passed")


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)  # the failure path logs on purpose
    _self_check()
