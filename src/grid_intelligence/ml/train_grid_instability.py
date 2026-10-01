"""Train XGBoost classifier for grid instability prediction.

Time-based 80/20 split (not random), class-weighted to handle the
~19% positive rate. Saves the model to models/grid_instability_v1.pkl
and metrics to docs/model_metrics.json.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from xgboost import XGBClassifier

from grid_intelligence.config import MODELS_DIR, PROJECT_ROOT
from grid_intelligence.ml.features import (
    NUMERIC_FEATURES,
    TARGET,
    build_feature_matrix,
)
from grid_intelligence.utils.logging import get_logger

log = get_logger(__name__)

MODEL_PATH = MODELS_DIR / "grid_instability_v1.pkl"
METRICS_PATH = PROJECT_ROOT / "docs" / "model_metrics.json"


def time_split(df, split_frac: float = 0.8):
    """Split by time — first 80% train, last 20% test, per the brief."""
    df = df.sort_values("event_ts").reset_index(drop=True)
    cutoff = int(len(df) * split_frac)
    return df.iloc[:cutoff].copy(), df.iloc[cutoff:].copy()


def train() -> dict:
    """Build features, train, evaluate, persist model + metrics."""
    log.info("train: building feature matrix")
    df = build_feature_matrix()

    train_df, test_df = time_split(df, 0.8)
    log.info(
        "train: split at %s | train=%d test=%d",
        train_df["event_ts"].max(),
        len(train_df),
        len(test_df),
    )

    X_train = train_df[NUMERIC_FEATURES]
    y_train = train_df[TARGET]
    X_test = test_df[NUMERIC_FEATURES]
    y_test = test_df[TARGET]

    # Class weight: scale_pos_weight = negatives / positives
    neg = int((y_train == 0).sum())
    pos = int((y_train == 1).sum())
    scale_pos_weight = neg / max(pos, 1)
    log.info(
        "train: class balance neg=%d pos=%d scale_pos_weight=%.2f",
        neg,
        pos,
        scale_pos_weight,
    )

    model = XGBClassifier(
        n_estimators=400,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.85,
        scale_pos_weight=scale_pos_weight,
        eval_metric="auc",
        tree_method="hist",
        n_jobs=2,
        random_state=42,
        verbosity=0,
    )

    log.info("train: fitting XGBoost classifier")
    model.fit(X_train, y_train)

    # Predictions
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    metrics = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "model_version": "v1",
        "n_train": int(len(train_df)),
        "n_test": int(len(test_df)),
        "n_features": len(NUMERIC_FEATURES),
        "positive_rate_train": float(y_train.mean()),
        "positive_rate_test": float(y_test.mean()),
        "auc_roc": float(roc_auc_score(y_test, y_proba)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
        "feature_importances": {
            name: float(imp)
            for name, imp in zip(
                NUMERIC_FEATURES, model.feature_importances_, strict=False
            )
        },
    }

    # Persist
    MODELS_DIR.mkdir(exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    METRICS_PATH.parent.mkdir(exist_ok=True)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2))

    log.info(
        "train: AUC=%.4f precision=%.4f recall=%.4f F1=%.4f",
        metrics["auc_roc"],
        metrics["precision"],
        metrics["recall"],
        metrics["f1"],
    )
    log.info("train: model saved to %s", MODEL_PATH)
    log.info("train: metrics saved to %s", METRICS_PATH)

    return metrics


if __name__ == "__main__":
    m = train()
    print("\n=== Model Metrics ===")
    print(f"AUC-ROC:  {m['auc_roc']:.4f}")
    print(f"Precision:{m['precision']:.4f}")
    print(f"Recall:   {m['recall']:.4f}")
    print(f"F1:       {m['f1']:.4f}")
    print(f"Confusion matrix: {m['confusion_matrix']}")
    print("\n=== Top 10 Feature Importances ===")
    top = sorted(m["feature_importances"].items(), key=lambda x: -x[1])[:10]
    for name, imp in top:
        print(f"  {name:25s} {imp:.4f}")