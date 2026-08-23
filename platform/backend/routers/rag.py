"""
Admin > RAG document management.

CONTRACT WITH PERSON 2 (Memory & RAG owner):
    rag/rag_pipeline.py's prep-task list already calls for an "add/remove
    document, changes reflected immediately" path. This router expects
    OperationalRAGPipeline to eventually expose:

        pipeline.add_document(title: str, content: str) -> None
        pipeline.remove_document(title: str) -> None

    Until those exist, this router still does something real — it keeps
    a durable record in the RagDocuments table (so the admin UI has a
    genuine, working add/remove flow to demo today) — but the change
    will NOT be reflected in what the RAG agent actually retrieves
    until Person 2's pipeline methods land. Every response says so
    explicitly via `indexed`, instead of silently pretending it worked
    end-to-end.

    Swap-over is designed to be a one-line change: as soon as the two
    methods above exist, `_get_pipeline()` picks them up automatically
    and `indexed` starts coming back true.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_connection

router = APIRouter(prefix="/api/admin/rag", tags=["admin:rag"])

_pipeline = None


def _get_pipeline():
    """Lazy singleton so importing this module doesn't force embedding
    model / vector store startup cost for routes that don't need it."""
    global _pipeline

    if _pipeline is None:
        from rag.rag_pipeline import OperationalRAGPipeline

        _pipeline = OperationalRAGPipeline()

    return _pipeline


class DocumentIn(BaseModel):
    title: str
    content: str
    source_path: str | None = None


@router.get("")
def list_documents():
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT doc_id, title, source_path, added_at
            FROM RagDocuments
            WHERE removed_at IS NULL
            ORDER BY added_at DESC
            """
        ).fetchall()

        return {"documents": [dict(row) for row in rows]}
    finally:
        conn.close()


@router.post("")
def add_document(doc: DocumentIn):
    conn = get_connection()

    try:
        cursor = conn.execute(
            """
            INSERT INTO RagDocuments (title, source_path, content)
            VALUES (?, ?, ?)
            """,
            (doc.title, doc.source_path, doc.content),
        )
        conn.commit()
        doc_id = cursor.lastrowid
    finally:
        conn.close()

    indexed = False
    try:
        pipeline = _get_pipeline()

        if hasattr(pipeline, "add_document"):
            pipeline.add_document(doc.title, doc.content)
            indexed = True
    except Exception:
        # RAG pipeline not wired for live add yet, or embedding
        # backend unavailable — the document is still durably saved
        # above; retrieval just won't see it yet.
        indexed = False

    return {"doc_id": doc_id, "indexed": indexed}


@router.delete("/{doc_id}")
def remove_document(doc_id: int):
    conn = get_connection()

    try:
        row = conn.execute(
            "SELECT title FROM RagDocuments WHERE doc_id = ?",
            (doc_id,),
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Document not found")

        conn.execute(
            "UPDATE RagDocuments SET removed_at = CURRENT_TIMESTAMP WHERE doc_id = ?",
            (doc_id,),
        )
        conn.commit()
    finally:
        conn.close()

    indexed = False
    try:
        pipeline = _get_pipeline()

        if hasattr(pipeline, "remove_document"):
            pipeline.remove_document(row["title"])
            indexed = True
    except Exception:
        indexed = False

    return {"doc_id": doc_id, "removed_from_index": indexed}
