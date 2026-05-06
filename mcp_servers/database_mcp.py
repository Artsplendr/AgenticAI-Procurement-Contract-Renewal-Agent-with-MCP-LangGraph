import os
import aiosqlite
from mcp_servers.base_mcp import BaseMCP

CREATE = """CREATE TABLE IF NOT EXISTS contracts (
    id TEXT PRIMARY KEY, vendor TEXT, category TEXT, value REAL, currency TEXT,
    start_date TEXT, expiry_date TEXT, auto_renewal INTEGER,
    sla_penalty TEXT, price_escalation TEXT, raw_text TEXT,
    created_at TEXT DEFAULT (datetime('now')));"""

class DatabaseMCP(BaseMCP):
    def __init__(self, db_path: str):
        super().__init__()
        self.db_path = db_path
    async def _init(self, db): await db.execute(CREATE); await db.commit()
    async def upsert_contract(self, data: dict):
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await self._init(db)
            await db.execute("""INSERT INTO contracts (id,vendor,category,value,currency,
                start_date,expiry_date,auto_renewal,sla_penalty,price_escalation,raw_text)
                VALUES (:id,:vendor,:category,:value,:currency,:start_date,:expiry_date,
                :auto_renewal,:sla_penalty,:price_escalation,:raw_text)
                ON CONFLICT(id) DO UPDATE SET vendor=excluded.vendor,
                expiry_date=excluded.expiry_date,value=excluded.value""", data)
            await db.commit()
    async def get_expiring_before(self, date_str: str) -> list:
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await self._init(db)
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM contracts WHERE expiry_date <= ? ORDER BY expiry_date", (date_str,)) as c:
                return [dict(r) for r in await c.fetchall()]

    async def contract_exists(self, contract_id: str) -> bool:
        """Return True if a real (non-seeded) record already exists for this id."""
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await self._init(db)
            async with db.execute(
                "SELECT raw_text FROM contracts WHERE id = ?", (contract_id,)) as c:
                row = await c.fetchone()
                if row is None:
                    return False
                # Seeded placeholder records should be re-extracted
                return row[0] not in (None, "", "Seeded record.", "seeded")
