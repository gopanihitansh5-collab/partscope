from __future__ import annotations

from fastapi import APIRouter

from app.deps import SessionDep
from src.graph import service as graph_service
from src.schemas.compatibility import (
    CompatibilityRankRequest,
    CompatibilityRankResponse,
    VerifyRequest,
    VerifyResponse,
)

router = APIRouter(tags=["compatibility"])


@router.post("/compatibility/rank", response_model=CompatibilityRankResponse)
def rank(request: CompatibilityRankRequest, session: SessionDep) -> CompatibilityRankResponse:
    return graph_service.rank(session, request)


@router.post("/compatibility/verify", response_model=VerifyResponse)
def verify(request: VerifyRequest, session: SessionDep) -> VerifyResponse:
    return graph_service.verify(session, request.part_id, request.candidate_part_id)
