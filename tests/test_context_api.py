"""Authored context facts and max-reference contracts, not co-purchase or user labels."""

import asyncio
import copy
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from pubburi_recommendation.content_model import FittedContentModel
from pubburi_recommendation.context_api import (
    ContextRecommendationRequest,
    recommend_context,
)
from pubburi_recommendation.main import app
from pubburi_recommendation.request_limits import CatalogRequestLimit

PATH = "/v1/recommendations/context"


def request():
    rows = (
        (10, "a", "authored beer", ["authored dry"], 1000, 5, 330, True),
        (11, "a", "authored beer", ["authored dry"], 1000, 5, 330, True),
        (30, "b", "authored wine", ["authored sweet"], 1000, 12, 750, True),
        (31, "b", "authored wine", ["authored sweet"], 1000, 12, 750, True),
        (20, "c", "authored beer", ["authored dry"], 1000, 5, 330, True),
        (40, "d", "authored wine", ["authored sweet"], 1000, 12, 750, True),
        (60, "off", "authored beer", ["authored dry"], 1000, 5, 330, False),
        (61, "off", "authored beer", ["authored dry"], 1000, 5, 330, True),
        (70, "price", "authored beer", ["authored dry"], 3000, 5, 330, True),
        (71, "abv", "authored wine", ["authored sweet"], 1000, 30, 750, True),
        (72, "unknown-price", "authored beer", ["authored dry"], None, 5, 330, True),
        (80, "unknown-abv", "authored beer", ["authored dry"], 1000, None, 330, True),
        (90, "excluded", "authored beer", ["authored dry"], 1000, 5, 330, True),
    )
    return {
        "catalog": [
            dict(
                product_id=pid,
                sku_group=group,
                category=category,
                taste_tags=taste,
                price_krw=price,
                abv_percent=abv,
                volume_ml=volume,
                available=available,
            )
            for pid, group, category, taste, price, abv, volume, available in rows
        ],
        "reference_product_ids": [30, 10, 60, 999],
        "constraints": {
            "max_price_krw": 1500,
            "max_abv_percent": 15,
            "exclude_product_ids": [90],
        },
        "limit": 3,
    }


def execute(value):
    return recommend_context(ContextRecommendationRequest.model_validate(value))


def test_multiple_context_facts_preserve_hard_bounds_and_original_winning_b1_evidence(
    monkeypatch,
):
    value = request()
    original = copy.deepcopy(value)
    fit = FittedContentModel.fit
    fits = []

    def counted(products):
        fits.append(products)
        return fit(products)

    monkeypatch.setattr(FittedContentModel, "fit", counted)
    result = execute(value)
    # These candidates/counts follow the declared facts, independent of production helpers.
    assert {item.product_id for item in result.items} == {20, 40}
    assert {row.product_id: row.reference_product_id for row in result.matches} == {20: 10, 40: 30}
    assert result.items == sorted(result.items, key=lambda item: (-item.score, item.product_id))
    assert result.eligible_count == 2 and result.excluded_reference_group_count == 6
    assert result.evaluated_reference_count == 2 and len(fits) == 1
    assert [row.state for row in result.references] == [
        "available",
        "available",
        "unavailable",
        "missing",
    ]
    assert all(row.supported_profile_tokens is None for row in result.references[2:])
    assert result.fallback_reason is None and result.representation_fitted
    assert value == original
    validated = ContextRecommendationRequest.model_validate(value)
    model = fit(validated.catalog)
    candidates = [p for p in validated.catalog if p.product_id in (20, 40, 70, 71, 72, 80, 90)]
    for item, match in zip(result.items, result.matches, strict=True):
        reference = next(p for p in validated.catalog if p.product_id == match.reference_product_id)
        previous = model.similar(reference, candidates, validated.constraints)
        assert item == next(row for row in previous.items if row.product_id == item.product_id)
        assert item.score == pytest.approx(sum(part.contribution for part in item.contributions))
        assert "content_similarity" in item.reasons and item.score > 0
    assert result.model_fingerprint == model.fingerprint


def test_reference_order_and_same_group_repetition_never_weight_or_amplify_scores():
    value = request()
    expected = execute(value)
    value["catalog"].reverse()
    value["reference_product_ids"].reverse()
    assert execute(value) == expected
    value["reference_product_ids"].append(11)
    repeated = execute(value)
    assert repeated.items == expected.items and repeated.matches == expected.matches
    assert repeated.excluded_reference_group_count == expected.excluded_reference_group_count
    # Same-score references keep the smallest reference ID, independent of caller order.
    assert next(row for row in repeated.matches if row.product_id == 20).reference_product_id == 10


