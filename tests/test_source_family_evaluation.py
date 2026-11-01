"""Authored fact judgments verify metrics and held-out transforms, never user quality."""

import copy
import math

import pytest
from pydantic import ValidationError
from test_source_family_experiment import (
    records_fixture,
    spec_fixture,
)

from pubburi_recommendation.catalog_audit import AuditError
from pubburi_recommendation.source_family_evaluation import (
    FamilyRetrievalCase,
    aggregate_retrieval,
    inspect_retrieval,
)
from pubburi_recommendation.source_family_experiment import FamilyExperiment, fit_representation


def case_fixture(**changes):
    return {
        "case_id": "authored-heldout-fact",
        "query_id": "Q3",
        "candidate_ids": ["Q1", "Q2"],
        "relevant_ids": ["Q2"],
        "cutoffs": [1, 2],
        "fact_basis": "Declared authored query and Q2 share exact Q11; Q1 has a different class.",
        **changes,
    }


def retrieval_inputs():
    spec = spec_fixture(retrieval_cases=[case_fixture()])
    spec["expected_facts"]["Q3"]["instance_of_ids"] = ["Q11"]
    records = records_fixture()
    records[2]["instance_of_ids"] = ["Q11"]
    return FamilyExperiment.model_validate(spec), records


def test_fit_only_training_partition_and_transform_retrieves_declared_fact():
    spec, records = retrieval_inputs()
    result = fit_representation(spec, records, {})
    gold = result["ranking_metrics"]
    query = gold["cases"][0]
    assert query["reference_source_id_order"] == ["Q1", "Q2"]
    assert [row["source_record_id"] for row in query["representation_cosine"]] == ["Q2", "Q1"]
    assert query["representation_cosine"][0]["score"] == pytest.approx(1)
    assert query["reference_metrics"]["at_k"]["1"] == {"recall": 0, "ndcg": 0}
    assert query["representation_metrics"]["at_k"]["1"] == {"recall": 1, "ndcg": 1}
    assert query["reference_metrics"]["at_k"]["2"]["ndcg"] == pytest.approx(1 / math.log2(3))
    no_eval = spec.model_copy(update={"retrieval_cases": []})
    old = fit_representation(no_eval, records, {})
    assert result["fit_fingerprint"] == old["fit_fingerprint"]
    assert result["fitted_parameters"] == old["fitted_parameters"]
    assert result["grain"] == "reviewed_source_product_family_not_sellable_sku"


def test_no_positive_query_is_omitted_with_explicit_macro_denominator():
    positive = inspect_retrieval(
        FamilyRetrievalCase.model_validate(case_fixture()),
        [{"source_record_id": "Q2", "score": 1.0}, {"source_record_id": "Q1", "score": 0.0}],
    )
    empty = inspect_retrieval(
        FamilyRetrievalCase.model_validate(case_fixture(case_id="no-match", relevant_ids=[])),
        [{"source_record_id": "Q1", "score": 0.0}, {"source_record_id": "Q2", "score": 0.0}],
    )
    assert empty["representation_metrics"] == {
        "status": "not_calculated",
        "reason": "no_positive_fact_judgments",
    }
    report = aggregate_retrieval([positive, empty])
    assert report["query_count"] == 2 and report["positive_label_queries"] == 1
    assert report["omitted_no_positive_queries"] == 1
    assert report["macro_means"]["representation_metrics"]["1"] == {
        "queries": 1,
        "mean_recall": 1,
        "mean_ndcg": 1,
    }
    assert aggregate_retrieval([empty])["status"] == "not_calculated"


@pytest.mark.parametrize(
    "mutation",
    [
        "fit-query",
        "heldout-candidate",
        "unknown-id",
        "false-positive",
        "false-negative",
        "duplicate-case",
    ],
)
def test_invalid_partition_or_manual_judgment_is_rejected_before_fit(mutation):
    spec, _ = retrieval_inputs()
    data = spec.model_dump()
    case = data["retrieval_cases"][0]
    if mutation == "fit-query":
        case["query_id"] = "Q1"
        case["candidate_ids"] = ["Q2"]
    elif mutation == "heldout-candidate":
        case["query_id"] = "Q2"
        case["candidate_ids"] = ["Q3"]
        case["relevant_ids"] = ["Q3"]
    elif mutation == "unknown-id":
        case["candidate_ids"] = ["Q2", "Q999"]
    elif mutation == "false-positive":
        case["relevant_ids"] = ["Q1", "Q2"]
    elif mutation == "false-negative":
        case["relevant_ids"] = []
    else:
        data["retrieval_cases"].append(copy.deepcopy(case))
    with pytest.raises(ValidationError):
        FamilyExperiment.model_validate(data)


def test_case_rejects_self_duplicates_unknown_gold_and_ambiguous_cutoffs():
    for changes in (
        {"query_id": "Q1"},
        {"candidate_ids": ["Q1", "Q1"]},
        {"relevant_ids": ["Q99"]},
        {"relevant_ids": ["Q2", "Q2"]},
        {"cutoffs": [2, 1]},
        {"cutoffs": [True]},
        {"cutoffs": [0]},
    ):
        with pytest.raises(ValidationError):
            FamilyRetrievalCase.model_validate(case_fixture(**changes))


def test_result_inspector_rejects_missing_duplicate_unknown_unsorted_and_nonfinite_scores():
    case = FamilyRetrievalCase.model_validate(case_fixture())
    for rows in (
        [{"source_record_id": "Q1", "score": 0.0}],
        [{"source_record_id": "Q1", "score": 0.0}] * 2,
        [{"source_record_id": "Q1", "score": 0.0}, {"source_record_id": "Q99", "score": 0.0}],
        [{"source_record_id": "Q2", "score": 0.0}, {"source_record_id": "Q1", "score": 0.0}],
        [
            {"source_record_id": "Q1", "score": float("nan")},
            {"source_record_id": "Q2", "score": 0.0},
        ],
        [{"source_record_id": "Q1", "score": 1.1}, {"source_record_id": "Q2", "score": 0.0}],
    ):
        with pytest.raises((AuditError, ValidationError)):
            inspect_retrieval(case, rows)


def test_heldout_unseen_style_retains_oov_without_changing_training_parameters():
    spec, records = retrieval_inputs()
    original = fit_representation(spec, records, {})
    changed = spec.model_dump()
    changed["expected_facts"]["Q3"]["instance_of_ids"] = ["Q999"]
    changed["retrieval_cases"][0]["relevant_ids"] = []
    records[2]["instance_of_ids"] = ["Q999"]
    result = fit_representation(FamilyExperiment.model_validate(changed), records, {})
    assert result["fit_fingerprint"] == original["fit_fingerprint"]
    assert result["fitted_parameters"] == original["fitted_parameters"]
    assert result["transformed"][0]["unknown_tokens"] == ["instance_of:Q999"]
    assert result["ranking_metrics"]["status"] == "not_calculated"
    assert [
        row["source_record_id"]
        for row in result["ranking_metrics"]["cases"][0]["representation_cosine"]
    ] == ["Q1", "Q2"]
