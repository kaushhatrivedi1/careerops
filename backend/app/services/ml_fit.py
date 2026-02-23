"""
ML model loading and inference for fit probability.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import settings


def _build_feature_vector(
    semantic_score: float,
    keyword_coverage: float,
    ats_risk_score: float,
) -> list[float]:
    return [semantic_score, keyword_coverage, ats_risk_score]


@lru_cache(maxsize=1)
def load_fit_model() -> tuple[Any | None, dict[str, Any]]:
    """
    Load pickled sklearn artifact if present.
    Returns (model, metadata). Model is None if missing/unreadable.
    """
    model_path = Path(settings.FIT_MODEL_PATH)
    if not model_path.exists():
        return None, {"loaded": False, "reason": "model_file_missing", "path": str(model_path)}

    try:
        import joblib
    except Exception:
        return None, {"loaded": False, "reason": "joblib_unavailable", "path": str(model_path)}

    try:
        artifact = joblib.load(model_path)
    except Exception as exc:
        return None, {
            "loaded": False,
            "reason": f"model_load_error:{type(exc).__name__}",
            "path": str(model_path),
        }

    model = artifact.get("model")
    metadata = artifact.get("metadata", {})
    return model, {"loaded": model is not None, "path": str(model_path), "metadata": metadata}


def predict_fit_probability(
    semantic_score: float,
    keyword_coverage: float,
    ats_risk_score: float,
) -> tuple[float | None, dict[str, Any]]:
    """
    Predict probability from the ML model.
    Returns (probability, info). Probability is None when model is unavailable.
    """
    model, model_info = load_fit_model()
    if model is None:
        return None, model_info

    feature_vector = _build_feature_vector(
        semantic_score=semantic_score,
        keyword_coverage=keyword_coverage,
        ats_risk_score=ats_risk_score,
    )

    try:
        probability = float(model.predict_proba([feature_vector])[0][1])
        return probability, {
            "loaded": True,
            "path": model_info.get("path"),
            "metadata": model_info.get("metadata", {}),
        }
    except Exception as exc:
        return None, {
            "loaded": False,
            "reason": f"inference_error:{type(exc).__name__}",
            "path": model_info.get("path"),
        }
