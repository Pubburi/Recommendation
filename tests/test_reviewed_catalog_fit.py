"""Authored regression for the reviewed fit workflow, never actual catalog quality data."""

import copy
import sys
from datetime import timedelta
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from test_business_export import (
    NOW,
    SNAPSHOT_HASH,
    catalog_fixture,
    mapping_fixture,
    snapshot_fixture,
)

from pubburi_recommendation import reviewed_catalog_fit
from pubburi_recommendation.baseline import Constraints
from pubburi_recommendation.business_export import ReviewedMapping, build_exports, content_hash
from pubburi_recommendation.catalog_audit import AuditError
from pubburi_recommendation.content_api import ContentRecommendationRequest
from pubburi_recommendation.reviewed_catalog_fit import (
    ReviewedFitSpec,
    check_case,
    run_reviewed_fit,
)


def inputs():
    catalog = catalog_fixture()
    mapping = ReviewedMapping.model_validate(mapping_fixture())
    report, exports = build_exports(catalog, snapshot_fixture(), SNAPSHOT_HASH, mapping, NOW)
    key = "fictional-can"
    cases = []
    for name, profile, constraints, keys, count, fallback, excluded in [
        ("cold", {}, {}, [key], 1, "no_supported_preferences", []),
        ("category", {"categories": ["맥주"]}, {}, [key], 1, None, []),
        ("numeric", {"preferred_abv_percent": 5}, {}, [key], 1, "no_supported_preferences", []),
        ("hard", {}, {"max_abv_percent": 4.99}, [], 0, "no_eligible_products", []),
        ("exclude", {}, {}, [], 0, "no_eligible_products", [key]),
        ("oov", {"taste_tags": ["unobserved"]}, {}, [key], 1, "no_supported_preferences", []),
    ]:
        cases.append(
            {
                "case_id": name,
                "profile": profile,
                "constraints": constraints,
                "exclude_keys": excluded,
                "expected_eligible_keys": keys,
                "expected_item_count": count,
                "expected_b1_fallback": fallback,
                "fact_basis": "Independently declared fictional facts.",
            }
        )
    spec = {
        "schema_version": 1,
        "experiment_id": "authored-known-catalog-v1",
        "evidence_kind": "authored_regression_fixture",
        "source_catalog_sha256": content_hash(catalog),
        "frozen_at_utc": (NOW - timedelta(days=1)).isoformat(),
        "expected_facts": {
            key: {
                "category": "맥주",
                "price_krw": 1000,
                "abv_percent": 5,
                "volume_ml": 500,
                "taste_tags": None,
                "aroma_tags": None,
                "sku_group": "fictional-family",
                "available": True,
            }
        },
        "scenarios": cases,
    }
    return spec, catalog, exports, mapping, report


def execute(data):
    spec, catalog, exports, mapping, report = data
    return run_reviewed_fit(
        ReviewedFitSpec.model_validate(spec), catalog, exports, mapping, report, NOW
    )


def test_actual_engine_fits_once_on_frozen_known_catalog_and_keeps_singleton_limits():
    result = execute(inputs())
    assert result["passed"] and result["passed_cases"] == 6
    assert (
        result["fit_summary"]["training_products"] == result["fit_summary"]["training_groups"] == 1
    )
    assert result["vocabulary"] == ["category:맥주"] and result["idf"] == [1.0]
    assert all(not row["active"] for row in result["fit_summary"]["numeric_fit"].values())
    assert result["ranking_metrics"]["status"] == "not_calculated"
    assert result["snapshot_origin"] == "demo_fixture"


@pytest.mark.parametrize(
    "mutation", ["fact", "source_hash", "future", "source_kind", "eligibility", "missing_mapping"]
)
def test_contradictory_or_changed_declarations_fail_before_any_fit(mutation):
    data = list(inputs())
    spec = data[0]
    if mutation == "fact":
        spec["expected_facts"]["fictional-can"]["volume_ml"] = 330
    elif mutation == "source_hash":
        spec["source_catalog_sha256"] = "f" * 64
    elif mutation == "future":
        spec["frozen_at_utc"] = (NOW + timedelta(seconds=1)).isoformat()
    elif mutation == "source_kind":
        spec["evidence_kind"] = "reviewed_public_source"
    elif mutation == "eligibility":
        spec["scenarios"][0]["constraints"] = {"max_abv_percent": 4}
    else:
        data[2] = {}
    with patch("pubburi_recommendation.content_model.FittedContentModel.fit") as fit:
        with pytest.raises(AuditError):
            execute(data)
        fit.assert_not_called()


def test_keys_counts_and_case_identity_are_validated_before_execution():
    for mutation in ("unknown", "duplicate", "count", "unbound_id"):
        spec = inputs()[0]
        if mutation == "unknown":
            spec["scenarios"][0]["exclude_keys"] = ["not-a-source"]
        elif mutation == "duplicate":
            spec["scenarios"].append(copy.deepcopy(spec["scenarios"][0]))
        elif mutation == "count":
            spec["scenarios"][0]["expected_item_count"] = 0
        else:
            spec["scenarios"][0]["constraints"] = {"exclude_product_ids": [37]}
        with pytest.raises(ValidationError):
            ReviewedFitSpec.model_validate(spec)


def test_independent_inspector_rejects_result_and_contribution_corruption():
    data = inputs()
    result = execute(data)
    spec = ReviewedFitSpec.model_validate(data[0])
    case = spec.scenarios[1]
    products = ContentRecommendationRequest.model_validate(data[2]["b1-demo-request.json"]).catalog
    original = result["cases"][1]
    for corruption in ("unknown_id", "score", "feature", "count", "fallback", "inactive_reason"):
        b1 = copy.deepcopy(original["b1"])
        if corruption == "unknown_id":
            b1["items"][0]["product_id"] = 999
        elif corruption == "score":
            b1["items"][0]["score"] = 0.5
        elif corruption == "feature":
            b1["items"][0]["contributions"][0]["feature"] = "taste:invented"
        elif corruption == "count":
            b1["eligible_count"] = 0
        elif corruption == "fallback":
            b1["fallback_reason"] = "no_supported_preferences"
        else:
            b1["items"][0]["reasons"].append("abv_within_range")
        checked = check_case(case, products, Constraints(), [37], original["b0"], b1)
        assert not checked["passed"]


def test_identical_frozen_inputs_reproduce_parameters_and_results():
    first = execute(inputs())
    second = execute(inputs())
    assert first == second


def test_existing_output_is_rejected_before_source_reads_or_a_repeated_fit(
    tmp_path, monkeypatch, capsys
):
    output = tmp_path / ".pubburi" / "existing"
    output.mkdir(parents=True)
    command = ["reviewed-fit"]
    for name in (
        "manifest",
        "input",
        "source-receipt",
        "curation",
        "business-snapshot",
        "mapping",
        "spec",
    ):
        command += ["--" + name, "unused"]
    command += ["--output-dir", str(output)]
    monkeypatch.setattr(sys, "argv", command)
    with patch.object(reviewed_catalog_fit, "load_source_catalog") as read:
        assert reviewed_catalog_fit.main() == 2
        read.assert_not_called()
    assert "existing_fit_output_must_be_preserved" in capsys.readouterr().err
