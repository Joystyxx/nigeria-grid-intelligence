"""Train XGBoost classifier for load-spike prediction.

Target: will a substation's load exceed its 90th percentile within the
NEXT 3 hours? The p90 threshold is computed ONLY on training data
(first 80% by time) to avoid leakage.

Complementary to train_grid_instability.py (outage prediction). Where
outages turned out to be unpredictable from this dataset, load spikes
ARE learnable because load is highly autocorrelated.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
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
    build_feature_matrix,
)
from grid_intelligence.utils.logging import get_logger

log = get_logger(__name__)

MODEL_PATH = MODELS_DIR / "load_spike_v1.pkl"
METRICS_PATH = PROJECT_ROOT / "docs" / "model_metrics_load_spike.json"

TARGET = "load_spike_within_3h"
HORIZON_HOURS = 3
PERCENTILE = 0.90


def _forward_window_max(s: pd.Series, window: int) -> pd.Series:
    """target[i] = 1 if any s[i+1..i+window] == 1. Forward-only."""
    shifted = s.shift(-1)
    rev = shifted.iloc[::-1]
    rolled = rev.rolling(window, min_periods=1).max()
    return rolled.iloc[::-1].fillna(0).astype(int)


def build_load_spike_target(df: pd.DataFrame, split_frac: float = 0.8) -> pd.DataFrame:
    """Add `load_spike_within_3h` using a TRAIN-ONLY p90 threshold."""
    df = df.copy()

    # Identify the global time cutoff (same split as the outage model)
    df_sorted = df.sort_values("event_ts")
    cutoff_idx = int(len(df_sorted) * split_frac)
    cutoff_ts = df_sorted.iloc[cutoff_idx]["event_ts"]
    log.info("load_spike: train cutoff = %s", cutoff_ts)

    # Compute per-substation p90 using TRAIN rows only
    train_mask = df["event_ts"] <= cutoff_ts
    p90_map = (
        df[train_mask]
        .groupby("substation_id")["avg_load_mw"]
        .quantile(PERCENTILE)
        .to_dict()
    )
    log.info("load_spike: computed train-only p90 for %d substations", len(p90_map))

    # Apply the p90 threshold to all rows (train + test) to flag high load
    df["load_p90_threshold"] = df["substation_id"].map(p90_map)
    df["is_high_load"] = (df["avg_load_mw"] > df["load_p90_threshold"]).astype(int)

    # Forward-looking target per substation
    df = df.sort_values(["substation_id", "event_ts"]).reset_index(drop=True)
    df[TARGET] = (
        df.groupby("substation_id")["is_high_load"]
        .transform(lambda s: _forward_window_max(s, HORIZON_HOURS))
    )

    return df, cutoff_ts


def train() -> dict:
    """Build features, compute load spike target, train, evaluate, persist."""
    log.info("train_load_spike: building feature matrix")
    df = build_feature_matrix()

    df, cutoff_ts = build_load_spike_target(df, split_frac=0.8)

    train_df = df[df["event_ts"] <= cutoff_ts].copy()
    test_df = df[df["event_ts"] > cutoff_ts].copy()

    log.info(
        "train_load_spike: train=%d test=%d target rate train=%.3f test=%.3f",
        len(train_df),
        len(test_df),
        train_df[TARGET].mean(),
        test_df[TARGET].mean(),
    )

    X_train = train_df[NUMERIC_FEATURES]
    y_train = train_df[TARGET]
    X_test = test_df[NUMERIC_FEATURES]
    y_test = test_df[TARGET]

    neg = int((y_train == 0).sum())
    pos = int((y_train == 1).sum())
    scale_pos_weight = neg / max(pos, 1)
    log.info(
        "train_load_spike: class balance neg=%d pos=%d scale_pos_weight=%.2f",
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

    log.info("train_load_spike: fitting XGBoost classifier")
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    metrics = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "model_version": "v1",
        "model_name": "load_spike",
        "target": TARGET,
        "horizon_hours": HORIZON_HOURS,
        "percentile_threshold": PERCENTILE,
        "train_cutoff_ts": str(cutoff_ts),
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

    MODELS_DIR.mkdir(exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    METRICS_PATH.parent.mkdir(exist_ok=True)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2))

    log.info(
        "train_load_spike: AUC=%.4f precision=%.4f recall=%.4f F1=%.4f",
        metrics["auc_roc"],
        metrics["precision"],
        metrics["recall"],
        metrics["f1"],
    )
    log.info("train_load_spike: model saved to %s", MODEL_PATH)
    log.info("train_load_spike: metrics saved to %s", METRICS_PATH)

    return metrics


if __name__ == "__main__":
    m = train()
    print("\n=== Load Spike Model Metrics ===")
    print(f"AUC-ROC:  {m['auc_roc']:.4f}")
    print(f"Precision:{m['precision']:.4f}")
    print(f"Recall:   {m['recall']:.4f}")
    print(f"F1:       {m['f1']:.4f}")
    print(f"Confusion matrix: {m['confusion_matrix']}")
    print("\n=== Top 10 Feature Importances ===")
    top = sorted(m["feature_importances"].items(), key=lambda x: -x[1])[:10]
    for name, imp in top:
        print(f"  {name:35s} {imp:.4f}")