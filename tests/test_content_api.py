"""Authored HTTP contracts; no real catalog, user data, or quality measurements."""

import asyncio
import copy
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from pubburi_recommendation.content_model import FittedContentModel
from pubburi_recommendation.main import app
from pubburi_recommendation.request_limits import CatalogRequestLimit

PATH = "/v1/recommendations/content"


def catalog():
    return [
        {
            "product_id": 3,
            "available": True,
            "sku_group": "authored-c",
            "taste_tags": ["허구 쓴맛"],
            "abv_percent": 15,
            "volume_ml": 750,
            "price_krw": 2000,
        },
        {
            "product_id": 1,
            "available": True,
            "sku_group": "authored-a",
            "taste_tags": ["허구 단맛"],
            "abv_percent": 5,
            "volume_ml": 250,
            "price_krw": 1000,
        },
        {
            "product_id": 2,
            "available": True,
            "sku_group": "authored-b",
            "taste_tags": None,
            "abv_percent": None,
            "volume_ml": None,
            "price_krw": None,
        },
    ]


@pytest.fixture
def client():
    with TestClient(app) as value:
        yield value


def test_existing_b1_engine_is_exposed_with_exact_contributions_and_request_local_scope(client):
    response = client.post(
        PATH,
        json={
            "catalog": catalog(),
            "profile": {
                "taste_tags": ["허구 단맛"],
                "preferred_abv_percent": 5,
                "preferred_volume_ml": 250,
            },
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["fit_scope"] == "request_catalog" and result["representation_fitted"]
    assert result["algorithm"] == "b1-tfidf-minmax-v1"
    assert len(result["model_fingerprint"]) == 64
    assert [item["product_id"] for item in result["items"]] == [1, 2, 3]
    assert result["items"][0]["score"] == pytest.approx(1)
    for item in result["items"]:
        assert item["score"] == pytest.approx(
            sum(part["contribution"] for part in item["contributions"])
        )
        assert all(part["contribution"] > 0 for part in item["contributions"])
    assert result["items"][1]["score"] == 0 and result["items"][1]["contributions"] == []
    assert "content_similarity" not in result["items"][1]["reasons"]


def test_soft_preferences_never_relax_hard_exclusion_unknown_or_availability(client):
    products = catalog()
    products[0]["available"] = False
    result = client.post(
        PATH,
        json={
            "catalog": products,
            "profile": {"taste_tags": ["허구 단맛"]},
            "constraints": {"exclude_product_ids": [1], "max_price_krw": 3000},
        },
    ).json()
    assert result["items"] == [] and result["eligible_count"] == 0
    assert result["fallback_reason"] == "no_eligible_products"
    assert result["representation_fitted"]
    result = client.post(
        PATH,
        json={
            "catalog": catalog(),
            "profile": {"taste_tags": ["허구 단맛"]},
            "constraints": {"min_abv_percent": 10},
            "limit": 1,
        },
    ).json()
    assert [item["product_id"] for item in result["items"]] == [3]
    assert result["eligible_count"] == 1


@pytest.mark.parametrize("profile", [{}, {"taste_tags": ["미등록 허구 태그"]}])
def test_empty_or_oov_profiles_return_deterministic_constrained_fallback(client, profile):
    result = client.post(PATH, json={"catalog": catalog(), "profile": profile}).json()
    assert [item["product_id"] for item in result["items"]] == [1, 2, 3]
    assert all(
        item["score"] == 0 and "deterministic_baseline" in item["reasons"]
        for item in result["items"]
    )
    assert result["fallback_reason"] == "no_supported_preferences"


def test_empty_catalog_never_calls_fit_or_invents_a_trained_fingerprint(client, monkeypatch):
    monkeypatch.setattr(
        FittedContentModel, "fit", lambda _: pytest.fail("empty catalog must not fit")
    )
    result = client.post(
        PATH, json={"catalog": [], "profile": {"taste_tags": ["허구 단맛"]}}
    ).json()
    assert result["representation_fitted"] is False and result["model_fingerprint"] is None
    assert result["items"] == [] and result["fallback_reason"] == "no_eligible_products"
    assert result["supported_profile_tokens"] == 0 and result["unknown_profile_tokens"] == 1


@pytest.mark.parametrize("tags", [None, []])
def test_nonempty_but_uninformative_catalog_does_not_claim_a_fitted_representation(client, tags):
    products = [
        {
            "product_id": pid,
            "available": True,
            "sku_group": "authored-unknown",
            "taste_tags": tags,
            "aroma_tags": tags,
            "abv_percent": 0,
            "volume_ml": 250,
        }
        for pid in [2, 1]
    ]
    result = client.post(
        PATH,
        json={
            "catalog": products,
            "profile": {"preferred_abv_percent": 0, "preferred_volume_ml": 250},
        },
    ).json()
    assert result["representation_fitted"] is False and result["model_fingerprint"] is None
    assert result["active_numeric_preferences"] == []
    assert result["fallback_reason"] == "no_supported_preferences"
    assert [item["product_id"] for item in result["items"]] == [1, 2]
    assert all(item["contributions"] == [] and item["score"] == 0 for item in result["items"])


def test_observed_numeric_variation_is_a_usable_representation_without_text(client):
    products = [
        {"product_id": 1, "available": True, "sku_group": "authored-a", "abv_percent": 0},
        {"product_id": 2, "available": True, "sku_group": "authored-b", "abv_percent": 10},
    ]
    result = client.post(
        PATH, json={"catalog": products, "profile": {"preferred_abv_percent": 0}}
    ).json()
    assert result["representation_fitted"] and result["model_fingerprint"]
    assert result["active_numeric_preferences"] == ["abv_percent"]
    assert result["items"][0]["product_id"] == 1 and result["items"][0]["score"] == 1


def test_supported_profile_without_eligible_overlap_is_distinct_from_oov(client):
    products = catalog()
    products[1]["available"] = False
    result = client.post(
        PATH, json={"catalog": products, "profile": {"taste_tags": ["허구 단맛"]}}
    ).json()
    assert result["supported_profile_tokens"] == 1 and result["unknown_profile_tokens"] == 0
    assert result["fallback_reason"] == "no_matching_features"
    assert all(
        item["score"] == 0 and "deterministic_baseline" in item["reasons"]
        for item in result["items"]
    )


def test_no_fit_at_startup_health_or_b0(monkeypatch):
    monkeypatch.setattr(
        FittedContentModel, "fit", lambda _: pytest.fail("non-content paths must not fit")
    )
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.post("/v1/recommendations/baseline", json={"catalog": []}).status_code == 200


def test_fresh_process_startup_and_openapi_do_not_load_the_model_libraries():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from pubburi_recommendation.main import app; app.openapi(); "
            "assert 'numpy' not in sys.modules and 'sklearn' not in sys.modules",
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_sequential_and_concurrent_requests_do_not_share_vocabulary_scalers_or_state(client):
    a = {"catalog": catalog(), "profile": {"taste_tags": ["허구 단맛"]}}
    b = {
        "catalog": [
            {
                "product_id": 11,
                "available": True,
                "sku_group": "other-only",
                "taste_tags": ["전혀 다른 허구 태그"],
                "abv_percent": 100,
            }
        ],
        "profile": {"taste_tags": ["허구 단맛"], "preferred_abv_percent": 5},
    }
    expected_a = client.post(PATH, json=a).json()
    expected_b = client.post(PATH, json=b).json()
    assert (
        expected_b["supported_profile_tokens"] == 0
        and expected_b["active_numeric_preferences"] == []
    )
    assert expected_a["model_fingerprint"] != expected_b["model_fingerprint"]
    assert client.post(PATH, json=a).json() == expected_a
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda body: client.post(PATH, json=body).json(), [a, b, a, b]))
    assert results == [expected_a, expected_b, expected_a, expected_b]
    permuted = copy.deepcopy(a)
    permuted["catalog"].reverse()
    assert client.post(PATH, json=permuted).json() == expected_a


