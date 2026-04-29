from typing import List

from app.models.schemas import SourceChunk


def _calibrate_confidence(raw_score: float, score_scale: float) -> float:
    if score_scale <= 0:
        return max(0.0, min(raw_score, 1.0))
    return max(0.0, min(raw_score * score_scale, 1.0))


def build_quality_metrics(chunks: List[SourceChunk], min_confidence_score: float, score_scale: float = 2.5) -> dict:
    scores = [chunk.score for chunk in chunks]
    if not scores:
        calibrated_confidence = _calibrate_confidence(0.0, score_scale)
        return {
            "chunk_count": 0,
            "source_count": 0,
            "avg_score": 0.0,
            "confidence": calibrated_confidence,
            "top_score": 0.0,
            "score_spread": 0.0,
            "low_confidence": calibrated_confidence < min_confidence_score,
        }

    avg_score = sum(scores) / len(scores)
    calibrated_confidence = _calibrate_confidence(avg_score, score_scale)
    top_score = max(scores)
    score_spread = max(scores) - min(scores) if len(scores) > 1 else 0.0
    source_count = len({chunk.source_url for chunk in chunks if chunk.source_url})
    return {
        "chunk_count": len(chunks),
        "source_count": source_count,
        "avg_score": avg_score,
        "confidence": calibrated_confidence,
        "top_score": top_score,
        "score_spread": score_spread,
        "low_confidence": calibrated_confidence < min_confidence_score,
    }


def should_trigger_handoff(
    query: str,
    quality_metrics: dict,
    had_grounding_violation: bool,
) -> bool:
    asks_for_human = "human" in query.lower()
    return bool(quality_metrics.get("low_confidence") or asks_for_human or had_grounding_violation)
