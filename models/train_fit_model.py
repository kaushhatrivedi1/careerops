"""
Train a lightweight supervised model for fit probability from training_examples.

Usage:
  cd backend
  python ../models/train_fit_model.py --db-url "$DATABASE_URL"
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sqlalchemy import create_engine, text


FEATURE_KEYS = ("semantic_score", "keyword_coverage", "ats_risk_score")


def _build_matrix(rows: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    x_values: list[list[float]] = []
    y_values: list[int] = []
    for row in rows:
        features = row.get("features_json") or {}
        x_values.append([
            float(features.get("semantic_score", 0.0)),
            float(features.get("keyword_coverage", 0.0)),
            float(features.get("ats_risk_score", 1.0)),
        ])
        y_values.append(int(float(row.get("label_value", 0.0)) >= 0.5))
    return np.array(x_values, dtype=float), np.array(y_values, dtype=int)


def load_rows(db_url: str, task: str, source: str) -> list[dict[str, Any]]:
    engine = create_engine(db_url)
    query = text(
        """
        SELECT features_json, label_value
        FROM training_examples
        WHERE task = :task AND source = :source
        """
    )
    with engine.connect() as conn:
        result = conn.execute(query, {"task": task, "source": source})
        rows = [dict(r._mapping) for r in result]
    return rows


def train_model(x: np.ndarray, y: np.ndarray) -> tuple[LogisticRegression, dict[str, float]]:
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y if len(np.unique(y)) > 1 else None,
    )
    model = LogisticRegression(max_iter=1000, random_state=42)
    model.fit(x_train, y_train)
    y_prob = model.predict_proba(x_test)[:, 1]
    y_pred = (y_prob >= 0.5).astype(int)

    metrics: dict[str, float] = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
    }
    if len(np.unique(y_test)) > 1:
        metrics["roc_auc"] = float(roc_auc_score(y_test, y_prob))
    return model, metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-url", required=True, help="Postgres URL for training_examples table")
    parser.add_argument("--task", default="fit_ranking")
    parser.add_argument("--source", default="weak_label")
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parent / "artifacts" / "fit_model.pkl"),
    )
    args = parser.parse_args()

    rows = load_rows(db_url=args.db_url, task=args.task, source=args.source)
    if len(rows) < 50:
        raise SystemExit("Need at least 50 training rows before fitting a stable model.")

    x, y = _build_matrix(rows)
    if len(np.unique(y)) < 2:
        raise SystemExit("Training labels only contain one class; cannot train classifier.")

    model, metrics = train_model(x, y)
    artifact = {
        "model": model,
        "metadata": {
            "task": args.task,
            "source": args.source,
            "feature_keys": FEATURE_KEYS,
            "row_count": int(len(rows)),
            "metrics": metrics,
            "threshold": 0.5,
            "model_type": "LogisticRegression",
        },
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, output_path)
    print(f"Saved model artifact to {output_path}")
    print(f"Metrics: {metrics}")


if __name__ == "__main__":
    main()
