"""Freeze handwritten truth and inject faults; never use ranking code to make labels."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from pubburi_recommendation.catalog_audit import read_json
from pubburi_recommendation.main import app
from pubburi_recommendation.scenario_evaluation import (
    EvaluationInputError,
    ResponseBundle,
    ScenarioSuite,
    evaluate,
)

SUITE_PATH = Path(__file__).resolve().parents[1] / "evaluation/baseline-contract-v1.json"


@pytest.fixture(scope="module")
def frozen_run():
    suite_json, suite_hash = read_json(SUITE_PATH)
    suite = ScenarioSuite.model_validate(suite_json)
    captures = []
    with TestClient(app) as client:
        for scenario in suite.scenarios:
            response = client.post(
                "/v1/recommendations/baseline", json=suite.request_for(scenario).model_dump()
            )
            captures.append(
                {
                    "case_id": scenario.case_id,
                    "status_code": response.status_code,
                    "body": response.json(),
                }
            )
    return (
        suite,
        suite_hash,
        {
            "schema_version": 1,
            "suite_sha256": suite_hash,
            "algorithm": suite.algorithm,
            "responses": captures,
        },
    )


def test_frozen_authored_cases_pass_and_do_not_claim_relevance_metrics(frozen_run):
    suite, suite_hash, capture = frozen_run
    report = evaluate(suite, ResponseBundle.model_validate(capture), suite_hash)
    assert report["passed"]
    assert report["scenario_count"] == report["passed_cases"] == 8
    assert report["failed_cases"] == 0
    assert report["issue_case_counts"] == {}
    assert report["data_kind"] == "authored_contract_fixture"
    assert report["ranking_metrics"] == {
        "status": "not_calculated",
        "reason": "no_independent_relevance_judgments",
    }


def test_checker_does_not_call_production_rank_or_filter_helpers(frozen_run, monkeypatch):
    import pubburi_recommendation.baseline as production
    import pubburi_recommendation.main as api

    def forbidden(*_args, **_kwargs):
        pytest.fail("Independent checker invoked a production engine helper")

    monkeypatch.setattr(production, "recommend_baseline", forbidden)
    monkeypatch.setattr(production, "within_range", forbidden)
    monkeypatch.setattr(api, "recommend_baseline", forbidden)
    suite, suite_hash, capture = frozen_run
    assert evaluate(suite, ResponseBundle.model_validate(capture), suite_hash)["passed"]


@pytest.mark.parametrize(
    "case_id, fault, expected_issue",
    [
        ("cold-start-order", "duplicate_product", "duplicate_product"),
        ("cold-start-order", "unknown_candidate", "unknown_candidate"),
        ("cold-start-order", "unavailable", "unavailable"),
        ("hard-constraint-intersection", "excluded_product", "excluded_product"),
        ("hard-constraint-intersection", "wrong_category", "category_mismatch"),
        ("hard-constraint-intersection", "unknown_price", "price_unknown"),
        ("inclusive-bounds-before-limit", "unknown_abv", "abv_unknown"),
        ("inclusive-bounds-before-limit", "below_min", "price_below_min"),
        ("hard-constraint-intersection", "above_max", "abv_above_max"),
        ("cold-start-order", "wrong_order", "b0_order_mismatch"),
        ("cold-start-order", "wrong_count", "eligible_count_mismatch"),
        ("empty-catalog", "wrong_fallback", "fallback_reason_mismatch"),
        ("cold-start-order", "inactive_reason", "reason_mismatch"),
        ("cold-start-order", "duplicate_reason", "duplicate_reason"),
        ("cold-start-order", "invalid_schema", "response_schema_invalid"),
        ("cold-start-order", "http_failure", "unexpected_http_status"),
    ],
)
def test_injected_faults_are_detected(frozen_run, case_id, fault, expected_issue):
    suite, suite_hash, capture = frozen_run
    changed = copy.deepcopy(capture)
    response = next(row for row in changed["responses"] if row["case_id"] == case_id)
    body = response["body"]
    replacements = {
        "unknown_candidate": 999,
        "unavailable": 106,
        "excluded_product": 108,
        "wrong_category": 103,
        "unknown_price": 104,
        "unknown_abv": 105,
        "below_min": 107,
        "above_max": 106,
    }
    if fault in replacements:
        body["items"][0]["product_id"] = replacements[fault]
    elif fault == "duplicate_product":
        body["items"].append(copy.deepcopy(body["items"][0]))
    elif fault == "wrong_order":
        body["items"].reverse()
    elif fault == "wrong_count":
        body["eligible_count"] += 1
    elif fault == "wrong_fallback":
        body["fallback_reason"] = None
    elif fault == "inactive_reason":
        body["items"][0]["reasons"].append("price_within_range")
    elif fault == "duplicate_reason":
        body["items"][0]["reasons"].append("available")
    elif fault == "invalid_schema":
        body["items"][0]["product_id"] = True
    elif fault == "http_failure":
        response["status_code"] = 500
    report = evaluate(suite, ResponseBundle.model_validate(changed), suite_hash)
    failed = next(row for row in report["cases"] if row["case_id"] == case_id)
    assert not report["passed"]
    assert expected_issue in failed["issues"]


@pytest.mark.parametrize(
    "coverage_fault, issue",
    [
        ("missing", "missing_response"),
        ("duplicate", "duplicate_response"),
        ("unexpected", "unexpected_case_response"),
    ],
)
def test_case_coverage_cannot_be_replaced_by_partial_or_unrelated_success(
    frozen_run, coverage_fault, issue
):
    suite, suite_hash, capture = frozen_run
    changed = copy.deepcopy(capture)
    if coverage_fault == "missing":
        changed["responses"].pop()
    else:
        row = copy.deepcopy(changed["responses"][0])
        if coverage_fault == "unexpected":
            row["case_id"] = "unregistered-case"
        changed["responses"].append(row)
    report = evaluate(suite, ResponseBundle.model_validate(changed), suite_hash)
    assert not report["passed"]
    assert issue in report["global_issues"] or any(
        issue in row["issues"] for row in report["cases"]
    )


@pytest.mark.parametrize(
    "field, value, message",
    [
        ("suite_sha256", "b" * 64, "suite_snapshot_hash_mismatch"),
        ("algorithm", "another-algorithm", "bundle_algorithm_mismatch"),
    ],
)
def test_capture_is_bound_to_exact_spec_and_algorithm(frozen_run, field, value, message):
    suite, suite_hash, capture = frozen_run
    changed = copy.deepcopy(capture)
    changed[field] = value
    with pytest.raises(EvaluationInputError, match=message):
        evaluate(suite, ResponseBundle.model_validate(changed), suite_hash)


@pytest.mark.parametrize(
    "fault",
    [
        "catalog_duplicate",
        "case_duplicate",
        "unknown_candidate",
        "candidate_duplicate",
        "false_truth",
        "false_order",
        "no_cases",
    ],
)
def test_contradictory_or_ambiguous_spec_is_rejected(frozen_run, fault):
    suite, _, _ = frozen_run
    spec = suite.model_dump()
    if fault == "catalog_duplicate":
        spec["catalog"].append(spec["catalog"][0])
    elif fault == "case_duplicate":
        spec["scenarios"].append(spec["scenarios"][0])
    elif fault == "unknown_candidate":
        spec["scenarios"][0]["candidate_ids"].append(999)
    elif fault == "candidate_duplicate":
        spec["scenarios"][0]["candidate_ids"].append(101)
    elif fault == "false_truth":
        spec["scenarios"][0]["expected_eligible_ids"].remove(101)
    elif fault == "false_order":
        spec["scenarios"][0]["expected_item_ids"].reverse()
    elif fault == "no_cases":
        spec["scenarios"] = []
    with pytest.raises(ValidationError):
        ScenarioSuite.model_validate(spec)


def generic_spec(frozen_run):
    original, suite_hash, capture = frozen_run
    spec = original.model_dump()
    spec["algorithm"] = "fixture-model"
    spec["ordering_policy"] = "constraints_only"
    for case in spec["scenarios"]:
        case["expected_item_count"] = len(case["expected_item_ids"])
        case["expected_item_ids"] = None
    captured = copy.deepcopy(capture)
    captured["algorithm"] = "fixture-model"
    for row in captured["responses"]:
        row["body"]["algorithm"] = "fixture-model"
        row["body"]["items"].reverse()
        for item in row["body"]["items"]:
            item["reasons"].remove("deterministic_baseline")
            item["reasons"].append("fixture-model-reason")
            item["score"] = 0.5  # The constraint checker must not grade this as relevance.
    return ScenarioSuite.model_validate(spec), suite_hash, captured


def test_constraint_mode_does_not_force_b0_ranking_or_grade_model_scores(frozen_run):
    spec, suite_hash, captured = generic_spec(frozen_run)
    report = evaluate(spec, ResponseBundle.model_validate(captured), suite_hash)
    assert report["passed"]
    assert report["ordering_policy"] == "constraints_only"
    assert report["response_contract_scope"] == "minimal_candidate_envelope_only"
    assert report["ranking_metrics"]["status"] == "not_calculated"


def test_constraint_mode_still_detects_ineligible_items_and_false_reason_codes(frozen_run):
    spec, suite_hash, captured = generic_spec(frozen_run)
    first = captured["responses"][0]["body"]["items"][0]
    first["product_id"] = 106
    first["reasons"].append("abv_within_range")
    report = evaluate(spec, ResponseBundle.model_validate(captured), suite_hash)
    assert "unavailable" in report["cases"][0]["issues"]
    assert "inactive_constraint_reason" in report["cases"][0]["issues"]


def test_constraint_mode_rejects_silent_order_truth_and_b0_policy_on_other_models(frozen_run):
    original, _, _ = frozen_run
    spec = original.model_dump()
    spec["algorithm"] = "fixture-model"
    with pytest.raises(ValidationError, match="b0_order_policy_requires_b0_algorithm"):
        ScenarioSuite.model_validate(spec)
    spec["ordering_policy"] = "constraints_only"
    with pytest.raises(ValidationError, match="constraints_only_has_no_order_judgments"):
        ScenarioSuite.model_validate(spec)


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "pubburi_recommendation.scenario_evaluation", *map(str, args)],
        capture_output=True,
        text=True,
    )


def test_cli_exit_codes_safe_reports_and_preservation(frozen_run, tmp_path):
    _, _, captured = frozen_run
    responses = tmp_path / "responses.json"
    responses.write_text(json.dumps(captured))
    output = tmp_path / "reports" / "evaluation.json"
    args = ["--suite", SUITE_PATH, "--responses", responses, "--output", output]
    success = run_cli(*args)
    assert success.returncode == 0
    assert json.loads(output.read_text())["passed"]
    preserved = output.read_bytes()
    assert run_cli(*args).returncode == 2
    assert output.read_bytes() == preserved
    changed = copy.deepcopy(captured)
    changed["responses"][0]["body"] = {"private-input-marker": "must-not-be-echoed"}
    responses.write_text(json.dumps(changed))
    failed_output = tmp_path / "reports" / "failed.json"
    failed = run_cli("--suite", SUITE_PATH, "--responses", responses, "--output", failed_output)
    assert failed.returncode == 1
    assert "private-input-marker" not in failed_output.read_text() + failed.stdout + failed.stderr
    responses.write_text('{"invalid":"private-input-marker"}')
    invalid = run_cli(
        "--suite",
        SUITE_PATH,
        "--responses",
        responses,
        "--output",
        tmp_path / "reports" / "invalid.json",
    )
    assert invalid.returncode == 2
    assert "private-input-marker" not in invalid.stdout + invalid.stderr


def test_cli_rejects_public_report_path(frozen_run, tmp_path):
    _, _, captured = frozen_run
    responses = tmp_path / "responses.json"
    responses.write_text(json.dumps(captured))
    output = tmp_path / "public.json"
    result = run_cli("--suite", SUITE_PATH, "--responses", responses, "--output", output)
    assert result.returncode == 2
    assert "report_requires_private_or_reports_directory" in result.stderr
    assert not output.exists()
