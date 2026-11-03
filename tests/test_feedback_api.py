"""Authored R05 facts/constraints, not customer observations or preference-quality labels."""

import asyncio
import copy
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from pubburi_recommendation.content_api import ContentRecommendationRequest, recommend_content
from pubburi_recommendation.content_model import FittedContentModel
from pubburi_recommendation.feedback_api import FeedbackRecommendationRequest, recommend_feedback
from pubburi_recommendation.main import app
from pubburi_recommendation.request_limits import CatalogRequestLimit

PATH = "/v1/recommendations/feedback"


def request():
    rows = (
        (1, "dry-anchor", "dry", 0, True),
        (2, "dry-anchor", "dry", 0, True),
        (3, "sweet-anchor", "sweet", 10, True),
        (4, "sweet-anchor", "sweet", 10, True),
        (5, "dry-candidate", "dry", 0, True),
        (6, "sweet-candidate", "sweet", 10, True),
        (7, "negative", "dry", 0, False),
        (8, "negative", "dry", 0, True),
        (9, "profile-candidate", "fruity", 0, True),
        (10, "unknown-price", "dry", 0, True),
        (11, "excluded", "dry", 0, True),
        (12, "off-positive", "sweet", 10, False),
        (13, "off-positive", "sweet", 10, True),
    )
    return {
        "catalog": [
            dict(
                product_id=pid,
                sku_group=group,
                taste_tags=["authored " + taste],
                abv_percent=abv,
                price_krw=None if pid == 10 else 1000,
                available=available,
            )
            for pid, group, taste, abv, available in rows
        ],
        "profile": {"taste_tags": ["authored fruity"]},
        "feedback": {"positive_product_ids": [3, 1, 12, 99], "not_interested_product_ids": [7]},
        "constraints": {
            "max_price_krw": 1500,
            "max_abv_percent": 15,
            "exclude_product_ids": [11],
        },
        "limit": 10,
    }


def execute(value):
    return recommend_feedback(FeedbackRecommendationRequest.model_validate(value))


def test_feedback_changes_ranking_with_one_fit_and_exact_original_winning_evidence(monkeypatch):
    body = request()
    before = copy.deepcopy(body)
    fit = FittedContentModel.fit
    calls = []

    def counted(products):
        calls.append(products)
        return fit(products)

    monkeypatch.setattr(FittedContentModel, "fit", counted)
    result = execute(body)
    # Fixed declared facts establish eligibility/winners; no production helper creates labels.
    assert [item.product_id for item in result.items] == [5, 6, 9]
    assert [(m.source, m.positive_product_id) for m in result.matches] == [
        ("positive_feedback", 1),
        ("positive_feedback", 3),
        ("profile", None),
    ]
    assert len(calls) == 1 and body == before
    assert result.eligible_count == 3
    assert result.excluded_not_interested_count == 2
    assert result.excluded_positive_group_count == 6
    assert result.evaluated_positive_count == result.informative_positive_count == 2
    assert result.ranking_mode == "positive_feedback" and result.fallback_reason is None
    assert [r.state for r in result.positive_references] == [
        "available",
        "available",
        "unavailable",
        "missing",
    ]
    assert result.not_interested_references[0].state == "unavailable"
    assert all(r.supported_profile_tokens is None for r in result.positive_references[2:])
    valid = FeedbackRecommendationRequest.model_validate(body)
    model = fit(valid.catalog)
    candidates = [p for p in valid.catalog if p.product_id in (5, 6, 9, 10, 11)]
    for item, match in zip(result.items, result.matches, strict=True):
        ranked = (
            model.rank(candidates, valid.profile, valid.constraints)
            if match.source == "profile"
            else model.similar(
                next(p for p in valid.catalog if p.product_id == match.positive_product_id),
                candidates,
                valid.constraints,
            )
        )
        assert item == next(row for row in ranked.items if row.product_id == item.product_id)
        assert item.score == pytest.approx(sum(c.contribution for c in item.contributions))
        assert item.score > 0 and "content_similarity" in item.reasons
    assert result.model_fingerprint == model.fingerprint