def test_global_max_merge_and_limit_are_applied_after_reference_scoring():
    value = {
        "catalog": [
            {"product_id": pid, "sku_group": str(pid), "available": True, "category": category}
            for pid, category in ((1, "one"), (2, "one"), (3, "two"), (4, "two"))
        ],
        "reference_product_ids": [3, 1],
        "limit": 1,
    }
    result = execute(value)
    assert [item.product_id for item in result.items] == [2]
    assert result.matches[0].reference_product_id == 1
    value["catalog"] = [row for row in value["catalog"] if row["product_id"] != 2]
    result = execute(value)
    assert [item.product_id for item in result.items] == [4]
    assert result.matches[0].reference_product_id == 3


def test_soft_context_category_never_overrides_hard_category_or_exclusion_budget():
    value = request()
    value["constraints"] = {
        "categories": ["authored wine"],
        "max_abv_percent": 15,
        "exclude_product_ids": list(range(1000, 2000)),
    }
    result = execute(value)
    assert [item.product_id for item in result.items] == [40]
    assert result.eligible_count == 1
    value["reference_product_ids"] = [10]
    result = execute(value)
    assert result.items and all("category_match" in item.reasons for item in result.items)
    assert all(item.product_id in (30, 31, 40) for item in result.items)


@pytest.mark.parametrize("mode", ["empty", "missing", "unavailable"])
def test_no_usable_references_never_fit_or_invent_evaluated_counts(mode, monkeypatch):
    value = request()
    if mode == "empty":
        value["catalog"] = []
    elif mode == "missing":
        value["reference_product_ids"] = [998, 999]
    else:
        value["reference_product_ids"] = [60, 999]

    def forbidden(_):
        raise AssertionError("No model fit without a usable reference")

    monkeypatch.setattr(FittedContentModel, "fit", forbidden)
    result = execute(value)
    assert result.items == result.matches == []
    assert result.fallback_reason == "no_usable_references"
    assert result.evaluated_reference_count == 0
    assert result.eligible_count is result.excluded_reference_group_count is None
    assert result.model_fingerprint is None and not result.representation_fitted
    assert all(row.active_numeric_preferences is None for row in result.references)


@pytest.mark.parametrize(
    "mode,reason",
    [
        ("same-group", "no_eligible_products"),
        ("hard-empty", "no_eligible_products"),
        ("unknown", "no_supported_preferences"),
        ("no-overlap", "no_matching_features"),
        ("constant", "no_supported_preferences"),
    ],
)
def test_empty_or_unsupported_context_never_fills_zero_score_items(mode, reason):
    value = {
        "catalog": [
            {"product_id": 1, "sku_group": "a", "available": True, "category": "one"},
            {"product_id": 2, "sku_group": "b", "available": True, "category": "two"},
        ],
        "reference_product_ids": [1],
    }
    if mode == "same-group":
        value["catalog"][1]["sku_group"] = "a"
    elif mode == "hard-empty":
        value["constraints"] = {"max_price_krw": 1000}
    elif mode == "unknown":
        value["catalog"][0]["category"] = None
    elif mode == "constant":
        for row in value["catalog"]:
            row["category"] = None
            row["abv_percent"] = 0
    result = execute(value)
    assert result.items == result.matches == [] and result.fallback_reason == reason
    assert result.eligible_count == (0 if mode in ("same-group", "hard-empty") else 1)
    assert result.evaluated_reference_count == 1
    if mode == "constant":
        assert not result.representation_fitted and result.model_fingerprint is None


def test_floor_is_inclusive_and_does_not_relax_or_fill_shortages():
    value = request()
    result = execute(value)
    value["min_relevance_score"] = min(item.score for item in result.items)
    assert execute(value).items == result.items
    value["catalog"] = [row for row in value["catalog"] if row["product_id"] != 40]
    value["catalog"][4]["taste_tags"] = None  # ID20 loses one explicit matching fact.
    result = execute(value)
    assert result.items == [] and result.fallback_reason == "below_relevance_floor"
    assert result.eligible_count == 1


def test_actual_zero_matches_while_unknown_has_no_numeric_evidence():
    value = {
        "catalog": [
            {"product_id": pid, "sku_group": str(pid), "available": True, "abv_percent": abv}
            for pid, abv in ((1, 0), (2, 0), (3, None), (4, 10))
        ],
        "reference_product_ids": [1],
    }
    result = execute(value)
    assert [item.product_id for item in result.items] == [2]
    assert result.items[0].score == 1
    assert result.items[0].contributions[0].component == "abv_percent"
    assert result.eligible_count == 3
    value["constraints"] = {"max_abv_percent": 0}
    result = execute(value)
    assert result.eligible_count == 1 and [item.product_id for item in result.items] == [2]


