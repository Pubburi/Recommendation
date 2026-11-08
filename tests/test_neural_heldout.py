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


def pairwise_inputs(monkeypatch):
    evaluate, protocol, rows = inputs(monkeypatch)
    protocol.training_materials = {
        str(n): evaluate.__globals__["MaterialJudgment"](
            material="wheat" if n == 2 else "rice", evidence_sha256=HASH
        )
        for n in (1, 2, 3)
    }
    return evaluate, protocol, rows


def test_pairwise_objective_fits_fact_targets_and_is_symmetric_without_heldout_leakage(monkeypatch):
    evaluate, protocol, rows = pairwise_inputs(monkeypatch)
    estimator = evaluate.__globals__["MLPClassifier"]
    captured = []

    class Capture(estimator):
        def fit(self, x, y):
            captured.append((x.copy(), y.copy()))
            return super().fit(x, y)

    monkeypatch.setitem(evaluate.__globals__, "MLPClassifier", Capture)
    report = evaluate(protocol, rows, HASH, objective="pairwise-material", latent_weight=0.25)
    info = report["neural_representation"]
    assert info["hidden_layer_sizes"] == [8, 4]
    assert (
        info["training_pairs"],
        info["positive_training_pairs"],
        info["negative_training_pairs"],
    ) == (3, 1, 2)
    assert info["supervised_training_products"] == 3 and info["unlabeled_training_products"] == 0
    assert "training_reconstruction_rmse" not in info
    features = evaluate.__globals__["pair_features"]
    a, b = np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.0, 1.0])
    np.testing.assert_array_equal(features(a, b), features(b, a))
    assert not np.array_equal(features(a, a), features(a, b))
    assert next(row for row in report["cases"] if row["query"] == 7)["orders"] == {
        "b1": [],
        "d1": [],
    }
    rows[-1].update(category="new-category", abv_percent=99.0, volume_ml=1_000_000)
    protocol.heldout["4"].material = "different"
    changed = evaluate(protocol, rows, HASH, objective="pairwise-material", latent_weight=0.25)
    assert changed["b1_fit"] == report["b1_fit"] and changed["d1_fit"] == report["d1_fit"]
    np.testing.assert_array_equal(captured[0][0], captured[1][0])
    np.testing.assert_array_equal(captured[0][1], captured[1][1])
    protocol.training_materials["3"].material = "wheat"
    target_changed = evaluate(
        protocol, rows, HASH, objective="pairwise-material", latent_weight=0.25
    )
    assert (
        target_changed["b1_fit"] == report["b1_fit"]
        and target_changed["d1_fit"] != report["d1_fit"]
    )
    np.testing.assert_array_equal(captured[0][0], captured[2][0])
    assert not np.array_equal(captured[0][1], captured[2][1])


def test_pairwise_unknown_target_is_not_negative_and_same_producer_pair_is_not_training(
    monkeypatch,
):
    evaluate, protocol, rows = pairwise_inputs(monkeypatch)
    protocol.train_rows.append(8)
    rows.append(
        {**rows[0], "source_row_number": 8, "producer_name": "Unlabeled", "category": "other"}
    )
    report = evaluate(protocol, rows, HASH, objective="pairwise-material")
    assert report["training"]["rows"] == 4
    assert report["neural_representation"]["unlabeled_training_products"] == 1
    assert report["neural_representation"]["training_pairs"] == 3
    rows[2]["producer_name"] = rows[0]["producer_name"]
    with pytest.raises(AuditError, match="positive_and_negative_training_pairs"):
        evaluate(protocol, rows, HASH, objective="pairwise-material")


@pytest.mark.parametrize("change", ["heldout", "noncanonical", "evidence"])
def test_pairwise_training_label_requires_exact_training_row_authority(monkeypatch, change):
    evaluate, protocol, rows = pairwise_inputs(monkeypatch)
    if change == "heldout":
        protocol.training_materials["4"] = protocol.training_materials["1"]
    elif change == "noncanonical":
        protocol.training_materials["01"] = protocol.training_materials.pop("1")
    else:
        protocol.training_materials["1"].evidence_sha256 = "b" * 64
    with pytest.raises(AuditError, match="training_material_authority"):
        evaluate(protocol, rows, HASH, objective="pairwise-material")


@pytest.mark.parametrize("value", [True, None, float("nan"), float("inf"), 0, 0.1])
def test_pairwise_alpha_rejects_unreviewed_values(monkeypatch, value):
    evaluate, protocol, rows = pairwise_inputs(monkeypatch)
    with pytest.raises(AuditError, match="pairwise_alpha"):
        evaluate(protocol, rows, HASH, objective="pairwise-material", pairwise_alpha=value)


