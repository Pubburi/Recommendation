"""Authored R08 policy contracts; no real product/preferences or human-quality labels."""

import asyncio
import copy
import math
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from pubburi_recommendation.content_api import ContentRecommendationRequest, recommend_content
from pubburi_recommendation.exploration import ExplorationRequest, recommend_exploration
from pubburi_recommendation.main import app
from pubburi_recommendation.request_limits import CatalogRequestLimit

PATH = "/v1/recommendations/exploration"


def request():
    products = []
    for product_id, group, category, tags in (
        (1, "family-a", "authored beer", ["authored shared"]),
        (2, "family-a", "authored beer", ["authored shared"]),
        (3, "family-b", "authored beer", ["authored shared"]),
        (4, "family-c", "authored wine", ["authored shared"]),
        (5, "family-d", None, None),
        (6, "family-e", "authored spirit", ["authored other"]),
        (7, "family-f", "authored beer", ["authored shared"]),
        (8, "family-g", "authored wine", ["authored shared"]),
    ):
        products.append(
            {
                "product_id": product_id,
                "sku_group": group,
                "available": product_id != 8,
                "category": category,
                "taste_tags": tags,
                "price_krw": 1000,
                "abv_percent": 5,
            }
        )
    return {
        "catalog": products,
        "profile": {"categories": ["authored beer"], "taste_tags": ["authored shared"]},
        "constraints": {"exclude_product_ids": [7], "max_price_krw": 1500, "max_abv_percent": 5},
        "limit": 3,
        "policy": {"relevance_weight": 0.5, "min_relevance_score": 0.05},
    }


def base_request(value, limit=100):
    return ContentRecommendationRequest.model_validate(
        {**{k: v for k, v in value.items() if k != "policy"}, "limit": limit}
    )


def test_opt_in_groups_and_hard_constraints_preserve_original_b1_scores_contributions():
    value = request()
    before = recommend_content(base_request(value))
    result = recommend_exploration(ExplorationRequest.model_validate(value))
    assert [item.product_id for item in before.items][:3] == [1, 2, 3]
    assert [item.product_id for item in result.items] == [1, 3, 4]
    assert result.selected_count == result.selected_group_count == 3
    assert result.candidate_pool_size == result.eligible_count == 6
    assert result.relevance_pool_size == 4 and not result.pool_truncated
    assert result.exploration_reason == "selected" and result.fallback_reason is None
    before_by_id = {item.product_id: item for item in before.items}
    for item in result.items:
        assert item == before_by_id[item.product_id]
        assert item.score == pytest.approx(sum(part.contribution for part in item.contributions))
        assert item.product_id not in {5, 6, 7, 8}
    assert len({item.sku_group for item in result.selections}) == 3
    assert result.selections[0].basis == "highest_relevance_anchor"
    assert result.selections[0].max_observed_text_similarity is None
    assert result.selections[1].max_observed_text_similarity == pytest.approx(1)
    assert 0 < result.selections[2].max_observed_text_similarity < 1


def test_mmr_can_choose_known_distinct_text_with_numeric_relevance_without_changing_base_score():
    value = request()
    # Separate authored case activates the observed numeric scale; not tuning the frozen case.
    value["catalog"][5]["abv_percent"] = 10
    value["profile"]["preferred_abv_percent"] = 5
    result = recommend_exploration(ExplorationRequest.model_validate(value))
    assert [item.product_id for item in result.items] == [1, 4, 3]
    base = {item.product_id: item for item in recommend_content(base_request(value)).items}
    assert base[3].score > base[4].score
    assert result.items[1] == base[4]
    selection = result.selections[1]
    assert selection.selection_score == pytest.approx(
        0.5 * base[4].score - 0.5 * selection.redundancy_penalty_input
    )
    assert selection.basis == "observed_text"
    assert selection.selection_score > 0
    value["policy"]["relevance_weight"] = 1
    assert [
        item.product_id
        for item in recommend_exploration(ExplorationRequest.model_validate(value)).items
    ] == [1, 3, 4]


