"""R04 authored fact evidence, optional serialization and unchanged B1 decisions."""

import copy
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from pubburi_recommendation.baseline import Constraints
from pubburi_recommendation.content_api import ContentRecommendationRequest, recommend_content
from pubburi_recommendation.content_contracts import (
    ContentProduct,
    ContentProfile,
    TasteScoreEvidence,
)
from pubburi_recommendation.content_explanations import annotate_explanations
from pubburi_recommendation.content_model import FittedContentModel
from pubburi_recommendation.main import app

PATHS = ("content", "exploration", "similar", "context", "feedback")


def request(endpoint="content"):
    rows = (
        (1, "a", True, 0, 330, 0),
        (2, "b", True, 5, 500, 1000),
        (3, "a", True, 0, 330, 0),
        (4, "unknown", True, None, None, None),
        (5, "other", True, 10, 750, 2500),
        (6, "negative", False, 0, 330, 1000),
        (7, "negative", True, 0, 330, 1000),
    )
    catalog = [
        dict(
            product_id=pid,
            sku_group=group,
            available=available,
            category="과실주" if pid == 5 else "맥주",
            price_krw=price,
            abv_percent=abv,
            volume_ml=volume,
            taste_tags=None
            if pid == 4
            else ["다른 태그"]
            if pid == 5
            else ["단,맛", "가벼운\n질감"],
            aroma_tags=[] if pid == 4 else None if pid == 5 else ["배"],
        )
        for pid, group, available, abv, volume, price in rows
    ]
    body = {
        "catalog": catalog,
        "constraints": {
            "categories": ["맥주"],
            "max_price_krw": 1500,
            "min_abv_percent": 0,
            "max_abv_percent": 5,
            "exclude_product_ids": [7],
        },
        "limit": 12,
    }
    if endpoint in ("content", "exploration"):
        body["profile"] = {
            "categories": ["맥주"],
            "taste_tags": ["단,맛", "가벼운\n질감"],
            "aroma_tags": ["배"],
            "preferred_abv_percent": 0,
            "preferred_volume_ml": 330,
        }
    elif endpoint == "similar":
        body["reference_product_id"] = 1
    elif endpoint == "context":
        body["reference_product_ids"] = [1, 6]
    elif endpoint == "feedback":
        body["feedback"] = {"positive_product_ids": [1], "not_interested_product_ids": [6]}
    elif endpoint == "baseline":
        body["catalog"] = [
            {
                k: v
                for k, v in p.items()
                if k in ("product_id", "available", "category", "price_krw", "abv_percent")
            }
            for p in catalog
        ]
    return body


def without_explanations(result):
    result = copy.deepcopy(result)
    for item in result["items"]:
        item.pop("explanation", None)
    return result


@pytest.mark.parametrize("endpoint", PATHS)
def test_opt_in_preserves_every_score_order_reason_and_existing_wire_with_one_fit(
    endpoint, monkeypatch
):
    fit, calls = FittedContentModel.fit, []

    def counted(products):
        calls.append(products)
        return fit(products)

    monkeypatch.setattr(FittedContentModel, "fit", counted)
    body = request(endpoint)
    original = copy.deepcopy(body)
    path = "/v1/recommendations/" + endpoint
    with TestClient(app) as client:
        omitted = client.post(path, json=body)
        explicit_false = client.post(path, json={**body, "include_explanations": False})
        assert omitted.status_code == explicit_false.status_code == 200
        assert omitted.content == explicit_false.content
        assert all("explanation" not in row for row in omitted.json()["items"])
        calls.clear()
        enabled = client.post(path, json={**body, "include_explanations": True})
    assert enabled.status_code == 200 and len(calls) == 1 and body == original
    actual = enabled.json()
    assert without_explanations(actual) == omitted.json()
    assert [row["product_id"] for row in actual["items"]] == (
        [1, 2] if endpoint == "exploration" else [1, 3, 2] if endpoint == "content" else [2]
    )
    for item in actual["items"]:
        explanation = item["explanation"]
        assert explanation["basis"] == "content_similarity"
        assert explanation["comparison"] == (
            {"kind": "profile"}
            if endpoint in ("content", "exploration")
            else {"kind": "reference_product", "product_id": 1}
        )
        assert len(explanation["filter_evidence"]) == 4
        assert {row["kind"] for row in explanation["filter_evidence"]} == {
            "availability_filter",
            "category_filter",
            "price_filter",
            "abv_filter",
        }
        assert explanation["total_positive_contributions"] == len(item["contributions"])
        assert explanation["score_evidence_truncated"]
        assert len(explanation["score_evidence"]) == 3
        assert all(row["contribution"] > 0 for row in explanation["score_evidence"])
        for evidence in explanation["score_evidence"]:
            if evidence["kind"] == "abv_comparison":
                assert evidence["actual_value"] == (5 if item["product_id"] == 2 else 0)
                assert evidence["target_value"] == 0 and evidence["unit"] == "vol%"
            elif evidence["kind"] == "volume_comparison":
                assert evidence["actual_value"] == (500 if item["product_id"] == 2 else 330)
                assert evidence["target_value"] == 330 and evidence["unit"] == "mL"