def test_pairwise_alpha_is_consumed_and_legacy_objective_must_be_explicit(monkeypatch):
    evaluate, protocol, rows = pairwise_inputs(monkeypatch)
    a = evaluate(protocol, rows, HASH, objective="pairwise-material", pairwise_alpha=0.001)
    b = evaluate(protocol, rows, HASH, objective="pairwise-material", pairwise_alpha=0.01)
    assert a["b1_fit"] == b["b1_fit"] and a["d1_fit"] != b["d1_fit"]
    assert b["neural_representation"]["alpha"] == 0.01
    with pytest.raises(AuditError, match="explicit_pairwise_objective"):
        evaluate(protocol, rows, HASH)


def test_balanced_loss_weights_only_observed_different_producer_pairs_without_heldout_leakage(
    monkeypatch,
):
    evaluate, protocol, rows = pairwise_inputs(monkeypatch)
    protocol.train_rows.extend([8, 9])
    rows.extend(
        [
            {**rows[0], "source_row_number": 8, "producer_name": "unknown-target"},
            {**rows[0], "source_row_number": 9},
        ]
    )
    protocol.training_materials["9"] = protocol.training_materials["1"]
    estimator = evaluate.__globals__["MLPClassifier"]
    captured = []

    class Capture(estimator):
        def fit(self, x, y, **kwargs):
            captured.append((x.copy(), y.copy(), kwargs.get("sample_weight")))
            return super().fit(x, y, **kwargs)

    monkeypatch.setitem(evaluate.__globals__, "MLPClassifier", Capture)
    uniform = evaluate(protocol, rows, HASH, objective="pairwise-material")
    explicit = evaluate(
        protocol, rows, HASH, objective="pairwise-material", pairwise_weighting="uniform"
    )
    assert uniform == explicit and captured[0][2] is captured[1][2] is None
    balanced = evaluate(
        protocol, rows, HASH, objective="pairwise-material", pairwise_weighting="balanced"
    )
    x, y, weights = captured[2]
    assert len(y) == 5 and y.sum() == 2  # Same producer and unknown target do not enter counts.
    np.testing.assert_allclose(weights[y == 1], [1.25, 1.25])
    np.testing.assert_allclose(weights[y == 0], [5 / 6] * 3)
    info = balanced["neural_representation"]
    assert info["total_weight"] == pytest.approx(5)
    assert info["positive_weight_sum"] == pytest.approx(2.5)
    assert info["negative_weight_sum"] == pytest.approx(2.5)
    assert uniform["b1_fit"] == balanced["b1_fit"]
    assert uniform["d1_fit"] != balanced["d1_fit"]
    assert "pairwise_weighting" not in uniform["neural_representation"]
    rows[3].update(category="unseen", abv_percent=97, volume_ml=999_999)
    protocol.heldout["4"].material = "different"
    changed = evaluate(
        protocol, rows, HASH, objective="pairwise-material", pairwise_weighting="balanced"
    )
    assert changed["d1_fit"] == balanced["d1_fit"]
    np.testing.assert_array_equal(x, captured[3][0])
    np.testing.assert_array_equal(y, captured[3][1])
    np.testing.assert_array_equal(weights, captured[3][2])


@pytest.mark.parametrize("value", [True, None, "BALANCED", "class_weight", ""])
def test_pairwise_weighting_is_strict_and_requires_explicit_objective(monkeypatch, value):
    evaluate, protocol, rows = pairwise_inputs(monkeypatch)
    with pytest.raises(AuditError, match="pairwise_weighting"):
        evaluate(protocol, rows, HASH, objective="pairwise-material", pairwise_weighting=value)
    protocol.training_materials = None
    with pytest.raises(AuditError, match="explicit_pairwise_objective"):
        evaluate(protocol, rows, HASH, pairwise_weighting="balanced")


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


