from agent.state import AgentState

def should_alert(state: AgentState) -> str:
    if not state.get("flagged_renewals"): return "end"
    urgent = [c for c in state["flagged_renewals"] if c["days_left"] <= 30]
    return "alert" if urgent else "draft_only"
