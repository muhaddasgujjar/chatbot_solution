from fastapi import APIRouter

from app.core.metrics import snapshot

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard")
def analytics_dashboard():
    """
    Aggregated metrics for the operator dashboard (latency, errors, handoff rate by audience segment).
    """
    return snapshot()
