"""Frozen authored SVD comparisons test leakage/authority, never service recommendation quality."""

import copy
import json
import math
import subprocess
import sys
from unittest.mock import patch

import numpy as np
import pytest
import sklearn
from pydantic import ValidationError
from test_source_family_cohort import ROOT, inputs, sha
from test_source_family_evaluation import case_fixture

from pubburi_recommendation import source_representation_comparison as comparison_module
from pubburi_recommendation.catalog_audit import AuditError
from pubburi_recommendation.source_family_cohort import CohortExperiment, load_cohort, run_cohort
from pubburi_recommendation.source_family_evaluation import FamilyRetrievalCase, inspect_retrieval
from pubburi_recommendation.source_representation_comparison import (
    MEASUREMENTS,
    ComparisonSpec,
    compare_representation,
)


def prepared(tmp_path):
    spec, manifest, paths = inputs(tmp_path)
    spec_path = tmp_path / "cohort.json"
    spec_path.write_text(json.dumps(spec.model_dump()))
    records, authorities = load_cohort(spec, manifest, paths)
    baseline = run_cohort(
        spec,
        records,
        {
            "spec_sha256": sha(spec_path),
            "manifest_sha256": sha(ROOT / "sources/wikidata-structured.json"),
            **authorities,
        },
    )
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n")
    config = {
        "schema_version": 1,
        "algorithm": "source-family-tfidf-svd-comparison-v1",
        "frozen_at_utc": "2026-10-31T00:00:00+00:00",
        "base_spec_sha256": sha(spec_path),
        "baseline_report_sha256": sha(baseline_path),
        "baseline_fingerprint": baseline["fit_fingerprint"],
        "evidence_kind": "authored_regression_fixture",
        "sklearn_version": sklearn.__version__,
        "n_components": 1,
        "random_state": 0,
        "svd_algorithm": "randomized",
        "n_iter": 7,
        "n_oversamples": 10,
        "power_iteration_normalizer": "QR",
        "normalization": "l2_tfidf_then_l2_latent",
        "retrieval_case_ids": [case.case_id for case in spec.retrieval_cases],
        "predeclared_measurements": MEASUREMENTS,
        "decision_scope": "representation_adequacy_only_not_service_adoption_or_quality",
        "no_parameter_sweep_or_heldout_tuning": True,
    }
    config_path = tmp_path / "comparison.json"
    config_path.write_text(json.dumps(config))
    output = tmp_path / ".pubburi" / "comparison-report.json"
    arguments = [
        "--manifest",
        str(ROOT / "sources/wikidata-structured.json"),
        "--spec",
        str(spec_path),
        "--baseline-report",
        str(baseline_path),
        "--comparison-spec",
        str(config_path),
        "--output",
        str(output),
    ]
    for name, binding in paths.items():
        arguments += ["--snapshot", name, *map(str, binding)]
    return spec, records, baseline, config, arguments, output


def test_actual_train_fit_measures_uncentered_energy_separately_from_centered_variance(tmp_path):
    spec, _, baseline, config, _, _ = prepared(tmp_path)
    before = copy.deepcopy(baseline)
    result = compare_representation(ComparisonSpec.model_validate(config), spec, baseline)
    # Two unit TF-IDF rows share only producer:Q20; the leading singular vector captures
    # the common direction. These analytic fit expectations do not use production scores.
    rare_idf = math.log(3 / 2) + 1
    overlap = 1 / (rare_idf**2 + 1)
    expected_retained = (1 + overlap) / 2
    measured = result["training_measurements"]
    assert measured["retained_frobenius_energy_ratio"] == pytest.approx(expected_retained)
    assert measured["reconstruction_relative_frobenius_error"] == pytest.approx(
        math.sqrt(1 - expected_retained)
    )
    assert measured["explained_variance_ratio_sum"] == pytest.approx(0, abs=1e-12)
    assert (
        result["fitted_parameters"]["numeric_fit"] == baseline["fitted_parameters"]["numeric_fit"]
    )
    assert result["transformed"][0]["numeric"] == baseline["transformed"][0]["numeric"]
    assert result["adoption"] == "not_adopted_by_offline_comparison"
    assert result["fit_records"] == 2 and result["transform_records"] == 1
    assert compare_representation(ComparisonSpec.model_validate(config), spec, baseline) == result
    assert baseline == before


