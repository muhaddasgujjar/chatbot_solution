from fastapi import APIRouter

from app.core.metrics import snapshot

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard")
def analytics_dashboard():
    """Aggregated metrics for the operator dashboard (latency, errors, handoff rate by segment)."""
    return snapshot()


@router.get("/kb-stats")
def kb_stats():
    """Return KB chunk counts from ChromaDB — total and by role_access."""
    from app.core.retrieval import _collection
    try:
        total = _collection.count()
        by_role: dict[str, int] = {}
        if total > 0:
            result = _collection.get(include=["metadatas"])
            for meta in (result.get("metadatas") or []):
                role = str(meta.get("role_access", "all"))
                by_role[role] = by_role.get(role, 0) + 1
        return {"total_chunks": total, "by_role": by_role, "status": "ok"}
    except Exception as exc:
        return {"total_chunks": 0, "by_role": {}, "status": f"error: {exc}"}