def test_order_ties_repeated_variant_and_global_limit_do_not_weight_feedback():
    body = request()
    expected = execute(body)
    body["catalog"].reverse()
    body["feedback"]["positive_product_ids"].reverse()
    assert execute(body) == expected
    body["feedback"]["positive_product_ids"].append(2)
    repeated = execute(body)
    assert repeated.items == expected.items and repeated.matches == expected.matches
    body["limit"] = 1
    assert execute(body).items == expected.items[:1]
    body["profile"] = {"taste_tags": ["authored dry"], "preferred_abv_percent": 0}
    assert execute(body).matches[0].source == "profile"


@pytest.mark.parametrize("negative", [[1], [2], [7, 1]])
def test_negative_wins_same_id_and_group_conflicts_without_spending_hard_exclusion_budget(negative):
    body = request()
    body["feedback"]["not_interested_product_ids"] = negative
    body["constraints"]["exclude_product_ids"] = list(range(1000, 2000))
    result = execute(body)
    blocked = next(r for r in result.positive_references if r.product_id == 1)
    assert blocked.state == "blocked" and blocked.active_numeric_preferences is None
    assert result.evaluated_positive_count == 1
    assert all(m.positive_product_id != 1 for m in result.matches)
    assert all(item.product_id not in (1, 2) for item in result.items)
    # Negative group gets counted first; overlap is never counted again as positive exclusion.
    assert result.excluded_positive_group_count == 4


def test_missing_negative_has_no_inferred_group_and_omitted_feedback_is_original_content():
    body = request()
    del body["feedback"]
    original = recommend_content(ContentRecommendationRequest.model_validate(body))
    result = execute(body)
    assert all(result.model_dump()[key] == value for key, value in original.model_dump().items())
    body["feedback"] = {"not_interested_product_ids": [999]}
    unknown = execute(body)
    assert unknown.items == original.items and unknown.excluded_not_interested_count == 0
    assert unknown.not_interested_references[0].state == "missing"
    assert unknown.not_interested_references[0].sku_group is None


@pytest.mark.parametrize("positive", [[], [999], [12], [1]])
def test_no_usable_positive_retains_labeled_profile_or_baseline_fallback(positive):
    body = request()
    body["feedback"] = {"positive_product_ids": positive, "not_interested_product_ids": [1]}
    body["profile"] = {}
    result = execute(body)
    assert result.ranking_mode == "profile_fallback"
    assert result.informative_positive_count == 0
    assert result.fallback_reason == "no_supported_preferences"
    assert result.items and all(item.score == 0 for item in result.items)
    assert all(m.source == "baseline" and m.positive_product_id is None for m in result.matches)
    assert all(item.product_id not in (1, 2) for item in result.items)


def test_available_uninformative_positive_and_null_empty_tags_are_not_positive_evidence():
    body = {
        "catalog": [
            {"product_id": 1, "sku_group": "a", "available": True, "taste_tags": None},
            {"product_id": 2, "sku_group": "b", "available": True, "taste_tags": []},
        ],
        "feedback": {"positive_product_ids": [1]},
    }
    result = execute(body)
    reference = result.positive_references[0]
    assert reference.state == "available" and result.evaluated_positive_count == 1
    assert reference.supported_profile_tokens == 0 and reference.active_numeric_preferences == []
    assert reference.fallback_reason == "no_supported_preferences"
    assert result.ranking_mode == "profile_fallback" and result.informative_positive_count == 0
    assert not result.representation_fitted and result.model_fingerprint is None
    assert [item.product_id for item in result.items] == [2]
    assert result.matches[0].source == "baseline"
    validated = FeedbackRecommendationRequest.model_validate(body)
    assert validated.catalog[0].taste_tags is None and validated.catalog[1].taste_tags == []


def test_actual_zero_numeric_feedback_is_distinct_from_unknown_without_zero_padding():
    body = {
        "catalog": [
            dict(product_id=pid, sku_group=str(pid), available=True, abv_percent=abv)
            for pid, abv in ((1, 0), (2, 0), (3, None), (4, 10))
        ],
        "feedback": {"positive_product_ids": [1]},
    }
    result = execute(body)
    assert [item.product_id for item in result.items] == [2]
    assert result.eligible_count == 3 and result.items[0].score == 1
    assert result.positive_references[0].active_numeric_preferences == ["abv_percent"]
    body["catalog"][1]["abv_percent"] = 10
    result = execute(body)
    assert result.items == result.matches == []
    assert result.fallback_reason == "no_matching_features"
    assert result.ranking_mode == "positive_feedback"