def test_tfidf_and_svd_fit_only_training_rows_and_heldout_transform_never_refits(
    tmp_path, monkeypatch
):
    spec, _, baseline, config, _, _ = prepared(tmp_path)
    vectorizer_type = comparison_module.TfidfVectorizer
    reducer_type = comparison_module.TruncatedSVD
    tfidf_fit = vectorizer_type.fit_transform
    svd_fit = reducer_type.fit_transform
    seen_documents, seen_shapes = [], []

    def record_tfidf(self, documents, *args, **kwargs):
        seen_documents.append(copy.deepcopy(documents))
        return tfidf_fit(self, documents, *args, **kwargs)

    def record_svd(self, matrix, *args, **kwargs):
        seen_shapes.append(matrix.shape)
        return svd_fit(self, matrix, *args, **kwargs)

    monkeypatch.setattr(vectorizer_type, "fit_transform", record_tfidf)
    monkeypatch.setattr(reducer_type, "fit_transform", record_svd)
    result = compare_representation(ComparisonSpec.model_validate(config), spec, baseline)
    assert seen_documents == [
        [["instance_of:Q10", "producer:Q20"], ["instance_of:Q11", "producer:Q20"]]
    ]
    assert seen_shapes == [(2, 3)]
    assert "producer:Q99" not in result["fitted_parameters"]["vocabulary"]
    assert result["transformed"][0]["unknown_tokens"] == ["producer:Q99"]


def test_heldout_facts_change_outputs_but_never_candidate_parameters_or_fingerprint(tmp_path):
    spec, records, baseline, config, _, _ = prepared(tmp_path)
    original = compare_representation(ComparisonSpec.model_validate(config), spec, baseline)
    changed = spec.model_dump()
    changed["expected_facts"]["Q3"].update(
        instance_of_ids=["Q999"], abv_percent=100, volume_ml=1_000_000
    )
    changed["retrieval_cases"][0]["relevant_ids"] = []
    altered = CohortExperiment.model_validate(changed)
    altered_records = copy.deepcopy(records)
    next(row for row in altered_records if row["source_record_id"] == "Q3").update(
        altered.expected_facts["Q3"].model_dump()
    )
    new_baseline = run_cohort(altered, altered_records, {})
    result = compare_representation(ComparisonSpec.model_validate(config), altered, new_baseline)
    assert result["fitted_parameters"] == original["fitted_parameters"]
    assert result["fit_fingerprint"] == original["fit_fingerprint"]
    assert result["transformed"] != original["transformed"]
    assert result["transform_coverage"]["zero_source_text_vectors"] == 1
    assert result["transform_coverage"]["zero_latent_vectors"] == 1
    assert result["transformed"][0]["normalized_latent_vector"] == [0.0]
    assert result["ranking_metrics"]["positive_label_queries"] == 0
    assert result["ranking_metrics"]["omitted_no_positive_queries"] == 1
    assert all(
        row["score"] == 0 for row in result["ranking_metrics"]["cases"][0]["representation_cosine"]
    )
    assert result["ranking_metrics"]["macro_means"]["representation_metrics"] == {}


def test_signed_cosines_keep_negative_order_without_weakening_nonnegative_baseline_validation():
    case = FamilyRetrievalCase.model_validate(case_fixture())
    rows = [{"source_record_id": "Q2", "score": -0.1}, {"source_record_id": "Q1", "score": -0.9}]
    with pytest.raises(ValidationError):
        inspect_retrieval(case, rows)
    result = inspect_retrieval(case, rows, signed_cosine=True)
    assert result["representation_cosine"] == rows
    assert result["representation_metrics"]["at_k"]["1"] == {"recall": 1, "ndcg": 1}
    with pytest.raises(AuditError, match="score_and_source_id_ties"):
        inspect_retrieval(case, list(reversed(rows)), signed_cosine=True)


@pytest.mark.parametrize("score", [-1.1, 1.1, float("nan"), float("inf"), True])
def test_signed_metrics_still_require_bounded_finite_strict_scores(score):
    case = FamilyRetrievalCase.model_validate(case_fixture())
    with pytest.raises(ValidationError):
        inspect_retrieval(
            case,
            [{"source_record_id": "Q2", "score": score}, {"source_record_id": "Q1", "score": 0.0}],
            signed_cosine=True,
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("n_components", True),
        ("n_components", 0),
        ("random_state", -1),
        ("svd_algorithm", "arpack"),
        ("n_iter", 0),
        ("n_oversamples", 0),
        ("normalization", "no_normalization"),
        ("power_iteration_normalizer", "auto"),
        ("retrieval_case_ids", ["a", "a"]),
        ("predeclared_measurements", []),
        ("frozen_at_utc", "2026-10-31T00:00:00+09:00"),
        ("no_parameter_sweep_or_heldout_tuning", False),
    ],
)
def test_comparison_requires_explicit_strict_frozen_protocol(tmp_path, field, value):
    *_, config, _, _ = prepared(tmp_path)
    config[field] = value
    with pytest.raises(ValidationError):
        ComparisonSpec.model_validate(config)


@pytest.mark.parametrize(
    "field", ["sklearn_version", "baseline_fingerprint", "evidence_kind", "retrieval_case_ids"]
)
def test_changed_protocol_is_rejected_before_candidate_fit(tmp_path, field, monkeypatch):
    spec, _, baseline, config, _, _ = prepared(tmp_path)
    config[field] = {
        "sklearn_version": "different",
        "baseline_fingerprint": "f" * 64,
        "evidence_kind": "reviewed_public_source",
        "retrieval_case_ids": ["different-case"],
    }[field]
    monkeypatch.setattr(
        comparison_module.TruncatedSVD, "fit_transform", lambda *_: pytest.fail("fit forbidden")
    )
    with pytest.raises(AuditError, match="protocol_conflicts"):
        compare_representation(ComparisonSpec.model_validate(config), spec, baseline)


