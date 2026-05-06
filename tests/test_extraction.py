import pytest, json
from unittest.mock import AsyncMock, patch, MagicMock
from agent.nodes import node_extract

SAMPLE_TEXT = "SERVICE AGREEMENT dated 2023-01-15. Vendor: Acme Corp. Value: EUR 250,000. Expiry: 2026-06-30. Auto-renewal: Yes. Escalation: 3% annual. SLA: 2% deduction."

BASE_STATE = {"contracts_dir":"data/contracts","db_path":":memory:",
    "pdf_files":["data/contracts/acme_001.pdf"],"extracted_contracts":[],
    "errors":[],"flagged_renewals":[],"market_benchmarks":{},"alerts":[],"memos":[],"human_approved":None}

@pytest.mark.asyncio
async def test_extraction_happy_path():
    mock_r = MagicMock()
    mock_r.content = [MagicMock(text=json.dumps({"vendor":"Acme Corp","category":"IT Services",
        "value":250000.0,"currency":"EUR","start_date":"2023-01-15","expiry_date":"2026-06-30",
        "auto_renewal":True,"sla_penalty":"2% deduction","price_escalation":"3% annual"}))]
    with patch("agent.nodes.FileSystemMCP") as MFS, \
         patch("agent.nodes.DatabaseMCP") as MDB, \
         patch("agent.nodes.client") as MC:
        MFS.return_value.list_pdfs = AsyncMock(return_value=["acme_001.pdf"])
        MFS.return_value.read_pdf_text = AsyncMock(return_value=SAMPLE_TEXT)
        MDB.return_value.upsert_contract = AsyncMock()
        MC.messages.create.return_value = mock_r
        result = await node_extract(BASE_STATE)
    assert len(result["extracted_contracts"]) == 1
    assert result["extracted_contracts"][0]["vendor"] == "Acme Corp"
    assert result["errors"] == []
