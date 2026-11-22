"""Typed state for the LangGraph agent workflow."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class AgentState(TypedDict, total=False):
    query: str
    part_id: int | None
    image_id: str | None
    include_forecast: bool
    include_retrieval: bool
    include_compatibility: bool

    intent: str
    plan: list[str]
    vision: dict | None
    source_part: dict | None
    candidates: list[dict]
    retrieval: dict | None
    forecasts: list[dict]
    evidence: dict
    response: dict | None

    warnings: Annotated[list[str], operator.add]
    errors: Annotated[list[str], operator.add]
    trace: Annotated[list[dict], operator.add]