@pytest.mark.parametrize("endpoint", PATHS)
@pytest.mark.parametrize("value", [None, 1, 0, "true", []])
def test_opt_in_is_strict_boolean_on_all_five_B1_paths(endpoint, value):
    with TestClient(app) as client:
        response = client.post(
            "/v1/recommendations/" + endpoint,
            json={**request(endpoint), "include_explanations": value},
        )
    assert response.status_code == 422


def test_baseline_does_not_accept_or_invent_B1_explanations():
    with TestClient(app) as client:
        result = client.post("/v1/recommendations/baseline", json=request("baseline"))
        assert result.status_code == 200 and "explanation" not in result.text
        assert (
            client.post(
                "/v1/recommendations/baseline",
                json={**request("baseline"), "include_explanations": True},
            ).status_code
            == 422
        )


def test_literal_namespaced_atoms_are_preserved_and_fixed_labels_never_become_HTML():
    atoms = ["단,맛", "가벼운\n질감", "x:y,<tag>"]
    body = {
        "catalog": [{"product_id": 1, "sku_group": "a", "available": True, "taste_tags": atoms}],
        "profile": {"taste_tags": atoms},
        "include_explanations": True,
    }
    result = recommend_content(ContentRecommendationRequest.model_validate(body))
    explanation = result.items[0].explanation
    assert len(explanation.score_evidence) == 3 and not explanation.score_evidence_truncated
    assert {row.actual_value for row in explanation.score_evidence} == set(atoms)
    assert all(
        row.actual_value == row.target_value and row.label == "맛 태그 일치"
        for row in explanation.score_evidence
    )
    assert sum(row.contribution for row in explanation.score_evidence) == pytest.approx(
        result.items[0].score
    )
    with pytest.raises(ValidationError):
        TasteScoreEvidence(actual_value="단", target_value="단", contribution=0)
    with pytest.raises(ValidationError):
        TasteScoreEvidence(actual_value="단", target_value="단", contribution=1, label="<HTML>")


@pytest.mark.parametrize("mode", ["empty_profile", "oov", "no_shared", "constant_numeric"])
def test_baseline_or_zero_evidence_never_claims_preference_or_unknown_numeric_facts(mode):
    catalog = [
        ContentProduct(
            product_id=1, sku_group="a", available=True, taste_tags=["단"], abv_percent=0
        ),
        ContentProduct(
            product_id=2, sku_group="b", available=True, taste_tags=["드라이"], abv_percent=0
        ),
    ]
    profile = ContentProfile()
    constraints = Constraints()
    if mode == "oov":
        profile = ContentProfile(taste_tags=["unregistered"])
    elif mode == "no_shared":
        profile = ContentProfile(taste_tags=["드라이"])
        constraints = Constraints(exclude_product_ids=[2])
    elif mode == "constant_numeric":
        profile = ContentProfile(preferred_abv_percent=0)
    model = FittedContentModel.fit(catalog)
    result = model.rank(catalog, profile, constraints, include_explanations=True)
    assert result.fallback_reason == (
        "no_matching_features" if mode == "no_shared" else "no_supported_preferences"
    )
    for item in result.items:
        explanation = item.explanation
        assert item.score == 0 and explanation.score_evidence == []
        assert explanation.basis == "deterministic_baseline"
        assert explanation.fallback_reason == result.fallback_reason
        assert (
            explanation.total_positive_contributions == 0
            and not explanation.score_evidence_truncated
        )


def test_unknown_numeric_is_not_zero_and_no_shared_row_is_not_falsely_baseline():
    catalog = [
        ContentProduct(product_id=pid, sku_group=str(pid), available=True, abv_percent=abv)
        for pid, abv in ((1, 0), (2, None), (3, 10))
    ]
    result = FittedContentModel.fit(catalog).rank(
        catalog, ContentProfile(preferred_abv_percent=0), include_explanations=True
    )
    assert result.items[0].explanation.score_evidence[0].actual_value == 0
    assert result.items[0].explanation.score_evidence[0].target_value == 0
    assert result.fallback_reason is None
    for item in result.items[1:]:
        assert item.explanation.score_evidence == []
        assert item.explanation.basis == "no_shared_features"
        assert item.explanation.fallback_reason is None


def test_only_actual_active_bounds_are_present_and_input_price_zero_stays_zero():
    body = request()
    body["constraints"] = {"min_price_krw": 0, "max_price_krw": 0}
    body["include_explanations"] = True
    result = recommend_content(ContentRecommendationRequest.model_validate(body))
    assert {row.product_id for row in result.items} == {1, 3}
    for item in result.items:
        evidence = item.explanation.filter_evidence
        assert [row.kind for row in evidence] == ["availability_filter", "price_filter"]
        assert evidence[1].actual_value == evidence[1].minimum == evidence[1].maximum == 0
        assert evidence[1].label == "입력 가격 조건 충족" and evidence[1].unit == "KRW"


