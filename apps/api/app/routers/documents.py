from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.deps import SessionDep
from src.models import Category, Document, DocumentChunk
from src.retrieval import service as retrieval_service
from src.schemas.retrieval import IndexRequest, IndexResponse

router = APIRouter(tags=["documents"])


@router.get("/documents")
def list_documents(
    session: SessionDep,
    category: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict]:
    stmt = (
        select(Document, func.count(DocumentChunk.id), Category.name)
        .outerjoin(DocumentChunk, DocumentChunk.document_id == Document.id)
        .outerjoin(Category, Document.category_id == Category.id)
        .group_by(Document.id, Category.name)
        .order_by(Document.title)
        .limit(limit)
    )
    if category:
        stmt = stmt.join(Category, Document.category_id == Category.id).where(
            (Category.slug == category) | (Category.name.ilike(f"%{category}%"))
        )
    rows = session.execute(stmt).all()
    return [
        {
            "id": doc.id,
            "title": doc.title,
            "doc_type": doc.doc_type,
            "category": category_name,
            "source": doc.source,
            "approved": doc.approved,
            "chunks": chunk_count,
            "created_at": doc.created_at.isoformat(),
        }
        for doc, chunk_count, category_name in rows
    ]


@router.get("/documents/{document_id}")
def get_document(document_id: int, session: SessionDep) -> dict:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    chunks = list(
        session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.ordinal)
        )
    )
    return {
        "id": document.id,
        "title": document.title,
        "doc_type": document.doc_type,
        "source": document.source,
        "approved": document.approved,
        "chunks": [
            {
                "id": chunk.id,
                "page": chunk.page,
                "section": chunk.section,
                "text": chunk.text,
                "token_count": chunk.token_count,
            }
            for chunk in chunks
        ],
    }


@router.post("/documents/index", response_model=IndexResponse)
def index_documents(request: IndexRequest, session: SessionDep) -> IndexResponse:
    return retrieval_service.build_index(session)