@pytest.mark.parametrize(
    "changes",
    [
        {"catalog": catalog() * 2},
        {"catalog": [{"product_id": "1", "available": True, "sku_group": "a"}]},
        {"catalog": [{"product_id": 1, "available": "true", "sku_group": "a"}]},
        {"catalog": [{"product_id": 1, "available": True}]},
        {"catalog": [{"product_id": 1, "available": True, "sku_group": "a", "volume_ml": 1.5}]},
        {
            "catalog": [
                {
                    "product_id": 1,
                    "available": True,
                    "sku_group": "a",
                    "taste_tags": ["same", " SAME "],
                }
            ]
        },
        {
            "catalog": [
                {"product_id": i + 1, "available": True, "sku_group": "a"} for i in range(1001)
            ]
        },
        {"profile": {"taste_tags": ["x" * 41]}},
        {"profile": {"preferred_abv_percent": 101}},
        {"profile": {"preferred_volume_ml": True}},
        {"constraints": {"min_abv_percent": 10, "max_abv_percent": 5}},
        {"limit": True},
        {"limit": 101},
        {"user_id": "private-marker-must-not-echo"},
    ],
)
def test_content_request_rejects_invalid_types_bounds_duplicates_and_unknown_fields(
    client, changes
):
    response = client.post(PATH, json={"catalog": catalog(), **changes})
    assert response.status_code == 422
    assert "private-marker-must-not-echo" not in response.text


