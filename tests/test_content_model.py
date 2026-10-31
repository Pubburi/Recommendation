import copy
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from pubburi_recommendation.baseline import Constraints
from pubburi_recommendation.catalog_audit import read_json
from pubburi_recommendation.content_experiment import ContentExperiment, run_experiment
from pubburi_recommendation.content_model import (
    ContentProduct,
    ContentProfile,
    FittedContentModel,
    product_tokens,
)
from pubburi_recommendation.scenario_evaluation import eligibility_issues

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "evaluation/content-fit-v1.json"


def product(pid, **values):
    return ContentProduct(product_id=pid, sku_group=f"sku-{pid}", available=True, **values)


def model_products():
    return [
        product(
            1, category="a", taste_tags=["단"], aroma_tags=["단"], abv_percent=0, volume_ml=100
        ),
        product(
            2, category="a", taste_tags=["쓴"], aroma_tags=["곡물"], abv_percent=10, volume_ml=200
        ),
    ]


def load_spec():
    payload, sha256 = read_json(SPEC_PATH)
    return ContentExperiment.model_validate(payload), sha256


def test_actual_fit_vocabulary_idf_and_numeric_range_are_training_only():
    training = model_products()
    model = FittedContentModel.fit(training)
    assert set(model.vectorizer.vocabulary_) == {
        "category:a",
        "taste:단",
        "aroma:단",
        "taste:쓴",
        "aroma:곡물",
    }
    idf = dict(zip(model.vectorizer.get_feature_names_out(), model.vectorizer.idf_, strict=True))
    assert idf["category:a"] == 1
    assert idf["taste:단"] == pytest.approx(math.log(3 / 2) + 1)
    assert model.summary["numeric_fit"]["abv_percent"]["minimum"] == 0
    assert model.summary["numeric_fit"]["abv_percent"]["maximum"] == 10
    assert model.summary["numeric_fit"]["volume_ml"]["minimum"] == 100
    assert model.summary["numeric_fit"]["volume_ml"]["maximum"] == 200
    before = copy.deepcopy(model.summary)
    fingerprint = model.fingerprint
    model.rank(
        [product(100, taste_tags=["학습 밖"], abv_percent=100, volume_ml=1_000_000)],
        ContentProfile(taste_tags=["학습 밖"], preferred_abv_percent=100),
    )
    assert "taste:학습 밖" not in model.vectorizer.vocabulary_
    assert model.summary == before and model.fingerprint == fingerprint


def test_atomic_korean_one_character_and_multiword_tags_keep_namespace():
    training = [
        product(1, taste_tags=["단", "가벼운 질감"], aroma_tags=["단"]),
        product(2, taste_tags=["쓴"]),
    ]
    model = FittedContentModel.fit(training)
    assert set(model.vectorizer.vocabulary_) == {
        "taste:단",
        "taste:가벼운 질감",
        "aroma:단",
        "taste:쓴",
    }
    result = model.rank(training, ContentProfile(taste_tags=["단"]))
    assert [part.feature for part in result.items[0].contributions] == ["taste:단"]
    aroma = model.rank(training, ContentProfile(aroma_tags=["단"]))
    assert [part.feature for part in aroma.items[0].contributions] == ["aroma:단"]
    assert product_tokens(product(9, taste_tags=["  LIGHT BODY  "])) == ["taste:light body"]


def test_score_is_sum_of_real_contributions_with_equal_active_component_weights():
    training = model_products()
    model = FittedContentModel.fit(training)
    result = model.rank(
        training,
        ContentProfile(
            categories=["a"],
            taste_tags=["단"],
            aroma_tags=["단"],
            preferred_abv_percent=0,
            preferred_volume_ml=100,
        ),
    )
    exact = result.items[0]
    assert exact.product_id == 1 and exact.score == pytest.approx(1)
    assert sum(part.contribution for part in exact.contributions) == pytest.approx(exact.score)
    components = {}
    for part in exact.contributions:
        components[part.component] = components.get(part.component, 0) + part.contribution
    assert components == pytest.approx({"text": 1 / 3, "abv_percent": 1 / 3, "volume_ml": 1 / 3})
    assert all(math.isfinite(item.score) and 0 <= item.score <= 1 for item in result.items)


