import math
import runpy
from pathlib import Path

import numpy as np
import pytest

from pubburi_recommendation.catalog_audit import AuditError

ROOT = Path(__file__).resolve().parents[1]
HASH = "a" * 64


def inputs(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    script = runpy.run_path(str(ROOT / "scripts/evaluate_neural_heldout.py"))
    protocol = script["Protocol"].model_validate(
        {
            "review_sha256": HASH,
            "train_rows": [1, 2, 3],
            "heldout": {
                str(n): {"material": "rice", "evidence_sha256": HASH} for n in (4, 5, 6, 7)
            },
        }
    )
    rows = [
        dict(
            source_row_number=n,
            producer_name=producer,
            category=category,
            abv_percent=abv,
            review_evidence={"sha256": HASH},
        )
        for n, producer, category, abv in (
            (1, "First", "takju", 5.0),
            (2, "Second", "yakju", 15.0),
            (3, "Third", "takju", 7.0),
            (4, "Fourth", "takju", 6.0),
            (5, "Fourth", "takju", 7.0),
            (6, "Fifth", "takju", 8.0),
            (7, "Sixth", "unsupported", None),
        )
    ]
    return script["evaluate"], protocol, rows


def test_heldout_changes_never_refit_models_and_zero_scores_never_fill(monkeypatch):
    evaluate, protocol, rows = inputs(monkeypatch)
    report = evaluate(protocol, rows, HASH)
    cases = {row["query"]: row for row in report["cases"]}
    assert cases[4]["orders"] == {"b1": [6], "d1": [6]}
    assert cases[7]["metrics"] == {
        "b1": {"recall": 0.0, "ndcg": 0.0},
        "d1": {"recall": 0.0, "ndcg": 0.0},
    }

    rows[-1]["category"] = "takju"
    rows[-1]["abv_percent"] = 6.0
    protocol.heldout["4"].material = "wheat"
    changed = evaluate(protocol, rows, HASH)
    assert changed["b1_fit"] == report["b1_fit"]
    assert changed["d1_fit"] == report["d1_fit"]
    assert changed["cases"] != report["cases"]


def test_reviewed_producer_cannot_cross_partition(monkeypatch):
    evaluate, protocol, rows = inputs(monkeypatch)
    rows[-1]["producer_name"] = " F i r s t "
    with pytest.raises(AuditError, match="heldout_producer_groups_must_be_known_and_disjoint"):
        evaluate(protocol, rows, HASH)


def test_reviewed_volume_is_fitted_only_on_training_observations(monkeypatch):
    evaluate, protocol, rows = inputs(monkeypatch)
    rows[0]["volume_ml"] = 375
    rows[1]["volume_ml"] = 750
    report = evaluate(protocol, rows, HASH)
    assert report["training"]["numeric_fit"]["volume_ml"] == {
        "observed_count": 2,
        "missing_count": 1,
        "active": True,
        "minimum": 375.0,
        "maximum": 750.0,
    }
    rows[-1]["volume_ml"] = 1_000_000
    changed = evaluate(protocol, rows, HASH)
    assert changed["training"] == report["training"]
    assert changed["b1_fit"] == report["b1_fit"]
    assert changed["d1_fit"] == report["d1_fit"]


def test_zero_latent_weight_keeps_b1_order_and_does_not_refit_representation(monkeypatch):
    evaluate, protocol, rows = inputs(monkeypatch)
    default = evaluate(protocol, rows, HASH)
    explicit = evaluate(protocol, rows, HASH, latent_weight=0.5)
    assert default == explicit
    baseline = evaluate(protocol, rows, HASH, latent_weight=0)
    assert all(case["orders"]["b1"] == case["orders"]["d1"] for case in baseline["cases"])
    assert baseline["b1_fit"] == default["b1_fit"]
    assert baseline["d1_fit"] == default["d1_fit"]


def test_candidate_width_is_consumed_without_refitting_on_heldout_facts(monkeypatch):
    evaluate, protocol, rows = inputs(monkeypatch)
    default = evaluate(protocol, rows, HASH)
    assert default == evaluate(protocol, rows, HASH, bottleneck_dimension=2)
    candidate = evaluate(protocol, rows, HASH, bottleneck_dimension=4)
    assert candidate["b1_fit"] == default["b1_fit"]
    assert candidate["d1_fit"] != default["d1_fit"]
    representation = candidate["neural_representation"]
    assert representation["bottleneck_dimension"] == 4
    assert math.isfinite(representation["training_reconstruction_rmse"])
    assert representation["training_reconstruction_rmse"] >= 0
    unsupported = next(row for row in candidate["cases"] if row["query"] == 7)
    assert unsupported["orders"] == {"b1": [], "d1": []}

    rows[-1].update(category="takju", abv_percent=6.0, volume_ml=1_000_000)
    protocol.heldout["4"].material = "wheat"
    changed = evaluate(protocol, rows, HASH, bottleneck_dimension=4)
    assert changed["d1_fit"] == candidate["d1_fit"]
    assert changed["training"] == candidate["training"]
    assert changed["neural_representation"] == representation


def test_observation_scale_changes_only_flags_and_restores_original_rmse(monkeypatch):
    evaluate, protocol, rows = inputs(monkeypatch)
    rows[0]["abv_percent"] = 0.0
    rows[2]["abv_percent"] = None
    estimator = evaluate.__globals__["MLPRegressor"]
    fits = []

    class Capture(estimator):
        def fit(self, x, y):
            fitted = super().fit(x, y)
            fits.append((x.copy(), y.copy(), fitted))
            return fitted

    monkeypatch.setitem(evaluate.__globals__, "MLPRegressor", Capture)
    default = evaluate(protocol, rows, HASH)
    assert default == evaluate(protocol, rows, HASH, observation_scale=1)
    candidate = evaluate(protocol, rows, HASH, observation_scale=0.5)
    original, original_target, _ = fits[0]
    scaled, scaled_target, model = fits[2]
    # Two category columns and then ABV value/observation flag. Known zero and
    # unknown retain the same value but distinct evidence even after downweighting.
    np.testing.assert_array_equal(original[:, -2:], [[0, 1], [1, 1], [0, 0]])
    np.testing.assert_array_equal(scaled[:, :-1], original[:, :-1])
    np.testing.assert_array_equal(scaled[:, -1], original[:, -1] * 0.5)
    np.testing.assert_array_equal(original_target, original)
    np.testing.assert_array_equal(scaled_target, scaled)
    prediction = model.predict(scaled)
    inverse_scale = np.ones(scaled.shape[1])
    inverse_scale[-1] = 0.5
    representation = candidate["neural_representation"]
    assert representation["training_reconstruction_rmse"] == pytest.approx(
        np.sqrt(np.mean((prediction / inverse_scale - original) ** 2))
    )
    assert representation["training_objective_rmse"] == pytest.approx(
        np.sqrt(np.mean((prediction - scaled) ** 2))
    )
    assert representation["observation_scale"] == 0.5
    assert candidate["b1_fit"] == default["b1_fit"]
    assert candidate["d1_fit"] != default["d1_fit"]
    assert rows[0]["abv_percent"] == 0.0 and rows[2]["abv_percent"] is None
    unsupported = next(row for row in candidate["cases"] if row["query"] == 7)
    assert unsupported["orders"] == {"b1": [], "d1": []}

    rows[-1].update(category="takju", abv_percent=80.0, volume_ml=1_000_000)
    protocol.heldout["4"].material = "wheat"
    changed = evaluate(protocol, rows, HASH, observation_scale=0.5)
    assert changed["b1_fit"] == candidate["b1_fit"]
    assert changed["d1_fit"] == candidate["d1_fit"]
    assert changed["training"] == candidate["training"]
    assert changed["neural_representation"] == representation


@pytest.mark.parametrize("scale", [0, 0.25, 2, True, float("nan"), float("inf"), "0.5"])
def test_invalid_observation_scale_is_rejected_before_fit(monkeypatch, scale):
    evaluate, protocol, rows = inputs(monkeypatch)
    monkeypatch.setattr(
        "pubburi_recommendation.content_model.FittedContentModel.fit",
        lambda *_: pytest.fail("invalid scale reached fit"),
    )
    with pytest.raises(AuditError, match="heldout_observation_scale_must_be_one_or_half"):
        evaluate(protocol, rows, HASH, observation_scale=scale)


@pytest.mark.parametrize("dimension", [0, 1, 3, 5, True, 2.0])
def test_invalid_width_is_rejected_before_fit(monkeypatch, dimension):
    evaluate, protocol, rows = inputs(monkeypatch)
    monkeypatch.setattr(
        "pubburi_recommendation.content_model.FittedContentModel.fit",
        lambda *_: pytest.fail("invalid dimension reached fit"),
    )
    with pytest.raises(AuditError, match="bottleneck_dimension_must_be_two_or_four"):
        evaluate(protocol, rows, HASH, bottleneck_dimension=dimension)


@pytest.mark.parametrize("weight", [-0.1, 1.1, float("nan"), float("inf"), True])
def test_invalid_latent_weight_is_rejected_before_fit(monkeypatch, weight):
    evaluate, protocol, rows = inputs(monkeypatch)
    monkeypatch.setattr(
        "pubburi_recommendation.content_model.FittedContentModel.fit",
        lambda *_: pytest.fail("invalid weight reached fit"),
    )
    with pytest.raises(AuditError, match="heldout_latent_weight_must_be_finite"):
        evaluate(protocol, rows, HASH, latent_weight=weight)
