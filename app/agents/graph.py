from __future__ import annotations

from app.agents.state import TradeState


def _execute_stub(state: TradeState) -> dict:
    # Week 7 replaces this with the Robinhood place_equity_order mapping.
    return {"order": {"status": "stub", "_stub": True}}


def _after_critic(state: TradeState) -> str:
    v = (state.get("critic_verdict") or {}).get("verdict")
    return "guardrail" if v == "accept" else "END"


def _after_guardrail(state: TradeState) -> str:
    passed = (state.get("guardrail") or {}).get("passed", False)
    # The tier gate: only the owner (execution_enabled=True) may reach execute.
    if passed and state.get("execution_enabled"):
        return "execute"
    return "END"


def build_graph():
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import END, START, StateGraph

    from app.agents.nodes import critic_node, guardrail_node, hypothesis_node, research_node

    g = StateGraph(TradeState)
    g.add_node("research", research_node)
    g.add_node("hypothesis", hypothesis_node)
    g.add_node("critic", critic_node)
    g.add_node("guardrail", guardrail_node)
    g.add_node("execute", _execute_stub)       # Week 7

    g.add_edge(START, "research")
    g.add_edge("research", "hypothesis")
    g.add_edge("hypothesis", "critic")
    g.add_conditional_edges("critic", _after_critic, {"guardrail": "guardrail", "END": END})
    g.add_conditional_edges("guardrail", _after_guardrail, {"execute": "execute", "END": END})
    g.add_edge("execute", END)

    # MemorySaver persists state per thread_id so a paused run can be resumed (Week 7).
    # interrupt_before=["execute"] is the human-approval pause — the graph stops BEFORE
    # execute and waits for graph.invoke(None, config=...) after the owner approves.
    return g.compile(checkpointer=MemorySaver(), interrupt_before=["execute"])