def test_unknown_text_is_not_rewarded_as_novel_when_numeric_preference_supplies_relevance():
    value = request()
    value["catalog"][5]["abv_percent"] = 10
    value["profile"]["preferred_abv_percent"] = 5
    value["limit"] = 10
    result = recommend_exploration(ExplorationRequest.model_validate(value))
    selection = next(item for item in result.selections if item.product_id == 5)
    assert selection.basis == "unknown_conservative"
    assert selection.max_observed_text_similarity is None
    assert selection.redundancy_penalty_input == 1
    assert [item.product_id for item in result.items].index(5) > [
        item.product_id for item in result.items
    ].index(4)
    assert (
        result.selected_count == 4
    )  # No irrelevant, unavailable, excluded or group duplicate fill.


def test_unknown_anchor_conservatively_penalizes_all_unverifiable_pairs():
    value = request()
    value["profile"] = {"preferred_abv_percent": 5}
    value["catalog"][0].update(category=None, taste_tags=None)
    value["catalog"][5]["abv_percent"] = 10
    value["limit"] = 3
    result = recommend_exploration(ExplorationRequest.model_validate(value))
    assert result.items[0].product_id == 1
    assert all(
        row.basis == "unknown_conservative"
        and row.redundancy_penalty_input == 1
        and row.max_observed_text_similarity is None
        for row in result.selections[1:]
    )


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("empty", "no_eligible_products"),
        ("empty-profile", "no_supported_preferences"),
        ("oov", "no_supported_preferences"),
        ("no-match", "no_matching_features"),
        ("hard-excluded", "no_eligible_products"),
    ],
)
def test_missing_supported_preference_or_eligible_candidates_returns_no_fake_exploration(
    mutation, reason
):
    value = request()
    if mutation == "empty":
        value["catalog"] = []
    elif mutation == "empty-profile":
        value["profile"] = {}
    elif mutation == "oov":
        value["profile"] = {"taste_tags": ["unknown authored"]}
    elif mutation == "no-match":
        value["profile"] = {"taste_tags": ["authored other"]}
        value["constraints"]["exclude_product_ids"] = [6, 7]
    else:
        value["constraints"]["exclude_product_ids"] = list(range(1, 9))
    result = recommend_exploration(ExplorationRequest.model_validate(value))
    assert result.items == result.selections == []
    assert result.exploration_reason == "baseline_fallback" and result.fallback_reason == reason
    assert result.selected_count == result.selected_group_count == result.relevance_pool_size == 0


def test_floor_and_group_shortage_do_not_relax_or_fill_from_lower_relevance():
    value = request()
    value["policy"]["min_relevance_score"] = 0.99
    value["limit"] = 100
    result = recommend_exploration(ExplorationRequest.model_validate(value))
    assert [item.product_id for item in result.items] == [1, 3]
    value["catalog"][0]["taste_tags"].append("authored extra")
    value["catalog"][1]["taste_tags"].append("authored extra")
    value["catalog"][2]["taste_tags"].append("authored extra")
    result = recommend_exploration(ExplorationRequest.model_validate(value))
    assert result.items == [] and result.exploration_reason == "below_relevance_floor"
    assert result.eligible_count == 6 and result.fallback_reason is None


def test_pool_is_explicitly_bounded_and_never_searches_beyond_top100_to_fill_groups():
    value = request()
    value["catalog"] = [
        {
            "product_id": i,
            "available": True,
            "sku_group": "same" if i <= 100 else "beyond",
            "taste_tags": ["wanted"],
        }
        for i in range(1, 102)
    ]
    value["profile"] = {"taste_tags": ["wanted"]}
    value["constraints"] = {}
    value["limit"] = 100
    result = recommend_exploration(ExplorationRequest.model_validate(value))
    assert result.eligible_count == 101 and result.candidate_pool_size == 100
    assert result.pool_truncated and result.relevance_pool_size == 100
    assert [item.product_id for item in result.items] == [1]


def test_input_permutation_and_concurrent_requests_do_not_change_results_or_leak_profiles():
    value = request()
    expected = recommend_exploration(ExplorationRequest.model_validate(value))
    value["catalog"].reverse()
    assert recommend_exploration(ExplorationRequest.model_validate(value)) == expected
    second = copy.deepcopy(value)
    second["constraints"]["exclude_product_ids"] = [1, 2, 3, 4, 7]

    def execute(payload):
        return recommend_exploration(ExplorationRequest.model_validate(payload))

    with ThreadPoolExecutor(max_workers=2) as pool:
        first_result, second_result = list(pool.map(execute, [value, second]))
    assert first_result == expected
    assert second_result.items == []


