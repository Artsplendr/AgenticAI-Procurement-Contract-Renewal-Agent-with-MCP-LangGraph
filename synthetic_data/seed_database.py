"""Pre-seed SQLite with faker records."""
import asyncio, random
from datetime import date, timedelta
from faker import Faker
from mcp_servers.database_mcp import DatabaseMCP

fake = Faker()

async def seed():
    db = DatabaseMCP("data/contracts.db")
    print("Seeding 15 records...")
    for i in range(15):
        days = random.choice([15,25,45,55,75,120,200,300])
        expiry = (date.today() + timedelta(days=days)).isoformat()
        r = {"id": f"seed_{i:03d}", "vendor": fake.company(),
             "category": random.choice(["IT Services","Logistics","Raw Materials"]),
             "value": float(random.randint(50_000,1_500_000)),
             "currency": random.choice(["EUR","USD"]),
             "start_date": fake.date_between(start_date="-2y",end_date="-3m").isoformat(),
             "expiry_date": expiry, "auto_renewal": random.choice([1,0]),
             "sla_penalty": random.choice(["2% deduction","500/day",None]),
             "price_escalation": random.choice(["3% annual","CPI-linked",None]),
             "raw_text": "Seeded record."}
        await db.upsert_contract(r)
        print(f"  {r['vendor']} — {expiry}")
    print("Done.")

if __name__ == "__main__":
    asyncio.run(seed())