def test_unknown_numeric_is_not_zero_or_numeric_reason_and_does_not_shrink_denominator():
    model = FittedContentModel.fit(model_products())
    unknown = product(3, category="a", taste_tags=["단"], aroma_tags=["단"])
    known = product(4, category="a", taste_tags=["단"], aroma_tags=["단"], abv_percent=0)
    result = model.rank(
        [unknown, known],
        ContentProfile(
            categories=["a"], taste_tags=["단"], aroma_tags=["단"], preferred_abv_percent=0
        ),
    )
    assert [item.product_id for item in result.items] == [4, 3]
    assert result.items[0].score == pytest.approx(1)
    assert result.items[1].score == pytest.approx(0.5)
    assert {part.component for part in result.items[1].contributions} == {"text"}
    numeric_only = model.rank([unknown, known], ContentProfile(preferred_abv_percent=0))
    assert numeric_only.items[0].score == 1
    assert numeric_only.items[1].score == 0 and not numeric_only.items[1].contributions


@pytest.mark.parametrize("profile", [ContentProfile(), ContentProfile(taste_tags=["미등록"])])
def test_cold_start_and_oov_query_use_deterministic_b0_fallback(profile):
    model = FittedContentModel.fit(model_products())
    response = model.rank([product(5), product(3)], profile)
    assert [item.product_id for item in response.items] == [3, 5]
    assert response.fallback_reason == "no_supported_preferences"
    assert all(
        item.score == 0
        and item.reasons == ["available", "deterministic_baseline"]
        and not item.contributions
        for item in response.items
    )
    assert response.unknown_profile_tokens == len(profile.taste_tags)


def test_all_unknown_or_constant_training_columns_are_not_fake_numeric_models():
    model = FittedContentModel.fit(
        [product(1, taste_tags=None, aroma_tags=[]), product(2, abv_percent=0)]
    )
    assert model.vectorizer is None and not model.scalers
    assert model.summary["unknown_tags"] == {"taste_tags": 2, "aroma_tags": 1}
    assert model.summary["reviewed_empty_tags"] == {"taste_tags": 0, "aroma_tags": 1}
    assert model.summary["numeric_fit"]["abv_percent"] == {
        "observed_count": 1,
        "missing_count": 1,
        "active": False,
        "minimum": 0,
        "maximum": 0,
    }
    assert (
        model.rank(
            [product(9, abv_percent=0)], ContentProfile(preferred_abv_percent=0)
        ).fallback_reason
        == "no_supported_preferences"
    )


def test_known_query_but_zero_candidate_vectors_uses_b0_without_similarity_claim():
    model = FittedContentModel.fit(model_products())
    result = model.rank(
        [product(9), product(3, taste_tags=["미등록"])], ContentProfile(taste_tags=["단"])
    )
    assert [item.product_id for item in result.items] == [3, 9]
    assert result.fallback_reason == "no_matching_features"
    assert all(
        item.score == 0 and "content_similarity" not in item.reasons for item in result.items
    )
    assert all("deterministic_baseline" in item.reasons for item in result.items)


