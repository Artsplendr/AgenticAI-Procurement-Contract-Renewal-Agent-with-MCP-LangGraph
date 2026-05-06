"""
Tests for node_check_renewals: verifies the threshold bucketing logic using
a temp-file SQLite database seeded with contracts at known expiry distances.

Note: SQLite :memory: databases are connection-scoped, so each aiosqlite.connect()
gets a fresh empty DB. Tests use a named temp file so all connections share state.
"""
import os
import pytest
import tempfile
from datetime import date, timedelta
from agent.nodes import node_check_renewals
from mcp_servers.database_mcp import DatabaseMCP

TODAY = date.today()

CONTRACTS = [
    # id, days_from_today
    ("c_10d",  10),   # urgent — inside ≤30 bucket
    ("c_25d",  25),   # urgent — inside ≤30 bucket
    ("c_45d",  45),   # inside ≤60 but not ≤30
    ("c_75d",  75),   # inside ≤90 but not ≤60
    ("c_120d", 120),  # outside all thresholds — must NOT be flagged
    ("c_past", -5),   # already expired — still ≤90 so flagged
]


def _make_state(db_path: str) -> dict:
    return {
        "contracts_dir": "data/contracts",
        "db_path": db_path,
        "pdf_files": [],
        "extracted_contracts": [],
        "flagged_renewals": [],
        "market_benchmarks": {},
        "alerts": [],
        "memos": [],
        "errors": [],
        "human_approved": None,
    }


async def _seeded_db() -> tuple[DatabaseMCP, str]:
    """Create a named temp DB file, seed it, return (db, path)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = DatabaseMCP(tmp.name)
    for cid, days in CONTRACTS:
        expiry = (TODAY + timedelta(days=days)).isoformat()
        await db.upsert_contract({
            "id": cid,
            "vendor": f"Vendor {cid}",
            "category": "IT Services",
            "value": 100_000.0,
            "currency": "EUR",
            "start_date": (TODAY - timedelta(days=365)).isoformat(),
            "expiry_date": expiry,
            "auto_renewal": 1,
            "sla_penalty": None,
            "price_escalation": None,
            "raw_text": "seeded",
        })
    return db, tmp.name


@pytest.mark.asyncio
async def test_urgent_contracts_are_flagged():
    """Contracts expiring within 30 days (including past) must appear in flagged_renewals."""
    _, db_path = await _seeded_db()
    try:
        result = await node_check_renewals(_make_state(db_path))
        flagged_ids = {c["id"] for c in result["flagged_renewals"]}
        assert "c_10d" in flagged_ids
        assert "c_25d" in flagged_ids
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_beyond_threshold_not_flagged():
    """Contracts expiring in 120 days must NOT appear regardless of threshold."""
    _, db_path = await _seeded_db()
    try:
        result = await node_check_renewals(_make_state(db_path))
        flagged_ids = {c["id"] for c in result["flagged_renewals"]}
        assert "c_120d" not in flagged_ids
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_no_duplicate_contracts():
    """A contract matching multiple thresholds must appear only once in flagged_renewals."""
    _, db_path = await _seeded_db()
    try:
        result = await node_check_renewals(_make_state(db_path))
        ids = [c["id"] for c in result["flagged_renewals"]]
        assert len(ids) == len(set(ids)), "Duplicate contracts found in flagged_renewals"
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_days_left_field_present():
    """Each flagged contract must carry days_left and urgency fields."""
    _, db_path = await _seeded_db()
    try:
        result = await node_check_renewals(_make_state(db_path))
        for c in result["flagged_renewals"]:
            assert "days_left" in c, f"Missing days_left on contract {c.get('id')}"
            assert "urgency" in c, f"Missing urgency on contract {c.get('id')}"
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_empty_db_returns_no_renewals():
    """When the database is empty, flagged_renewals must be an empty list."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    try:
        result = await node_check_renewals(_make_state(tmp.name))
        assert result["flagged_renewals"] == []
    finally:
        os.unlink(tmp.name)
