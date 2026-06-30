from __future__ import annotations

import uuid

from app.agents.state import TradeState

from app.models import User


def _execute_stub(state: TradeState) -> dict:
    # Week 7 replaces this with the Robinhood place_equity_order mapping.
    return {"order": {"status": "stub", "_stub": True}}


def _after_critic(state: TradeState) -> str:
    # Accept -> run guardrails; reject -> straight to logging (still recorded). Either way
    # the run reaches log_node, so every decision lands in the dashboard reasoning trail.
    v = (state.get("critic_verdict") or {}).get("verdict")
    return "guardrail" if v == "accept" else "log"


def _after_log(state: TradeState) -> str:
    passed = (state.get("guardrail") or {}).get("passed", False)
    # The tier gate: only the owner (execution_enabled=True) may reach execute, and only
    # once the guardrails passed. Rejected runs have no guardrail -> passed False -> END.
    if passed and state.get("execution_enabled"):
        return "execute"
    return "END"


def build_graph():
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import END, START, StateGraph

    from app.agents.nodes import (
        critic_node,
        guardrail_node,
        hypothesis_node,
        log_node,
        research_node,
    )

    g = StateGraph(TradeState)
    g.add_node("research", research_node)
    g.add_node("hypothesis", hypothesis_node)
    g.add_node("critic", critic_node)
    g.add_node("guardrail", guardrail_node)
    g.add_node("log", log_node)                # writes the Decision record for EVERY run
    g.add_node("execute", _execute_stub)       # Week 7

    g.add_edge(START, "research")
    g.add_edge("research", "hypothesis")
    g.add_edge("hypothesis", "critic")
    g.add_conditional_edges("critic", _after_critic, {"guardrail": "guardrail", "log": "log"})
    g.add_edge("guardrail", "log")             # accept path logs after the guardrail result
    g.add_conditional_edges("log", _after_log, {"execute": "execute", "END": END})
    g.add_edge("execute", END)

    # MemorySaver persists state per thread_id so a paused run can be resumed (Week 7).
    # interrupt_before=["execute"] is the human-approval pause — the graph stops BEFORE
    # execute and waits for graph.invoke(None, config=...) after the owner approves.
    return g.compile(checkpointer=MemorySaver(), interrupt_before=["execute"])


def run_graph(
    ticker: str,
    user: User,
    *,
    query: str | None = None,
    decision_id: str | None = None,
) -> dict:
    """Assemble the initial TradeState for `user` and run the graph to its first stop.

    The Week-4 contract is frozen — `execution_enabled` is *derived* from the user's role
    via execution_enabled_for, never set by hand. Public tier ends at END; owner tier pauses
    at interrupt_before=["execute"] for the Week-7 approval gate.
    """
    from app.models import execution_enabled_for

    decision_id = decision_id or str(uuid.uuid4())
    state: TradeState = {
        "ticker": ticker,
        "execution_enabled": execution_enabled_for(user),
        "decision_id": decision_id,
    }
    if query is not None:
        state["query"] = query

    graph = build_graph()
    cfg = {"configurable": {"thread_id": decision_id}}
    return graph.invoke(state, config=cfg)