@pytest.mark.parametrize("endpoint", ["context", "feedback"])
def test_each_winning_reference_carries_its_own_actual_comparison_and_profile_ties_win(endpoint):
    body = {
        "catalog": [
            dict(
                product_id=pid,
                sku_group=str(pid),
                available=True,
                taste_tags=[tag],
                abv_percent=abv,
            )
            for pid, tag, abv in ((1, "단", 0), (2, "드라이", 10), (3, "드라이", 10), (4, "단", 0))
        ],
        "include_explanations": True,
    }
    body["reference_product_ids" if endpoint == "context" else "feedback"] = (
        [2, 1] if endpoint == "context" else {"positive_product_ids": [2, 1]}
    )
    with TestClient(app) as client:
        result = client.post("/v1/recommendations/" + endpoint, json=body).json()
        assert [row["product_id"] for row in result["items"]] == [3, 4]
        assert [row["explanation"]["comparison"]["product_id"] for row in result["items"]] == [2, 1]
        if endpoint == "feedback":
            body["profile"] = {"taste_tags": ["드라이"], "preferred_abv_percent": 10}
            result = client.post("/v1/recommendations/feedback", json=body).json()
            item = next(row for row in result["items"] if row["product_id"] == 3)
            assert item["explanation"]["comparison"] == {"kind": "profile"}


def test_top_contribution_selection_is_explicitly_partial_without_changing_original_parts():
    tags = ["tag" + str(i) for i in range(20)]
    body = {
        "catalog": [
            dict(
                product_id=pid,
                sku_group=str(pid),
                available=True,
                category="맥주",
                taste_tags=tags,
                aroma_tags=tags,
                abv_percent=abv,
                volume_ml=vol,
            )
            for pid, abv, vol in ((1, 0, 330), (2, 10, 750))
        ],
        "profile": {
            "categories": ["맥주"],
            "taste_tags": tags,
            "aroma_tags": tags,
            "preferred_abv_percent": 0,
            "preferred_volume_ml": 330,
        },
    }
    original = recommend_content(ContentRecommendationRequest.model_validate(body))
    result = recommend_content(
        ContentRecommendationRequest.model_validate(body | {"include_explanations": True})
    )
    item = result.items[0]
    assert item.contributions == original.items[0].contributions and len(item.contributions) == 43
    assert item.explanation.total_positive_contributions == 43
    assert item.explanation.score_evidence_truncated and len(item.explanation.score_evidence) == 3
    top = sorted(item.contributions, key=lambda p: (-p.contribution, p.component, p.feature))[:3]
    assert [row.contribution for row in item.explanation.score_evidence] == [
        p.contribution for p in top
    ]


def test_maximum_atoms_and_reference_id_remain_bounded_without_truncating_values():
    category = "\0" * 64
    tags = ["\0" * 38 + str(i).zfill(2) for i in range(20)]
    products = [
        ContentProduct(
            product_id=pid,
            sku_group=str(pid),
            available=True,
            category=category,
            taste_tags=tags,
            aroma_tags=tags,
            abv_percent=abv,
            volume_ml=volume,
            price_krw=2_147_483_647,
        )
        for pid, abv, volume in ((2_147_483_647, 0, 1), (2, 0, 1), (3, 100, 1_000_000))
    ]
    model = FittedContentModel.fit(products)
    constraints = Constraints(
        categories=[category],
        min_price_krw=0,
        max_price_krw=2_147_483_647,
        min_abv_percent=0,
        max_abv_percent=100,
    )
    result = model.similar(products[0], products, constraints, include_explanations=True)
    for item in result.items:
        assert len(item.explanation.model_dump_json().encode("utf-8")) <= 4096
        assert item.explanation.comparison.product_id == 2_147_483_647


def test_false_evidence_is_rejected_instead_of_rendering_unsupported_facts():
    body = request()
    valid = ContentRecommendationRequest.model_validate(body)
    result = recommend_content(valid)
    result.items[0].contributions[0].feature = "taste:invented"
    with pytest.raises(ValueError, match="evidence_conflicts"):
        annotate_explanations(result, valid.catalog, valid.profile, valid.constraints)


def test_explanation_openapi_is_discriminated_and_empty_opt_in_keeps_startup_light():
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()["components"]["schemas"]
        explained = schema["ItemExplanation"]["properties"]
        assert explained["score_evidence"]["items"]["discriminator"]["propertyName"] == "kind"
        assert explained["comparison"]["discriminator"]["propertyName"] == "kind"
    code = (
        "import sys;from fastapi.testclient import TestClient;"
        "from pubburi_recommendation.main import app;c=TestClient(app);"
        "assert c.get('/health').status_code==200;assert c.get('/openapi.json').status_code==200;"
        "assert c.post('/v1/recommendations/content',json={'catalog':[],"
        "'include_explanations':True}).status_code==200;"
        "assert 'numpy' not in sys.modules and 'sklearn' not in sys.modules"
    )
    run = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stderr