@pytest.mark.parametrize("mode", ["negative", "hard", "unavailable"])
def test_zero_candidates_never_relax_exclusions_or_hard_constraints(mode):
    body = request()
    if mode == "negative":
        body["feedback"]["not_interested_product_ids"] = [
            row["product_id"] for row in body["catalog"]
        ]
    elif mode == "hard":
        body["constraints"]["categories"] = ["no authored category"]
    else:
        for row in body["catalog"]:
            row["available"] = False
    result = execute(body)
    assert result.items == result.matches == []
    assert result.eligible_count == 0 and result.fallback_reason == "no_eligible_products"


def test_concurrent_requests_and_input_objects_are_isolated():
    body = request()
    expected = execute(body)
    other = copy.deepcopy(body)
    other["feedback"] = {"not_interested_product_ids": [5, 6, 9]}
    with ThreadPoolExecutor(max_workers=2) as pool:
        actual, different = list(pool.map(execute, (body, other)))
    assert actual == expected and different != expected
    assert execute(body) == expected


@pytest.mark.parametrize("field", ["positive_product_ids", "not_interested_product_ids"])
@pytest.mark.parametrize(
    "value", [[1, 1], list(range(1, 22)), [True], ["1"], [0], [2_147_483_648], None]
)
def test_strict_unique_bounded_feedback_ids(field, value):
    body = request()
    body["feedback"][field] = value
    with pytest.raises(ValidationError):
        FeedbackRecommendationRequest.model_validate(body)


def test_duplicate_catalog_validation_precedes_feedback_removal():
    body = request()
    body["catalog"].append(copy.deepcopy(body["catalog"][0]))
    with pytest.raises(ValidationError):
        FeedbackRecommendationRequest.model_validate(body)


def test_http_openapi_and_fixed_diagnostics():
    with TestClient(app) as client:
        response = client.post(PATH, json=request())
        assert response.status_code == 200 and response.json() == execute(request()).model_dump()
        bad = client.post(
            PATH, json={"catalog": [], "feedback": {"positive_product_ids": ["PRIVATE"]}}
        )
        assert bad.status_code == 422 and "PRIVATE" not in bad.text
        assert all(set(row) == {"type", "loc", "msg"} for row in bad.json()["detail"])
        schema = client.get("/openapi.json").json()
        assert set(schema["paths"][PATH]["post"]["responses"]) >= {"200", "408", "413", "422"}


@pytest.mark.parametrize("media", ["application/json", "application/vnd.pubburi+json", None])
def test_body_cap_duplicate_json_and_original_syntax_error_priority(media):
    headers = {} if media is None else {"Content-Type": media}
    with TestClient(app) as client:
        duplicate = (
            '{"catalog":[],"feedback":{"positive_product_ids":[1],'
            '"positive_product_\\u0069ds":[1]}}'
        )
        response = client.post(PATH, content=duplicate, headers=headers)
        assert response.status_code == 422
        assert response.json()["detail"][0]["type"] == "duplicate_json_key"
        invalid = '{"catalog":[],"catalog":[]} trailing'
        actual = client.post(PATH, content=invalid, headers=headers)
        original = client.post("/v1/recommendations/content", content=invalid, headers=headers)
        assert (
            actual.status_code == original.status_code == 422 and actual.json() == original.json()
        )
        assert client.post(PATH, content=b" " * 524289, headers=headers).status_code == 413


def test_receive_deadline_and_disconnect_precede_feedback_fit():
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


def test_startup_and_empty_feedback_keep_numeric_runtime_unloaded():
    code = (
        "from fastapi.testclient import TestClient;"
        "from pubburi_recommendation.main import app;import sys;c=TestClient(app);"
        "assert c.get('/openapi.json').status_code==200;"
        "assert c.get('/health').status_code==200;"
        "assert c.post('/v1/recommendations/feedback',json={'catalog':[],"
        "'profile':{'taste_tags':['unknown']},'feedback':{'positive_product_ids':[1],"
        "'not_interested_product_ids':[2]}}).status_code==200;"
        "assert 'numpy' not in sys.modules and 'sklearn' not in sys.modules"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, result.stderr