@pytest.mark.parametrize(
    "change",
    [
        "weight-low",
        "weight-high",
        "weight-bool",
        "weight-string",
        "floor-low",
        "floor-high",
        "nan",
        "extra",
        "duplicate-id",
        "limit-bool",
    ],
)
def test_strict_policy_and_existing_catalog_bounds(change):
    value = request()
    if change.startswith("weight-"):
        value["policy"]["relevance_weight"] = {
            "weight-low": 0.49,
            "weight-high": 1.01,
            "weight-bool": True,
            "weight-string": "0.7",
        }[change]
    elif change.startswith("floor-"):
        value["policy"]["min_relevance_score"] = -0.1 if change == "floor-low" else 1.01
    elif change == "nan":
        value["policy"]["relevance_weight"] = math.nan
    elif change == "extra":
        value["policy"]["arbitrary"] = True
    elif change == "duplicate-id":
        value["catalog"].append(copy.deepcopy(value["catalog"][0]))
    else:
        value["limit"] = True
    with pytest.raises(ValidationError):
        ExplorationRequest.model_validate(value)


def test_http_contract_openapi_and_existing_content_default_are_preserved():
    value = request()
    with TestClient(app) as client:
        result = client.post(PATH, json=value)
        assert result.status_code == 200
        assert (
            result.json()
            == recommend_exploration(ExplorationRequest.model_validate(value)).model_dump()
        )
        regular = {k: v for k, v in value.items() if k != "policy"}
        assert (
            client.post("/v1/recommendations/content", json=regular).json()
            == recommend_content(ContentRecommendationRequest.model_validate(regular)).model_dump()
        )
        schema = client.get("/openapi.json").json()
        assert set(schema["paths"][PATH]["post"]["responses"]) >= {"200", "408", "413", "422"}


@pytest.mark.parametrize("media", ["application/json", "application/vnd.pubburi+json", None])
def test_new_endpoint_applies_duplicate_keys_malformed_priority_and_raw_size_limit(media):
    headers = {} if media is None else {"Content-Type": media}
    with TestClient(app) as client:
        response = client.post(PATH, content='{"catalog":[],"catalog":[]}', headers=headers)
        assert (
            response.status_code == 422
            and response.json()["detail"][0]["type"] == "duplicate_json_key"
        )
        response = client.post(
            PATH, content='{"catalog":[],"catalog":[]} trailing', headers=headers
        )
        original = client.post(
            "/v1/recommendations/content",
            content='{"catalog":[],"catalog":[]} trailing',
            headers=headers,
        )
        assert response.status_code == original.status_code == 422
        assert response.json() == original.json()  # Preserve the framework's media-specific error.
        assert (
            client.post(PATH, content=b" " * (512 * 1024 + 1), headers=headers).status_code == 413
        )


def test_new_endpoint_absolute_receive_deadline_precedes_schema_fit():
    called = False

    async def inner(scope, receive, send):
        nonlocal called
        called = True

    middleware = CatalogRequestLimit(inner, body_timeout_seconds=0.01)

    async def run():
        async def receive():
            await asyncio.sleep(0.1)
            return {"type": "http.request", "body": b"{", "more_body": True}

        messages = []

        async def send(message):
            messages.append(message)

        await middleware({"type": "http", "method": "POST", "path": PATH}, receive, send)
        return messages

    messages = asyncio.run(run())
    assert not called and messages[0]["status"] == 408


def test_startup_openapi_and_empty_exploration_do_not_import_model_runtime():
    code = (
        "from fastapi.testclient import TestClient;"
        "from pubburi_recommendation.main import app;import sys;c=TestClient(app);"
        "assert c.get('/openapi.json').status_code==200;"
        "assert c.post('/v1/recommendations/exploration',json={'catalog':[]}).status_code==200;"
        "assert 'numpy' not in sys.modules and 'sklearn' not in sys.modules"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, result.stderr