@pytest.mark.parametrize("mode", ["no-reduction", "unknown-rank", "oversized", "future-freeze"])
def test_degenerate_or_unbounded_candidates_are_rejected_before_candidate_fit(
    tmp_path, mode, monkeypatch
):
    spec, _, baseline, config, _, _ = prepared(tmp_path)
    if mode == "no-reduction":
        config["n_components"] = 2
    elif mode == "unknown-rank":
        baseline["fit_text_matrix"]["rank"] = None
    elif mode == "oversized":
        baseline["fit_text_matrix"]["shape"] = [1000, 1001]
    else:
        config["frozen_at_utc"] = "2099-01-01T00:00:00+00:00"
    monkeypatch.setattr(
        comparison_module.TruncatedSVD, "fit_transform", lambda *_: pytest.fail("fit forbidden")
    )
    with pytest.raises(AuditError, match="bounded_nontrivial|cannot_be_future"):
        compare_representation(ComparisonSpec.model_validate(config), spec, baseline)


def test_real_cli_recomputes_exact_baseline_and_publishes_reproducible_private_candidate(tmp_path):
    _, _, baseline, _, arguments, output = prepared(tmp_path)
    command = [
        sys.executable,
        "-m",
        "pubburi_recommendation.source_representation_comparison",
        *arguments,
    ]
    run = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    report = json.loads(output.read_text())
    assert report["baseline"] == baseline and report["candidate"]["fitted"]
    assert not report["network_performed"] and not report["service_mapping_or_adoption_performed"]
    assert report["candidate"]["ranking_metrics"]["query_count"] == 1
    assert report["candidate"]["ranking_metrics"]["positive_label_queries"] == 1
    again = output.with_name("replay.json")
    command[command.index("--output") + 1] = str(again)
    run = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    assert output.read_bytes() == again.read_bytes()
    assert set(json.loads(run.stdout)) == {
        "fit_records",
        "transform_records",
        "latent_dimensions",
        "passed_contract",
    }


@pytest.mark.parametrize(
    "mutation", ["raw", "receipt", "review", "base-spec", "baseline-hash", "baseline-content"]
)
def test_cli_authority_or_baseline_changes_never_fit_candidate_or_publish(
    tmp_path, mutation, monkeypatch, capsys
):
    _, _, _, config, arguments, output = prepared(tmp_path)
    if mutation in ("raw", "receipt", "review"):
        start = arguments.index("--snapshot") + 1
        target = arguments[start + {"raw": 1, "receipt": 2, "review": 3}[mutation]]
        from pathlib import Path

        path = Path(target)
        path.write_text(path.read_text() + " ")
    elif mutation == "base-spec":
        config["base_spec_sha256"] = "f" * 64
    elif mutation == "baseline-hash":
        config["baseline_report_sha256"] = "f" * 64
    else:
        from pathlib import Path

        path = Path(arguments[arguments.index("--baseline-report") + 1])
        data = json.loads(path.read_text())
        data["cohort"]["producer_overlap"] = 1
        path.write_text(json.dumps(data))
        config["baseline_report_sha256"] = sha(path)
    from pathlib import Path

    Path(arguments[arguments.index("--comparison-spec") + 1]).write_text(json.dumps(config))
    monkeypatch.setattr(
        comparison_module.TruncatedSVD, "fit_transform", lambda *_: pytest.fail("fit forbidden")
    )
    with patch.object(sys, "argv", ["source-representation-comparison", *arguments]):
        assert comparison_module.main() == 2
    assert not output.exists()
    captured = capsys.readouterr()
    assert "Source representation comparison failed:" in captured.err
    assert str(tmp_path) not in captured.err and captured.out == ""


def test_existing_output_is_preserved_before_read_or_fit(tmp_path, monkeypatch):
    *_, arguments, output = prepared(tmp_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("existing-owned-report")
    monkeypatch.setattr(comparison_module, "read_json", lambda *_: pytest.fail("read forbidden"))
    with patch.object(sys, "argv", ["source-representation-comparison", *arguments]):
        assert comparison_module.main() == 2
    assert output.read_text() == "existing-owned-report"


def test_report_parameters_and_training_measurements_are_finite(tmp_path):
    spec, _, baseline, config, _, _ = prepared(tmp_path)
    report = compare_representation(ComparisonSpec.model_validate(config), spec, baseline)
    assert np.isfinite(report["fitted_parameters"]["components"]).all()
    assert 0 <= report["training_measurements"]["retained_frobenius_energy_ratio"] <= 1
    assert 0 <= report["training_measurements"]["reconstruction_relative_frobenius_error"] <= 1
