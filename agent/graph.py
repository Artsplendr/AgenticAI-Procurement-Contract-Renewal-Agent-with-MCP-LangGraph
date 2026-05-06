from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.nodes import node_ingest, node_extract, node_check_renewals, node_benchmark, node_draft_memos, node_alert
from agent.checkpoints import should_alert

def build_graph():
    g = StateGraph(AgentState)
    g.add_node("ingest", node_ingest)
    g.add_node("extract", node_extract)
    g.add_node("check_renewals", node_check_renewals)
    g.add_node("benchmark", node_benchmark)
    g.add_node("draft_memos", node_draft_memos)
    g.add_node("alert", node_alert)
    g.set_entry_point("ingest")
    g.add_edge("ingest", "extract")
    g.add_edge("extract", "check_renewals")
    g.add_edge("check_renewals", "benchmark")
    g.add_edge("benchmark", "draft_memos")
    g.add_conditional_edges("draft_memos", should_alert, {"alert":"alert","draft_only":END,"end":END})
    g.add_edge("alert", END)
    return g.compile()
