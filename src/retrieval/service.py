"""Graph-aware retrieval and grounded answer construction.

Retrieval is hybrid: lexical similarity (TF-IDF cosine) plus entity overlap and
graph proximity (document/part/category links). Answers are extractive and
citation-backed. When evidence is weak the service refuses instead of
generating a compatibility or stock claim.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.common.config import settings
from src.common.utils import clamp
from src.models import Category, Compatibility, Document, DocumentChunk, Part
from src.retrieval.chunking import split_sentences
from src.schemas.retrieval import (
    AnswerRequest,
    AnswerResponse,
    Citation,
    IndexResponse,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
    RetrievedChunk,
)

PART_NUMBER_RE = re.compile(r"\b[A-Z]{2,6}\d{3,6}-[A-Z0-9][A-Z0-9-]*\b")

VECTOR_WEIGHT = 0.62
ENTITY_WEIGHT = 0.23
GRAPH_WEIGHT = 0.15


@dataclass
class ChunkRecord:
    chunk_id: int
    document_id: int
    document_title: str
    doc_type: str
    category_id: int | None
    page: int
    section: str | None
    text: str
    source: str


@dataclass
class RetrievalIndex:
    vectorizer: TfidfVectorizer
    matrix: object
    records: list[ChunkRecord]
    signature: tuple[int, int]
    created_at: str

    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "vectorizer": self.vectorizer,
                "matrix": self.matrix,
                "records": self.records,
                "signature": self.signature,
                "created_at": self.created_at,
            },
            directory / "index.joblib",
        )
        (directory / "metadata.json").write_text(
            json.dumps(
                {
                    "created_at": self.created_at,
                    "chunks": len(self.records),
                    "vocab_size": len(self.vectorizer.vocabulary_),
                    "strategy": "tfidf-word-ngram(1,2) + entity + graph rerank",
                    "signature": list(self.signature),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return directory / "index.joblib"

    @classmethod
    def load(cls, directory: Path) -> RetrievalIndex:
        payload = joblib.load(directory / "index.joblib")
        return cls(
            vectorizer=payload["vectorizer"],
            matrix=payload["matrix"],
            records=payload["records"],
            signature=tuple(payload["signature"]),
            created_at=payload["created_at"],
        )


_cache: dict[str, RetrievalIndex] = {}


def index_dir() -> Path:
    return settings.artifact_path / "retrieval"


def _corpus_signature(session: Session) -> tuple[int, int]:
    count, max_id = session.execute(
        select(func.count(DocumentChunk.id), func.coalesce(func.max(DocumentChunk.id), 0))
    ).one()
    return int(count), int(max_id)


def build_index(session: Session) -> IndexResponse:
    started = time.perf_counter()
    rows = session.execute(
        select(DocumentChunk, Document)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(Document.approved.is_(True))
        .order_by(DocumentChunk.id)
    ).all()

    records = [
        ChunkRecord(
            chunk_id=chunk.id,
            document_id=doc.id,
            document_title=doc.title,
            doc_type=doc.doc_type,
            category_id=doc.category_id,
            page=chunk.page,
            section=chunk.section,
            text=chunk.text,
            source=doc.source,
        )
        for chunk, doc in rows
    ]
    if not records:
        raise ValueError("No approved document chunks to index. Run the seed script first.")

    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        min_df=1,
        sublinear_tf=True,
    )
    matrix = vectorizer.fit_transform([r.text for r in records])

    index = RetrievalIndex(
        vectorizer=vectorizer,
        matrix=matrix,
        records=records,
        signature=_corpus_signature(session),
        created_at=datetime.now(UTC).isoformat(),
    )
    index.save(index_dir())
    _cache.clear()
    _cache[str(index_dir())] = index

    return IndexResponse(
        documents=len({r.document_id for r in records}),
        chunks=len(records),
        vocab_size=len(vectorizer.vocabulary_),
        artifact_path=str(index_dir() / "index.joblib"),
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
    )


def _ensure_index(session: Session) -> RetrievalIndex:
    directory = index_dir()
    signature = _corpus_signature(session)
    cached = _cache.get(str(directory))
    if cached and cached.signature == signature:
        return cached

    path = directory / "index.joblib"
    if path.exists():
        try:
            loaded = RetrievalIndex.load(directory)
            if loaded.signature == signature:
                _cache[str(directory)] = loaded
                return loaded
        except Exception:
            pass

    build_index(session)
    return _cache[str(directory)]


def extract_entities(session: Session, query: str, part_id: int | None = None) -> dict:
    upper = query.upper()
    part_numbers = set(PART_NUMBER_RE.findall(upper))
    parts: list[Part] = []
    if part_numbers:
        parts = list(session.scalars(select(Part).where(Part.part_number.in_(part_numbers))))
    if part_id:
        part = session.get(Part, part_id)
        if part:
            parts.append(part)
            part_numbers.add(part.part_number)

    categories = {
        c.id: c
        for c in session.scalars(select(Category))
        if c.name.lower() in query.lower() or c.slug in query.lower()
    }
    if not categories and parts:
        for part in parts:
            if part.category_id:
                category = session.get(Category, part.category_id)
                if category:
                    categories[category.id] = category

    linked_documents: set[int] = set()
    if parts:
        linked_documents = set(
            session.scalars(
                select(Compatibility.source_document_id).where(
                    Compatibility.part_id.in_([p.id for p in parts]),
                    Compatibility.source_document_id.is_not(None),
                )
            )
        )

    return {
        "part_numbers": part_numbers,
        "part_ids": {p.id for p in parts},
        "category_ids": set(categories),
        "linked_documents": linked_documents,
    }


def _query_tokens(query: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", query.lower()) if len(t) > 2}


def _entity_score(text: str, tokens: set[str], part_numbers: set[str]) -> float:
    if not tokens and not part_numbers:
        return 0.0
    lowered = text.lower()
    chunk_tokens = {t for t in re.split(r"[^a-z0-9]+", lowered) if len(t) > 2}
    token_overlap = len(tokens & chunk_tokens) / max(1, len(tokens))
    part_hit = 1.0 if any(pn.lower() in lowered for pn in part_numbers) else 0.0
    return clamp(0.7 * token_overlap + 0.3 * part_hit)


def search(
    session: Session,
    request: RetrievalSearchRequest,
    extra_part_ids: set[int] | None = None,
) -> RetrievalSearchResponse:
    started = time.perf_counter()
    index = _ensure_index(session)
    entities = extract_entities(session, request.query, request.part_id)
    if extra_part_ids:
        entities["part_ids"] |= extra_part_ids

    vector = index.vectorizer.transform([request.query])
    similarities = cosine_similarity(vector, index.matrix).ravel()

    tokens = _query_tokens(request.query)
    scored: list[tuple[float, float, float, float, ChunkRecord]] = []
    max_graph = 1.0
    for record, vector_score in zip(index.records, similarities, strict=False):
        if request.approved_only and record.source == "":
            continue
        if request.category:
            category = session.get(Category, record.category_id) if record.category_id else None
            if not category or (
                category.slug != request.category and category.name.lower() != request.category.lower()
            ):
                continue
        if request.part_id and record.document_id in entities["linked_documents"]:
            graph = 1.0
        elif request.part_id and record.category_id in entities["category_ids"]:
            graph = 0.6
        elif record.category_id in entities["category_ids"]:
            graph = 0.45
        elif record.document_id in entities["linked_documents"]:
            graph = 0.8
        elif any(pn.lower() in record.text.lower() for pn in entities["part_numbers"]):
            graph = 0.7
        else:
            graph = 0.0

        entity = _entity_score(record.text, tokens, entities["part_numbers"])
        combined = VECTOR_WEIGHT * float(vector_score) + ENTITY_WEIGHT * entity + GRAPH_WEIGHT * graph
        if combined <= 0:
            continue
        scored.append((combined, float(vector_score), entity, graph, record))
        max_graph = max(max_graph, graph)

    scored.sort(key=lambda item: (-item[0], item[4].chunk_id))
    top = scored[: request.top_k]

    chunks = [
        RetrievedChunk(
            chunk_id=record.chunk_id,
            document_id=record.document_id,
            document_title=record.document_title,
            doc_type=record.doc_type,
            page=record.page,
            section=record.section,
            text=record.text,
            score=round(combined, 4),
            vector_score=round(vector_score, 4),
            entity_score=round(entity, 4),
            graph_score=round(graph, 4),
            source=record.source,
        )
        for combined, vector_score, entity, graph, record in top
    ]

    return RetrievalSearchResponse(
        query=request.query,
        chunks=chunks,
        total=len(chunks),
        strategy="hybrid: tfidf cosine + entity overlap + graph proximity",
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
    )


def _best_sentences(text: str, tokens: set[str], limit: int = 2) -> list[str]:
    sentences = split_sentences(text)
    if not sentences:
        return []
    scored = []
    for sentence in sentences:
        sentence_tokens = {t for t in re.split(r"[^a-z0-9]+", sentence.lower()) if len(t) > 2}
        overlap = len(tokens & sentence_tokens)
        length_penalty = 1.0 if 8 <= len(sentence.split()) <= 40 else 0.6
        scored.append((overlap * length_penalty, sentence))
    scored.sort(key=lambda item: -item[0])
    chosen = [s for _, s in scored[:limit]]
    ordered = [s for s in sentences if s in chosen]
    return ordered or chosen


def answer(session: Session, request: AnswerRequest) -> AnswerResponse:
    result = search(session, request)
    tokens = _query_tokens(request.query)

    if not result.chunks:
        return AnswerResponse(
            query=request.query,
            answer=(
                "Insufficient evidence. No approved document chunk matched this question, so "
                "the platform will not infer compatibility, fitment or stock information."
            ),
            citations=[],
            confidence=0.0,
            grounded=False,
            insufficient_evidence=True,
            warnings=["No approved evidence was retrieved."],
        )

    top = result.chunks[0]
    if top.score < settings.retrieval_min_score:
        return AnswerResponse(
            query=request.query,
            answer=(
                "Insufficient evidence. The closest approved passages scored below the "
                "confidence threshold; request engineering review instead of assuming "
                "interchangeability."
            ),
            citations=[],
            confidence=round(clamp(top.score / 0.55), 4),
            grounded=False,
            insufficient_evidence=True,
            warnings=[f"Top retrieval score {top.score:.3f} is below the threshold."],
            chunks=result.chunks,
        )

    used = [c for c in result.chunks[:3] if c.score >= settings.retrieval_min_score * 0.6]
    bullets: list[str] = []
    citations: list[Citation] = []
    for number, chunk in enumerate(used, start=1):
        sentences = _best_sentences(chunk.text, tokens, limit=2)
        if not sentences:
            continue
        bullets.append(f"- {' '.join(sentences)} [{number}]")
        citations.append(
            Citation(
                document_id=chunk.document_id,
                document_title=chunk.document_title,
                page=chunk.page,
                section=chunk.section,
                chunk_id=chunk.chunk_id,
                score=chunk.score,
            )
        )

    if not bullets:
        return AnswerResponse(
            query=request.query,
            answer="Insufficient evidence. Retrieved chunks did not contain an extractable answer.",
            citations=[],
            confidence=0.0,
            grounded=False,
            insufficient_evidence=True,
            warnings=["Chunks were retrieved but no supported sentence could be extracted."],
            chunks=result.chunks,
        )

    confidence = round(clamp(used[0].score / 0.55), 4)
    warnings: list[str] = []
    if confidence < 0.45:
        warnings.append("Confidence is low; confirm the part number against the machine serial.")
    if not any(c.document_title for c in citations):
        warnings.append("Citation titles are missing.")

    header = (
        "Grounded answer from approved documentation. Each statement is extracted from the "
        "cited passage; nothing is generated beyond the evidence.\n\n"
    )
    footer = (
        "\n\nCitations: "
        + "; ".join(
            f"[{i}] {c.document_title}, page {c.page}"
            + (f", section '{c.section}'" if c.section else "")
            for i, c in enumerate(citations, start=1)
        )
    )

    return AnswerResponse(
        query=request.query,
        answer=header + "\n".join(bullets) + footer,
        citations=citations,
        confidence=confidence,
        grounded=True,
        insufficient_evidence=False,
        warnings=warnings,
        chunks=result.chunks,
    )