def test_hard_constraints_precede_similarity_and_limit_independently_checked():
    model = FittedContentModel.fit(model_products())
    candidates = [
        product(10, category="a", taste_tags=["단"], abv_percent=5, price_krw=1000),
        product(11, category="a", taste_tags=["단"], abv_percent=None, price_krw=1000),
        product(12, category="a", taste_tags=["단"], abv_percent=0, price_krw=0),
        product(13, category="b", taste_tags=["단"], abv_percent=5, price_krw=1000),
        product(14, category="a", taste_tags=["単"], abv_percent=5, price_krw=None),
        ContentProduct(
            product_id=15,
            sku_group="off",
            available=False,
            category="a",
            abv_percent=5,
            price_krw=1000,
        ),
    ]
    constraints = Constraints(
        categories=["a"], max_price_krw=1000, max_abv_percent=5, exclude_product_ids=[10]
    )
    result = model.rank(candidates, ContentProfile(taste_tags=["단"]), constraints, limit=1)
    assert result.eligible_count == 1 and [item.product_id for item in result.items] == [12]
    by_id = {p.product_id: p for p in candidates}
    assert all(not eligibility_issues(by_id[item.product_id], constraints) for item in result.items)
    assert set(result.items[0].reasons) >= {
        "available",
        "category_match",
        "price_within_range",
        "abv_within_range",
    }
    empty = model.rank(
        candidates, ContentProfile(taste_tags=["단"]), Constraints(categories=["none"])
    )
    assert empty.items == [] and empty.fallback_reason == "no_eligible_products"


def test_permutation_ties_fit_and_transform_are_reproducible_without_refit(monkeypatch):
    training = model_products()
    left = FittedContentModel.fit(training)
    right = FittedContentModel.fit(list(reversed(training)))
    assert left.fingerprint == right.fingerprint

    def forbidden(*args, **kwargs):
        pytest.fail("transform must never call fit")

    monkeypatch.setattr(type(left.vectorizer), "fit", forbidden)
    monkeypatch.setattr(type(left.scalers["abv_percent"]), "fit", forbidden)
    candidates = [product(9, taste_tags=["단"]), product(4, taste_tags=["단"])]
    profile = ContentProfile(taste_tags=["단"])
    assert left.rank(candidates, profile) == right.rank(list(reversed(candidates)), profile)
    assert [item.product_id for item in left.rank(candidates, profile).items] == [4, 9]


def test_similar_product_excludes_anchor_and_respects_explicit_exclusion():
    training = model_products()
    model = FittedContentModel.fit(training)
    candidate = product(
        8, category="a", taste_tags=["단"], aroma_tags=["단"], abv_percent=0, volume_ml=100
    )
    result = model.similar(training[0], [training[0], training[1], candidate])
    assert [item.product_id for item in result.items] == [8, 2]
    assert result.items[0].score == pytest.approx(1)
    excluded = model.similar(
        training[0], [training[0], candidate], Constraints(exclude_product_ids=[8])
    )
    assert excluded.items == []


@pytest.mark.parametrize("anchor_in_candidates", [False, True])
def test_similar_accepts_full_exclusion_budget_without_mutating_constraints(anchor_in_candidates):
    training = model_products()
    model = FittedContentModel.fit(training)
    constraints = Constraints(exclude_product_ids=list(range(1000, 2000)))
    original = constraints.model_dump()
    candidates = [training[1]] + ([training[0]] if anchor_in_candidates else [])
    result = model.similar(training[0], candidates, constraints)
    assert [item.product_id for item in result.items] == [2]
    assert result.eligible_count == 1
    assert constraints.model_dump() == original


def test_similar_still_rejects_duplicate_anchor_candidates_before_removing_anchor():
    training = model_products()
    with pytest.raises(ValueError, match="catalog_product_ids_must_be_unique"):
        FittedContentModel.fit(training).similar(training[0], [training[0], training[0]])


@pytest.mark.parametrize("anchor_in_candidates", [False, True])
def test_reference_experiment_accepts_full_exclusion_budget(anchor_in_candidates):
    payload, sha256 = read_json(SPEC_PATH)
    case = payload["cases"][6]
    if anchor_in_candidates:
        case["reference_product_id"] = 102
        case["expected_eligible_ids"].remove(102)
    case["constraints"] = {"exclude_product_ids": list(range(1000, 2000))}
    spec = ContentExperiment.model_validate(payload)
    original = spec.cases[6].constraints.model_dump()
    result = run_experiment(spec, sha256)["cases"][6]
    assert result["passed_contract"]
    assert case["reference_product_id"] not in result["b0_product_ids"]
    assert case["reference_product_id"] not in [
        item["product_id"] for item in result["b1"]["items"]
    ]
    assert spec.cases[6].constraints.model_dump() == original