def test_different_context_requests_do_not_share_model_or_reference_state():
    value = request()
    expected = execute(value)
    other = copy.deepcopy(value)
    other["reference_product_ids"] = [40]
    other["constraints"] = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        actual, different = list(pool.map(execute, [value, other]))
    assert actual == expected and different.references[0].product_id == 40
    assert 40 not in [item.product_id for item in different.items]
    assert execute(value) == expected


@pytest.mark.parametrize(
    "field,value",
    [
        ("reference_product_ids", []),
        ("reference_product_ids", list(range(1, 22))),
        ("reference_product_ids", [1, 1]),
        ("reference_product_ids", [True]),
        ("reference_product_ids", ["1"]),
        ("reference_product_ids", [0]),
        ("reference_product_ids", [2_147_483_648]),
        ("limit", True),
        ("min_relevance_score", -0.1),
        ("min_relevance_score", 1.1),
        ("min_relevance_score", float("nan")),
        ("min_relevance_score", "0.5"),
        ("profile", {}),
    ],
)
def test_strict_bounded_unique_context_contract(field, value):
    body = request()
    body[field] = value
    with pytest.raises(ValidationError):
        ContextRecommendationRequest.model_validate(body)


def test_duplicate_catalog_ids_are_rejected_before_reference_group_removal():
    body = request()
    body["catalog"].append(copy.deepcopy(body["catalog"][0]))
    with pytest.raises(ValidationError):
        ContextRecommendationRequest.model_validate(body)


def test_http_openapi_and_fixed_validation_diagnostics():
    with TestClient(app) as client:
        response = client.post(PATH, json=request())
        assert response.status_code == 200 and response.json() == execute(request()).model_dump()
        invalid = client.post(PATH, json={"catalog": [], "reference_product_ids": ["PRIVATE"]})
        assert invalid.status_code == 422 and "PRIVATE" not in invalid.text
        assert all(set(row) == {"type", "loc", "msg"} for row in invalid.json()["detail"])
        schema = client.get("/openapi.json").json()
        assert set(schema["paths"][PATH]["post"]["responses"]) >= {"200", "408", "413", "422"}


@pytest.mark.parametrize("media", ["application/json", "application/vnd.pubburi+json", None])
def test_duplicate_json_and_original_error_priority_and_body_cap(media):
    headers = {} if media is None else {"Content-Type": media}
    with TestClient(app) as client:
        response = client.post(
            PATH,
            content='{"catalog":[],"reference_product_ids":[1],"reference_product_\\u0069ds":[1]}',
            headers=headers,
        )
        assert response.status_code == 422
        assert response.json()["detail"][0]["type"] == "duplicate_json_key"
        invalid = '{"catalog":[],"catalog":[]} trailing'
        response = client.post(PATH, content=invalid, headers=headers)
        existing = client.post("/v1/recommendations/content", content=invalid, headers=headers)
        assert response.status_code == existing.status_code == 422
        assert response.json() == existing.json()
        assert client.post(PATH, content=b" " * 524289, headers=headers).status_code == 413


def test_receive_deadline_and_disconnect_precede_context_fit():
    called = False

    async def inner(scope, receive, send):
        nonlocal called
        called = True

    async def run(disconnect):
        messages = []

        async def receive():
            if disconnect:
                return {"type": "http.disconnect"}
            await asyncio.sleep(0.1)
            return {"type": "http.request", "body": b"{", "more_body": True}

        async def send(message):
            messages.append(message)

        await CatalogRequestLimit(inner, body_timeout_seconds=0.01)(
            {"type": "http", "method": "POST", "path": PATH}, receive, send
        )
        return messages

    assert asyncio.run(run(False))[0]["status"] == 408
    assert asyncio.run(run(True)) == [] and not called


def test_startup_and_no_usable_context_keep_numeric_runtime_unloaded():
    code = (
        "from fastapi.testclient import TestClient;"
        "from pubburi_recommendation.main import app;import sys;c=TestClient(app);"
        "assert c.get('/openapi.json').status_code==200;"
        "assert c.get('/health').status_code==200;"
        "assert c.post('/v1/recommendations/baseline',json={'catalog':[]}).status_code==200;"
        "assert c.post('/v1/recommendations/context',json={'catalog':[],"
        "'reference_product_ids':[1]}).status_code==200;"
        "assert c.post('/v1/recommendations/context',json={'catalog':[{'product_id':1,"
        "'sku_group':'a','available':False}],'reference_product_ids':[1,2]}).status_code==200;"
        "assert 'numpy' not in sys.modules and 'sklearn' not in sys.modules"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, result.stderr