def test_denoising_views_mask_only_observed_blocks_with_remaining_evidence(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    script = runpy.run_path(str(ROOT / "scripts/evaluate_neural_heldout.py"))
    train = np.array(
        [[1, 0, 1, 0, 0], [1, 0.4, 1, 0.8, 1], [0, 0, 0, 0, 1], [1, 0, 0, 0, 0]],
        dtype=float,
    )
    original = train.copy()
    x, y = script["training_views"](train, 1, "numeric-block-denoising")
    np.testing.assert_array_equal(train, original)
    np.testing.assert_array_equal(x[:4], original)
    np.testing.assert_array_equal(x[4:], [[1, 0, 0, 0, 0], [1, 0, 0, 0.8, 1], [1, 0.4, 1, 0, 0]])
    np.testing.assert_array_equal(y, original[[0, 1, 2, 3, 0, 1, 1]])
    assert np.any(x != 0, axis=1).all()


def test_denoising_fit_uses_train_views_without_changing_facts_or_b1(monkeypatch):
    evaluate, protocol, rows = inputs(monkeypatch)
    rows[0].update(abv_percent=0.0, volume_ml=375)
    rows[1]["volume_ml"] = 750
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
    assert default == evaluate(protocol, rows, HASH, training_mode="clean")
    candidate = evaluate(protocol, rows, HASH, training_mode="numeric-block-denoising")
    x, y, model = fits[2]
    assert len(x) == len(y) == 7
    np.testing.assert_array_equal(x[:3], fits[0][0])
    np.testing.assert_array_equal(y[:3], fits[0][1])
    representation = candidate["neural_representation"]
    assert representation["training_view_rows"] == 7
    assert representation["training_corrupted_views"] == 4
    assert representation["training_mode"] == "numeric-block-denoising"
    assert representation["training_reconstruction_rmse"] == pytest.approx(
        np.sqrt(np.mean((model.predict(x[:3]) - y[:3]) ** 2))
    )
    assert representation["training_objective_rmse"] == pytest.approx(
        np.sqrt(np.mean((model.predict(x) - y) ** 2))
    )
    assert candidate["training"]["rows"] == 3
    assert candidate["b1_fit"] == default["b1_fit"]
    assert candidate["d1_fit"] != default["d1_fit"]
    for base, changed in zip(default["cases"], candidate["cases"], strict=True):
        assert base["orders"]["b1"] == changed["orders"]["b1"]
        assert set(changed["orders"]["d1"]) == set(changed["orders"]["b1"])
    assert candidate["cases"][-1]["orders"] == {"b1": [], "d1": []}
    assert rows[0]["abv_percent"] == 0.0 and rows[2]["abv_percent"] is None

    rows[-1].update(category="takju", abv_percent=90.0, volume_ml=1_000_000)
    protocol.heldout["4"].material = "wheat"
    changed = evaluate(protocol, rows, HASH, training_mode="numeric-block-denoising")
    assert changed["d1_fit"] == candidate["d1_fit"]
    assert changed["b1_fit"] == candidate["b1_fit"]
    assert changed["training"] == candidate["training"]
    assert changed["neural_representation"] == representation


@pytest.mark.parametrize("mode", ["", "denoise", "CLEAN", None, True, 1, ["clean"]])
def test_invalid_training_mode_is_rejected_before_fit(monkeypatch, mode):
    evaluate, protocol, rows = inputs(monkeypatch)
    monkeypatch.setattr(
        "pubburi_recommendation.content_model.FittedContentModel.fit",
        lambda *_: pytest.fail("invalid training mode reached fit"),
    )
    with pytest.raises(AuditError, match="training_mode_must_be_clean_or_numeric_block_denoising"):
        evaluate(protocol, rows, HASH, training_mode=mode)


def test_iteration_budget_is_consumed_without_refitting_on_heldout(monkeypatch):
    evaluate, protocol, rows = inputs(monkeypatch)
    estimator = evaluate.__globals__["MLPRegressor"]
    budgets = []

    class Capture(estimator):
        def fit(self, x, y):
            budgets.append(self.max_iter)
            return super().fit(x, y)

    monkeypatch.setitem(evaluate.__globals__, "MLPRegressor", Capture)
    default = evaluate(protocol, rows, HASH)
    assert default == evaluate(protocol, rows, HASH, max_iterations=1000)
    candidate = evaluate(protocol, rows, HASH, max_iterations=3000)
    assert budgets == [1000, 1000, 3000]
    assert candidate["b1_fit"] == default["b1_fit"]
    assert candidate["d1_fit"] != default["d1_fit"]
    assert 0 < candidate["iterations"] <= 3000
    assert candidate["neural_representation"]["max_iterations"] == 3000
    assert isinstance(candidate["convergence_warnings"], list)
    rows[-1].update(category="takju", abv_percent=90.0, volume_ml=1_000_000)
    protocol.heldout["4"].material = "wheat"
    changed = evaluate(protocol, rows, HASH, max_iterations=3000)
    for field in ("b1_fit", "d1_fit", "training", "neural_representation", "iterations"):
        assert changed[field] == candidate[field]


@pytest.mark.parametrize("budget", [0, 999, 1001, 3001, True, 1000.0, "3000", None])
def test_invalid_iteration_budget_is_rejected_before_fit(monkeypatch, budget):
    evaluate, protocol, rows = inputs(monkeypatch)
    monkeypatch.setattr(
        "pubburi_recommendation.content_model.FittedContentModel.fit",
        lambda *_: pytest.fail("invalid iteration budget reached fit"),
    )
    with pytest.raises(AuditError, match="max_iterations_must_be_one_or_three_thousand"):
        evaluate(protocol, rows, HASH, max_iterations=budget)


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