@pytest.mark.parametrize("number", ["NaN", "Infinity", "1e9999"])
def test_nonfinite_input_is_a_safe_json_validation_error(client, number):
    body = '{"catalog":[],"profile":{"preferred_abv_percent":' + number + "}}"
    response = client.post(PATH, content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 422 and response.headers["content-type"].startswith(
        "application/json"
    )
    assert response.json()["detail"] and '"input"' not in response.text


def test_content_body_limit_and_openapi_contract(client):
    body = b'{"catalog":[]}'
    exact = body + b" " * (524288 - len(body))
    assert (
        client.post(PATH, content=exact, headers={"Content-Type": "application/json"}).status_code
        == 200
    )
    response = client.post(PATH, content=exact + b" ", headers={"Content-Type": "application/json"})
    assert response.status_code == 413
    schema = client.get("/openapi.json").json()
    assert set(schema["paths"][PATH]["post"]["responses"]) >= {"200", "408", "413", "422"}
    response_schema = schema["components"]["schemas"]["ContentRecommendationResponse"]
    assert response_schema["properties"]["fit_scope"]["const"] == "request_catalog"
    assert {
        item.get("type") for item in response_schema["properties"]["model_fingerprint"]["anyOf"]
    } == {"string", "null"}


@pytest.mark.parametrize("path", [PATH, "/v1/recommendations/baseline"])
@pytest.mark.parametrize("trickle", [False, True])
def test_body_deadline_is_total_not_reset_by_each_chunk_and_never_enters_fit(path, trickle):
    async def scenario():
        sent = []

        async def receive():
            await asyncio.sleep(0.003 if trickle else 1)
            return {"type": "http.request", "body": b" ", "more_body": True}

        async def send(message):
            sent.append(message)

        async def downstream(*_args):
            pytest.fail("timed out input reached parsing or fit")

        await CatalogRequestLimit(downstream, body_timeout_seconds=0.01)(
            {"type": "http", "method": "POST", "path": path}, receive, send
        )
        assert sent[0]["status"] == 408
        assert json.loads(sent[1]["body"]) == {"detail": "Catalog request body timed out"}

    asyncio.run(scenario())


@pytest.mark.parametrize("path", [PATH, "/v1/recommendations/baseline"])
def test_streaming_size_and_disconnect_boundaries_are_shared_by_both_paths(path):
    async def scenario(disconnect):
        messages = iter(
            [{"type": "http.disconnect"}]
            if disconnect
            else [{"type": "http.request", "body": b" " * 65536, "more_body": True}] * 9
        )
        sent = []

        async def receive():
            return next(messages)

        async def send(message):
            sent.append(message)

        async def downstream(*_args):
            pytest.fail("oversized/disconnected input reached parser or fit")

        await CatalogRequestLimit(downstream)(
            {"type": "http", "method": "POST", "path": path}, receive, send
        )
        assert sent == [] if disconnect else sent[0]["status"] == 413

    asyncio.run(scenario(False))
    asyncio.run(scenario(True))
