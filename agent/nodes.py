import os, json, re
from datetime import date, timedelta
from anthropic import Anthropic
from agent.state import AgentState
from agent.prompts import EXTRACTION_SYSTEM, MEMO_SYSTEM, ALERT_TEMPLATE
from mcp_servers.filesystem_mcp import FileSystemMCP
from mcp_servers.database_mcp import DatabaseMCP
from mcp_servers.search_mcp import SearchMCP
from mcp_servers.email_mcp import EmailMCP
import config

client = Anthropic(api_key=config.ANTHROPIC_API_KEY)

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```")

def _parse_json(text: str) -> dict:
    """Parse JSON from Claude's response, stripping any markdown code fences."""
    m = _JSON_FENCE.search(text)
    return json.loads(m.group(1) if m else text)

async def node_ingest(state: AgentState) -> AgentState:
    fs = FileSystemMCP(state["contracts_dir"])
    return {**state, "pdf_files": await fs.list_pdfs()}

async def node_extract(state: AgentState) -> AgentState:
    fs = FileSystemMCP(state["contracts_dir"])
    db = DatabaseMCP(state["db_path"])
    extracted, errors = [], list(state.get("errors", []))
    for pdf_path in state["pdf_files"]:
        contract_id = os.path.splitext(os.path.basename(pdf_path))[0]
        try:
            # Skip Claude API call if this contract was already extracted
            if await db.contract_exists(contract_id):
                print(f"[extract] Skipping {contract_id} (already in DB)")
                continue
            text = await fs.read_pdf_text(pdf_path)
            r = client.messages.create(model=config.MODEL_NAME, max_tokens=1024,
                system=EXTRACTION_SYSTEM,
                messages=[{"role": "user", "content": text[:12000]}])
            data = _parse_json(r.content[0].text)
            data["id"] = contract_id
            data["raw_text"] = text[:2000]
            await db.upsert_contract(data)
            extracted.append(data)
            print(f"[extract] Extracted {contract_id}")
        except Exception as e:
            errors.append(f"{pdf_path}: {e}")
    return {**state, "extracted_contracts": extracted, "errors": errors}

async def node_check_renewals(state: AgentState) -> AgentState:
    db = DatabaseMCP(state["db_path"])
    today, flagged, seen = date.today(), [], set()
    for threshold in config.RENEWAL_THRESHOLDS:
        for c in await db.get_expiring_before((today + timedelta(days=threshold)).isoformat()):
            if c["id"] not in seen:
                seen.add(c["id"])
                days_left = (date.fromisoformat(c["expiry_date"]) - today).days
                flagged.append({**c, "days_left": days_left, "urgency": threshold})
    return {**state, "flagged_renewals": flagged}

async def node_benchmark(state: AgentState) -> AgentState:
    search = SearchMCP(api_key=config.SERP_API_KEY)
    benchmarks = {}
    for c in state["flagged_renewals"]:
        benchmarks[c["id"]] = await search.search(f"{c['category']} market price benchmark 2026")
    return {**state, "market_benchmarks": benchmarks}

async def node_draft_memos(state: AgentState) -> AgentState:
    memos_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "memos")
    os.makedirs(memos_dir, exist_ok=True)
    paths = []
    for c in state["flagged_renewals"]:
        fname = os.path.join(memos_dir, f"{c['id']}_renewal_memo.md")
        # Skip if memo already exists — re-run only if the file is missing
        if os.path.exists(fname):
            print(f"[draft_memos] Skipping {c['id']} (memo already exists)")
            paths.append(fname)
            continue
        bench = state["market_benchmarks"].get(c["id"], "No data.")
        r = client.messages.create(model=config.MODEL_NAME, max_tokens=1024,
            system=MEMO_SYSTEM,
            messages=[{"role": "user", "content": f"Contract:\n{json.dumps(c, indent=2)}\n\nMarket:\n{bench}"}])
        with open(fname, "w") as f:
            f.write(r.content[0].text)
        paths.append(fname)
        print(f"[draft_memos] Drafted memo for {c['id']}")
    return {**state, "memos": paths}

async def node_alert(state: AgentState) -> AgentState:
    emailer = EmailMCP()
    sent = []
    memo_paths = state.get("memos", [])
    memo_map = {os.path.splitext(os.path.basename(p))[0].replace("_renewal_memo", ""): p
                for p in memo_paths}
    for c in state["flagged_renewals"]:
        memo_file = os.path.basename(memo_map.get(c["id"], "")) or "N/A"
        body = ALERT_TEMPLATE.format(**c, memo_file=memo_file)
        subject = f"[Procurement Alert] {c['vendor']} — {c['days_left']}d to renewal"
        await emailer.send(to=config.ALERT_EMAIL_TO, subject=subject, body=body)
        sent.append(subject)
    return {**state, "alerts": sent}
