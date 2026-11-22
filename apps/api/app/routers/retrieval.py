from __future__ import annotations

from fastapi import APIRouter

from app.deps import SessionDep
from src.retrieval import service as retrieval_service
from src.schemas.retrieval import (
    AnswerRequest,
    AnswerResponse,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
)

router = APIRouter(tags=["retrieval"])


@router.post("/retrieval/search", response_model=RetrievalSearchResponse)
def search(request: RetrievalSearchRequest, session: SessionDep) -> RetrievalSearchResponse:
    return retrieval_service.search(session, request)


@router.post("/retrieval/answer", response_model=AnswerResponse)
def answer(request: AnswerRequest, session: SessionDep) -> AnswerResponse:
    return retrieval_service.answer(session, request)
