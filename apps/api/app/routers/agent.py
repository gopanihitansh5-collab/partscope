from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.deps import SessionDep
from src.agents import service as agent_service
from src.models import AgentRun
from src.monitoring.metrics import AGENT_RUNS
from src.schemas.agent import (
    AgentRunDetail,
    AgentRunOut,
    AgentRunRequest,
    FeedbackRequest,
    ToolRunOut,
)

router = APIRouter(tags=["agent"])


def _out(run: AgentRun) -> AgentRunOut:
    return AgentRunOut(
        run_id=run.run_id,
        query=run.query,
        status=run.status,
        intent=run.intent,
        response=run.response,
        trace=run.trace or [],
        error=run.error,
        latency_ms=run.latency_ms,
        created_at=run.created_at,
        finished_at=run.finished_at,
    )


@router.post("/agent/runs", response_model=AgentRunOut)
def create_run(request: AgentRunRequest, session: SessionDep) -> AgentRunOut:
    run = agent_service.run_agent(session, request)
    AGENT_RUNS.labels(run.status, run.intent or "unknown").inc()
    return _out(run)


@router.get("/agent/runs", response_model=list[AgentRunOut])
def list_runs(session: SessionDep, limit: int = Query(default=20, ge=1, le=100)) -> list[AgentRunOut]:
    return [_out(run) for run in agent_service.list_runs(session, limit=limit)]


@router.get("/agent/runs/{run_id}", response_model=AgentRunDetail)
def get_run(run_id: str, session: SessionDep) -> AgentRunDetail:
    run = agent_service.get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    tools = agent_service.get_tool_runs(session, run.id)
    return AgentRunDetail(
        **_out(run).model_dump(),
        tool_runs=[ToolRunOut.model_validate(t) for t in tools],
    )


@router.get("/agent/runs/{run_id}/events")
def stream_events(run_id: str, session: SessionDep) -> StreamingResponse:
    run = agent_service.get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    trace = run.trace or []
    status = run.status

    def generate():
        for event in trace:
            yield f"event: trace\ndata: {json.dumps(event)}\n\n"
        yield f"event: done\ndata: {json.dumps({'run_id': run_id, 'status': status})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/agent/runs/{run_id}/feedback")
def feedback(run_id: str, request: FeedbackRequest, session: SessionDep) -> dict:
    result = agent_service.add_feedback(session, run_id, request.rating, request.comment)
    if result is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return {"status": "recorded", "feedback_id": result.id}


@router.post("/agent/runs/{run_id}/cancel", response_model=AgentRunOut)
def cancel(run_id: str, session: SessionDep) -> AgentRunOut:
    run = agent_service.cancel_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    if run.status != "cancelled":
        raise HTTPException(status_code=409, detail=f"Run is already {run.status}")
    return _out(run)