@pytest.mark.parametrize(
    "change",
    [
        {"taste_tags": ["단", " 단 "]},
        {"taste_tags": [""]},
        {"aroma_tags": ["x" * 41]},
        {"aroma_tags": [f"tag-{i}" for i in range(21)]},
        {"volume_ml": 0},
        {"volume_ml": True},
        {"abv_percent": float("nan")},
        {"abv_percent": float("inf")},
        {"description": "unreviewed"},
    ],
)
def test_product_input_contract_rejects_invalid_or_unreviewed_fields(change):
    with pytest.raises(ValidationError):
        product(1, **change)


@pytest.mark.parametrize("products", [[], [product(1), product(1)], [dict(product_id=1)]])
def test_fit_requires_bounded_unique_validated_products(products):
    with pytest.raises(ValueError):
        FittedContentModel.fit(products)


@pytest.mark.parametrize("limit", [0, 101, True, 1.5])
def test_rank_limit_is_strict(limit):
    with pytest.raises(ValueError):
        FittedContentModel.fit(model_products()).rank([], ContentProfile(), limit=limit)


def test_group_split_demo_fits_real_estimators_but_has_no_relevance_metrics():
    spec, sha256 = load_spec()
    report = run_experiment(spec, sha256)
    assert report["fit_summary"]["training_products"] == 4
    assert report["fit_summary"]["training_groups"] == 3
    assert report["fit_summary"]["numeric_fit"]["abv_percent"]["maximum"] == 15
    assert report["fit_summary"]["numeric_fit"]["volume_ml"]["minimum"] == 350
    assert report["transform_products"] == 7 and report["transform_groups"] == 6
    assert report["passed_contract_cases"] == report["case_count"] == 8
    explicit = report["cases"][0]
    assert explicit["b0_product_ids"][0] == 101 and explicit["b1"]["items"][0]["product_id"] == 102
    assert report["ranking_metrics"]["status"] == "not_calculated"
    assert run_experiment(spec, sha256) == report


@pytest.mark.parametrize(
    "mutation",
    [
        "group_overlap",
        "uncovered_group",
        "train_candidate",
        "wrong_fact",
        "unknown_reference",
        "both_profile_reference",
    ],
)
def test_partition_or_manual_fact_conflicts_are_rejected(mutation):
    payload, _ = read_json(SPEC_PATH)
    if mutation == "group_overlap":
        payload["transform_group_ids"].append("train-a")
    if mutation == "uncovered_group":
        payload["fit_group_ids"].remove("train-a")
    if mutation == "train_candidate":
        payload["cases"][0]["candidate_ids"].append(1)
    if mutation == "wrong_fact":
        payload["cases"][0]["expected_eligible_ids"].append(105)
    if mutation == "unknown_reference":
        payload["cases"][0]["reference_product_id"] = 999
    if mutation == "both_profile_reference":
        payload["cases"][0]["reference_product_id"] = 1
    with pytest.raises(ValidationError):
        ContentExperiment.model_validate(payload)


def test_cli_writes_new_private_report_and_preserves_existing_output(tmp_path):
    output = tmp_path / ".pubburi" / "run.json"
    command = [
        sys.executable,
        "-m",
        "pubburi_recommendation.content_experiment",
        "--spec",
        str(SPEC_PATH),
        "--output",
        str(output),
    ]
    first = subprocess.run(command, capture_output=True, text=True, check=False)
    assert first.returncode == 0, first.stderr
    content = output.read_bytes()
    assert json.loads(content)["passed_contract"]
    second = subprocess.run(command, capture_output=True, text=True, check=False)
    assert second.returncode == 2 and "existing_report_must_be_preserved" in second.stderr
    assert output.read_bytes() == content
    command[-1] = str(tmp_path / "public.json")
    assert subprocess.run(command, capture_output=True, check=False).returncode == 2
    assert not (tmp_path / "public.json").exists()
