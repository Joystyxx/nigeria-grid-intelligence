"""Tests for the ML layer.

Verifies feature engineering produces the expected shape, and that the
trained model loads and produces valid probabilities.
"""
import joblib
import pytest

from grid_intelligence.config import MODELS_DIR
from grid_intelligence.ml.features import NUMERIC_FEATURES, TARGET, build_feature_matrix


pytestmark = pytest.mark.requires_db


def test_feature_matrix_shape_and_target_rate():
    df = build_feature_matrix()
    assert len(df) > 100_000, "Feature matrix should exceed 100k rows"
    for col in NUMERIC_FEATURES:
        assert col in df.columns, f"Missing feature column: {col}"
    assert TARGET in df.columns, f"Missing target column: {TARGET}"
    target_rate = df[TARGET].mean()
    assert 0.10 < target_rate < 0.30, f"Target rate {target_rate:.3f} outside expected range"


def test_outage_model_loads_and_predicts():
    path = MODELS_DIR / "grid_instability_v1.pkl"
    if not path.exists():
        pytest.skip("Model file not present; run train_grid_instability first")
    model = joblib.load(path)
    df = build_feature_matrix().head(500)
    X = df[NUMERIC_FEATURES]
    proba = model.predict_proba(X)[:, 1]
    assert len(proba) == len(X)
    assert (proba >= 0).all() and (proba <= 1).all()
