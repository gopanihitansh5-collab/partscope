"""Typed, independently testable tools used by the agent workflow.

Every tool call is persisted as a ``ToolRun`` with its input, output, status and
latency, which makes agent behaviour reproducible and auditable.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from sqlalchemy.orm import Session

from src.catalog import service as catalog_service
from src.common.config import settings
from src.forecasting import service as forecast_service
from src.graph import service as graph_service
from src.models import Part, ToolRun
from src.retrieval import service as retrieval_service
from src.schemas.catalog import PartSearchRequest
from src.schemas.compatibility import CompatibilityRankRequest
from src.schemas.retrieval import AnswerRequest
from src.vision import service as vision_service

PART_NUMBER_RE = re.compile(r"\b[A-Z]{2,6}\d{3,6}-[A-Z0-9][A-Z0-9-]*\b")


class ToolError(RuntimeError):
    pass


class Tools:
    def __init__(self, session: Session, agent_run_id: int):
        self.session = session
        self.agent_run_id = agent_run_id

    def _record(
        self, name: str, payload: dict, started: float, status: str, output: dict, error: str | None
    ) -> None:
        self.session.add(
            ToolRun(
                agent_run_id=self.agent_run_id,
                tool_name=name,
                status=status,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                input=payload,
                output=output,
                error=error,
            )
        )
        self.session.commit()

    def _run(self, name: str, payload: dict, fn):
        started = time.perf_counter()
        try:
            output = fn()
            self._record(name, payload, started, "ok", output, None)
            return output
        except Exception as exc:
            self._record(name, payload, started, "failed", {}, str(exc))
            raise ToolError(f"{name} failed: {exc}") from exc

    def identify(self, image_id: str) -> dict:
        path = (settings.upload_path / Path(image_id).name).resolve()
        if not str(path).startswith(str(settings.upload_path.resolve())):
            raise ToolError("Invalid image id.")
        if not path.exists():
            raise ToolError(f"Uploaded image '{image_id}' was not found.")

        def call() -> dict:
            response = vision_service.identify(self.session, path)
            return response.model_dump(mode="json")

        return self._run("vision.identify", {"image_id": image_id}, call)

    def resolve_part(self, query: str, part_id: int | None = None) -> dict:
        def call() -> dict:
            part: Part | None = None
            if part_id:
                part = self.session.get(Part, part_id)
            if part is None:
                match = PART_NUMBER_RE.search(query.upper())
                if match:
                    part = catalog_service.get_by_number(self.session, match.group(0))
            if part is None:
                result = catalog_service.search(
                    self.session, PartSearchRequest(query=query, limit=5)
                )
                if result.items:
                    part = self.session.get(Part, result.items[0].id)
            if part is None:
                raise ToolError("No catalog part matched the request.")
            return {
                "part_id": part.id,
                "part_number": part.part_number,
                "name": part.name,
                "category": part.category.name if part.category else None,
                "status": part.status,
                "criticality": part.criticality,
            }

        return self._run("catalog.resolve_part", {"query": query, "part_id": part_id}, call)

    def catalog_search(self, query: str, limit: int = 5) -> dict:
        def call() -> dict:
            result = catalog_service.search(
                self.session, PartSearchRequest(query=query, limit=limit)
            )
            return result.model_dump(mode="json")

        return self._run("catalog.search", {"query": query, "limit": limit}, call)

    def rank_compatibilities(self, part_id: int, limit: int = 5) -> dict:
        def call() -> dict:
            result = graph_service.rank(
                self.session, CompatibilityRankRequest(part_id=part_id, limit=limit)
            )
            return result.model_dump(mode="json")

        return self._run("graph.rank", {"part_id": part_id, "limit": limit}, call)

    def retrieve(self, query: str, part_id: int | None) -> dict:
        def call() -> dict:
            result = retrieval_service.answer(
                self.session, AnswerRequest(query=query, part_id=part_id, top_k=6)
            )
            return result.model_dump(mode="json")

        return self._run("retrieval.answer", {"query": query, "part_id": part_id}, call)

    def forecast(self, part_id: int, horizon_days: int = 30) -> dict:
        def call() -> dict:
            result = forecast_service.forecast_part(
                self.session, part_id, horizon_days=horizon_days
            )
            return result.model_dump(mode="json")

        return self._run("forecast.demand", {"part_id": part_id, "horizon_days": horizon_days}, call)
