"""Agent run lifecycle: execution, persistence, retrieval and feedback."""

from __future__ import annotations

import time
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.agents.tools import Tools
from src.agents.workflow import build_graph, initial_state
from src.common.logging import get_logger
from src.common.utils import utcnow
from src.models import AgentRun, Feedback, ToolRun
from src.schemas.agent import AgentRunRequest

log = get_logger("agent")


def run_agent(session: Session, request: AgentRunRequest) -> AgentRun:
    run = AgentRun(
        run_id=str(uuid.uuid4()),
        query=request.query,
        image_path=request.image_id,
        status="running",
        trace=[],
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    started = time.perf_counter()
    try:
        tools = Tools(session, run.id)
        graph = build_graph(tools)
        state = initial_state(
            query=request.query,
            part_id=request.part_id,
            image_id=request.image_id,
            include_forecast=request.include_forecast,
            include_retrieval=request.include_retrieval,
            include_compatibility=request.include_compatibility,
        )
        final = graph.invoke(state, config={"recursion_limit": 30})
        errors = final.get("errors", [])
        run.intent = final.get("intent")
        run.response = final.get("response")
        run.trace = final.get("trace", [])
        run.error = "; ".join(errors) if errors else None
        run.status = "completed" if final.get("response") else "failed"
    except Exception as exc:  # noqa: BLE001 - persisted as run failure
        log.exception("agent_run_failed", run_id=run.run_id)
        run.status = "failed"
        run.error = str(exc)
        run.trace = [
            *run.trace,
            {
                "node": "workflow",
                "status": "error",
                "detail": str(exc),
                "latency_ms": None,
                "at": utcnow().isoformat(),
            },
        ]

    run.latency_ms = round((time.perf_counter() - started) * 1000, 2)
    run.finished_at = utcnow()
    session.commit()
    session.refresh(run)
    return run


def get_run(session: Session, run_id: str) -> AgentRun | None:
    return session.scalar(select(AgentRun).where(AgentRun.run_id == run_id))


def get_tool_runs(session: Session, agent_run_id: int) -> list[ToolRun]:
    return list(
        session.scalars(
            select(ToolRun).where(ToolRun.agent_run_id == agent_run_id).order_by(ToolRun.id)
        )
    )


def list_runs(session: Session, limit: int = 20) -> list[AgentRun]:
    return list(session.scalars(select(AgentRun).order_by(AgentRun.id.desc()).limit(limit)))


def add_feedback(
    session: Session, run_id: str, rating: int, comment: str | None
) -> Feedback | None:
    run = get_run(session, run_id)
    if run is None:
        return None
    feedback = Feedback(agent_run_id=run.id, rating=rating, comment=comment)
    session.add(feedback)
    session.commit()
    session.refresh(feedback)
    return feedback


def cancel_run(session: Session, run_id: str) -> AgentRun | None:
    run = get_run(session, run_id)
    if run is None:
        return None
    if run.status == "running":
        run.status = "cancelled"
        run.finished_at = utcnow()
        session.commit()
        session.refresh(run)
    return run
