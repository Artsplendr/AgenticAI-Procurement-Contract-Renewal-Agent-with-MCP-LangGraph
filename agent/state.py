from typing import TypedDict, List, Dict, Any, Optional

class ContractRecord(TypedDict):
    id: str; vendor: str; category: str; value: float; currency: str
    start_date: str; expiry_date: str; auto_renewal: bool
    sla_penalty: Optional[str]; price_escalation: Optional[str]; raw_text: str

class AgentState(TypedDict):
    contracts_dir: str; db_path: str
    pdf_files: List[str]
    extracted_contracts: List[ContractRecord]
    flagged_renewals: List[Dict[str, Any]]
    market_benchmarks: Dict[str, Any]
    alerts: List[str]; memos: List[str]; errors: List[str]
    human_approved: Optional[bool]
