"""LangGraph workflow that coordinates vision, graph, retrieval and forecasting."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from langgraph.graph import END, StateGraph

from src.agents.state import AgentState
from src.agents.tools import ToolError, Tools

COMPATIBILITY_KEYWORDS = {
    "compatible",
    "compatibility",
    "replacement",
    "replace",
    "alternative",
    "interchange",
    "fit",
    "supersede",
}
FORECAST_KEYWORDS = {
    "stock",
    "demand",
    "shortage",
    "forecast",
    "reorder",
    "inventory",
    "next month",
    "next quarter",
}
DOC_KEYWORDS = {"manual", "document", "specification", "torque", "procedure", "interval", "guide"}


def _event(node: str, status: str, started: float, detail: str | None = None) -> dict:
    return {
        "node": node,
        "status": status,
        "detail": detail,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "at": datetime.now(UTC).isoformat(),
    }


def validate_input(state: AgentState, tools: Tools) -> dict:
    started = time.perf_counter()
    query = (state.get("query") or "").strip()[:2000]
    errors: list[str] = []
    warnings: list[str] = []
    if not query and not state.get("image_id") and not state.get("part_id"):
        errors.append("Provide a query, an image_id or a part_id.")
    if state.get("image_id"):
        from pathlib import Path

        from src.common.config import settings

        if not (settings.upload_path / Path(state["image_id"]).name).exists():
            errors.append(f"Uploaded image '{state['image_id']}' was not found.")
    return {
        "query": query,
        "warnings": warnings,
        "errors": errors,
        "trace": [_event("validate_input", "error" if errors else "ok", started)],
    }


def classify_intent(state: AgentState, tools: Tools) -> dict:
    started = time.perf_counter()
    query = state.get("query", "").lower()
    if state.get("image_id"):
        intent = "identify"
    elif any(word in query for word in COMPATIBILITY_KEYWORDS):
        intent = "compatibility"
    elif any(word in query for word in FORECAST_KEYWORDS):
        intent = "forecast"
    elif any(word in query for word in DOC_KEYWORDS):
        intent = "documentation"
    else:
        intent = "search"
    return {"intent": intent, "trace": [_event("classify_intent", "ok", started, intent)]}


def plan_tasks(state: AgentState, tools: Tools) -> dict:
    started = time.perf_counter()
    intent = state.get("intent", "search")
    include_compatibility = state.get("include_compatibility", True)
    include_retrieval = state.get("include_retrieval", True)
    include_forecast = state.get("include_forecast", True)

    plan = ["resolve_catalog_part"]
    if state.get("image_id"):
        plan.insert(0, "identify_image")
    if include_compatibility or intent in {"compatibility", "identify"}:
        include_compatibility = True
        plan.append("rank_compatibilities")
    if include_retrieval or intent in {"documentation", "compatibility"}:
        include_retrieval = True
        plan.append("retrieve_evidence")
    if include_forecast or intent == "forecast":
        include_forecast = True
        plan.append("forecast_demand")
    plan.append("validate_evidence")
    plan.append("format_response")

    return {
        "plan": plan,
        "include_compatibility": include_compatibility,
        "include_retrieval": include_retrieval,
        "include_forecast": include_forecast,
        "trace": [_event("plan_tasks", "ok", started, " -> ".join(plan))],
    }


def route_after_plan(state: AgentState) -> str:
    if state.get("errors"):
        return "graph"
    if state.get("image_id"):
        return "vision"
    return "graph"


def vision_agent(state: AgentState, tools: Tools) -> dict:
    started = time.perf_counter()
    if not state.get("image_id"):
        return {"trace": [_event("vision_agent", "skipped", started)]}
    try:
        result = tools.identify(state["image_id"])
    except ToolError as exc:
        return {
            "errors": [str(exc)],
            "warnings": ["Image identification failed; continuing with text evidence."],
            "trace": [_event("vision_agent", "error", started, str(exc))],
        }

    update: dict[str, Any] = {
        "vision": result,
        "trace": [
            _event(
                "vision_agent",
                "ok",
                started,
                f"{len(result.get('top_candidates', []))} candidates, "
                f"confidence {result.get('confidence', 0):.3f}",
            )
        ],
    }
    if not state.get("part_id") and result.get("top_candidates"):
        top = result["top_candidates"][0]
        if top.get("part_id"):
            update["part_id"] = top["part_id"]
    if result.get("low_confidence"):
        update["warnings"] = [
            "Vision confidence is low; candidate parts require manual review."
        ]
    return update


def graph_agent(state: AgentState, tools: Tools) -> dict:
    started = time.perf_counter()
    try:
        source = tools.resolve_part(state.get("query", ""), state.get("part_id"))
    except ToolError as exc:
        return {
            "errors": [str(exc)],
            "candidates": [],
            "trace": [_event("graph_agent", "error", started, str(exc))],
        }

    update: dict[str, Any] = {
        "source_part": source,
        "part_id": source["part_id"],
    }
    candidates: list[dict] = []
    warnings: list[str] = []

    if state.get("include_compatibility", True):
        try:
            ranked = tools.rank_compatibilities(source["part_id"], limit=5)
            candidates = ranked.get("candidates", [])
        except ToolError as exc:
            warnings.append(f"Compatibility ranking failed: {exc}")

    if not candidates:
        try:
            fallback = tools.catalog_search(state.get("query", ""), limit=3)
            for item in fallback.get("items", []):
                if item["id"] == source["part_id"]:
                    continue
                candidates.append(
                    {
                        "part_id": item["id"],
                        "part_number": item["part_number"],
                        "name": item["name"],
                        "category": (item.get("category") or {}).get("name"),
                        "score": 0.35,
                        "relationship": "catalog_match",
                        "confidence": 0.35,
                        "source": "catalog-search",
                        "source_document_id": None,
                        "evidence": [],
                        "warnings": [
                            "No approved compatibility relationship; this is a catalog match only."
                        ],
                    }
                )
        except ToolError:
            pass

    update["candidates"] = candidates
    if not candidates:
        warnings.append("No compatible alternatives were found for this part.")
    update["warnings"] = warnings
    update["trace"] = [
        _event("graph_agent", "ok", started, f"{len(candidates)} ranked alternatives")
    ]
    return update


def retrieval_agent(state: AgentState, tools: Tools) -> dict:
    started = time.perf_counter()
    if not state.get("include_retrieval", True) or not state.get("query"):
        return {"trace": [_event("retrieval_agent", "skipped", started)]}
    try:
        result = tools.retrieve(state["query"], state.get("part_id"))
    except ToolError as exc:
        return {
            "warnings": ["Document retrieval failed; answer will rely on catalog evidence."],
            "trace": [_event("retrieval_agent", "error", started, str(exc))],
        }
    detail = (
        f"{len(result.get('citations', []))} citations, "
        f"grounded={result.get('grounded')}"
    )
    update: dict[str, Any] = {
        "retrieval": result,
        "trace": [_event("retrieval_agent", "ok", started, detail)],
    }
    if result.get("insufficient_evidence"):
        update["warnings"] = ["Documentation evidence was insufficient for a grounded answer."]
    return update


def forecast_agent(state: AgentState, tools: Tools) -> dict:
    started = time.perf_counter()
    if not state.get("include_forecast", True) or not state.get("part_id"):
        return {"trace": [_event("forecast_agent", "skipped", started)]}

    target_ids = [state["part_id"]]
    for candidate in state.get("candidates", [])[:2]:
        if candidate.get("part_id") and candidate["part_id"] not in target_ids:
            target_ids.append(candidate["part_id"])

    forecasts: list[dict] = []
    warnings: list[str] = []
    for part_id in target_ids:
        try:
            forecasts.append(tools.forecast(part_id))
        except ToolError as exc:
            warnings.append(f"Forecast failed for part {part_id}: {exc}")

    return {
        "forecasts": forecasts,
        "warnings": warnings,
        "trace": [
            _event("forecast_agent", "ok" if forecasts else "error", started, f"{len(forecasts)} forecasts")
        ],
    }


def evidence_validator(state: AgentState, tools: Tools) -> dict:
    started = time.perf_counter()
    candidates = state.get("candidates", [])
    retrieval = state.get("retrieval") or {}
    forecasts = {f["part_id"]: f for f in state.get("forecasts", [])}
    vision = state.get("vision") or {}

    warnings: list[str] = []
    validated: list[dict] = []
    for candidate in candidates:
        candidate = dict(candidate)
        candidate_warnings = list(candidate.get("warnings", []))
        has_source = candidate.get("source_document_id") is not None
        relationship = candidate.get("relationship")
        if not has_source and relationship not in {"supersedes", "replaces"}:
            candidate_warnings.append("No approved source document linked to this relationship.")
        candidate["citations"] = [
            citation
            for citation in retrieval.get("citations", [])
            if citation.get("document_id") == candidate.get("source_document_id")
        ]
        if not candidate["citations"] and retrieval.get("grounded"):
            candidate["citations"] = retrieval.get("citations", [])[:1]
        candidate["forecast"] = forecasts.get(candidate.get("part_id"))
        candidate["evidence_complete"] = bool(
            has_source and candidate["citations"] and candidate.get("forecast")
        )
        candidate["warnings"] = candidate_warnings
        validated.append(candidate)

    insufficient = not validated and not retrieval.get("grounded")
    confidence_parts = []
    if vision.get("confidence"):
        confidence_parts.append(float(vision["confidence"]))
    if validated:
        confidence_parts.append(float(validated[0].get("score", 0.0)))
    if retrieval.get("confidence"):
        confidence_parts.append(float(retrieval["confidence"]))
    confidence = round(sum(confidence_parts) / len(confidence_parts), 4) if confidence_parts else 0.0

    if not validated:
        warnings.append("No ranked alternatives were produced; refusal is recommended.")
    if retrieval.get("insufficient_evidence"):
        warnings.append("The documentation answer is a refusal: evidence was insufficient.")
    if validated and not any(c["evidence_complete"] for c in validated):
        warnings.append("No alternative has complete graph + document + forecast evidence.")

    evidence = {
        "confidence": confidence,
        "insufficient_evidence": insufficient,
        "evidence_complete": any(c["evidence_complete"] for c in validated),
        "candidates": validated,
    }
    return {
        "evidence": evidence,
        "candidates": validated,
        "warnings": warnings,
        "trace": [
            _event(
                "evidence_validator",
                "ok" if not insufficient else "insufficient",
                started,
                f"confidence {confidence:.3f}",
            )
        ],
    }


def response_formatter(state: AgentState, tools: Tools) -> dict:
    started = time.perf_counter()
    source = state.get("source_part")
    vision = state.get("vision")
    retrieval = state.get("retrieval") or {}
    evidence = state.get("evidence", {})
    candidates = state.get("candidates", [])

    alternatives = []
    for candidate in candidates[:5]:
        alternatives.append(
            {
                "part_id": candidate.get("part_id"),
                "part_number": candidate.get("part_number"),
                "name": candidate.get("name"),
                "category": candidate.get("category"),
                "score": candidate.get("score"),
                "relationship": candidate.get("relationship"),
                "confidence": candidate.get("confidence"),
                "source": candidate.get("source"),
                "evidence_path": candidate.get("evidence", []),
                "citations": candidate.get("citations", []),
                "forecast": candidate.get("forecast"),
                "evidence_complete": candidate.get("evidence_complete", False),
                "warnings": candidate.get("warnings", []),
            }
        )

    if evidence.get("insufficient_evidence"):
        summary = (
            "Insufficient evidence to recommend a replacement. No approved compatibility, "
            "documentation and forecast evidence could be combined for this request."
        )
    else:
        pieces = []
        if source:
            pieces.append(f"Identified {source['part_number']} ({source['name']}).")
        if alternatives:
            pieces.append(f"Ranked {len(alternatives)} compatible alternatives with evidence.")
        if retrieval.get("grounded"):
            pieces.append("Grounded documentation answer available with citations.")
        if evidence.get("confidence", 0) < 0.5:
            pieces.append("Overall confidence is low; manual review is required.")
        summary = " ".join(pieces)

    response = {
        "summary": summary,
        "source_part": source,
        "vision": vision,
        "alternatives": alternatives,
        "documentation": {
            "answer": retrieval.get("answer"),
            "citations": retrieval.get("citations", []),
            "grounded": retrieval.get("grounded", False),
            "insufficient_evidence": retrieval.get("insufficient_evidence", True),
            "confidence": retrieval.get("confidence", 0.0),
        },
        "confidence": evidence.get("confidence", 0.0),
        "insufficient_evidence": evidence.get("insufficient_evidence", True),
        "evidence_complete": evidence.get("evidence_complete", False),
        "warnings": list(dict.fromkeys(state.get("warnings", []))),
        "plan": state.get("plan", []),
        "intent": state.get("intent"),
        "synthetic_data": True,
    }
    return {
        "response": response,
        "warnings": [],
        "trace": [_event("response_formatter", "ok", started)],
    }


def build_graph(tools: Tools):
    graph = StateGraph(AgentState)
    graph.add_node("validate_input", lambda s: validate_input(s, tools))
    graph.add_node("classify_intent", lambda s: classify_intent(s, tools))
    graph.add_node("plan_tasks", lambda s: plan_tasks(s, tools))
    graph.add_node("vision_agent", lambda s: vision_agent(s, tools))
    graph.add_node("graph_agent", lambda s: graph_agent(s, tools))
    graph.add_node("retrieval_agent", lambda s: retrieval_agent(s, tools))
    graph.add_node("forecast_agent", lambda s: forecast_agent(s, tools))
    graph.add_node("evidence_validator", lambda s: evidence_validator(s, tools))
    graph.add_node("response_formatter", lambda s: response_formatter(s, tools))

    graph.set_entry_point("validate_input")
    graph.add_edge("validate_input", "classify_intent")
    graph.add_edge("classify_intent", "plan_tasks")
    graph.add_conditional_edges(
        "plan_tasks",
        route_after_plan,
        {"vision": "vision_agent", "graph": "graph_agent"},
    )
    graph.add_edge("vision_agent", "graph_agent")
    graph.add_edge("graph_agent", "retrieval_agent")
    graph.add_edge("retrieval_agent", "forecast_agent")
    graph.add_edge("forecast_agent", "evidence_validator")
    graph.add_edge("evidence_validator", "response_formatter")
    graph.add_edge("response_formatter", END)
    return graph.compile()


def initial_state(
    query: str,
    part_id: int | None,
    image_id: str | None,
    include_forecast: bool,
    include_retrieval: bool,
    include_compatibility: bool,
) -> AgentState:
    return {
        "query": query,
        "part_id": part_id,
        "image_id": image_id,
        "include_forecast": include_forecast,
        "include_retrieval": include_retrieval,
        "include_compatibility": include_compatibility,
        "warnings": [],
        "errors": [],
        "trace": [],
        "candidates": [],
        "forecasts": [],
    }
