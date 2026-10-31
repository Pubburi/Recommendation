"""Handwritten fictional inputs validate contracts, not real customer preferences."""

import asyncio
import itertools

import pytest
from fastapi.testclient import TestClient

from pubburi_recommendation.main import app
from pubburi_recommendation.request_limits import CatalogRequestLimit


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def product(product_id, **attributes):
    return {"product_id": product_id, "available": True, **attributes}


def test_cold_start_has_stable_order_without_learning_or_input_order_bias(client):
    catalog = [product(4), product(1), product(3, available=False), product(2)]
    for permutation in itertools.permutations(catalog):
        response = client.post("/v1/recommendations/baseline", json={"catalog": permutation})
        assert response.status_code == 200
        assert response.json() == {
            "algorithm": "b0-id-ascending-v1",
            "items": [
                {"product_id": pid, "reasons": ["available", "deterministic_baseline"]}
                for pid in [1, 2, 4]
            ],
            "eligible_count": 3,
            "fallback_reason": None,
        }


def test_all_hard_constraints_precede_limit_and_missing_values_fail_closed(client):
    # Synthetic prices/ABV: these values describe this test only, not real drinks.
    valid = {"category": "fixture-a", "price_krw": 1000, "abv_percent": 5}
    catalog = [
        product(1, **valid, available=False),
        product(2, **valid),
        product(3, **{**valid, "category": "fixture-b"}),
        product(4, **{**valid, "price_krw": 2001}),
        product(5, **{**valid, "abv_percent": 10.1}),
        product(6, **{**valid, "price_krw": None}),
        product(7, **{**valid, "abv_percent": None}),
        product(8, **{**valid, "category": None}),
        product(9, **valid),
        product(10, **{**valid, "price_krw": 2000, "abv_percent": 10}),
    ]
    constraints = {
        "categories": ["fixture-a"],
        "exclude_product_ids": [2],
        "min_price_krw": 1000,
        "max_price_krw": 2000,
        "min_abv_percent": 5,
        "max_abv_percent": 10,
    }
    result = client.post(
        "/v1/recommendations/baseline",
        json={
            "catalog": catalog,
            "constraints": constraints,
            "limit": 1,
        },
    ).json()
    assert result["eligible_count"] == 2
    assert result["items"] == [
        {
            "product_id": 9,
            "reasons": [
                "available",
                "category_match",
                "price_within_range",
                "abv_within_range",
                "deterministic_baseline",
            ],
        }
    ]
    assert result["fallback_reason"] is None


@pytest.mark.parametrize("catalog", [[], [product(1, available=False)], [product(1)]])
def test_empty_candidates_do_not_relax_constraints(client, catalog):
    response = client.post(
        "/v1/recommendations/baseline",
        json={
            "catalog": catalog,
            "constraints": {"exclude_product_ids": [1]},
        },
    )
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["eligible_count"] == 0
    assert response.json()["fallback_reason"] == "no_eligible_products"


@pytest.mark.parametrize(
    "constraints, expected, reasons",
    [
        ({}, [1, 2, 3], ["available", "deterministic_baseline"]),
        ({"max_price_krw": 0}, [2], ["available", "price_within_range", "deterministic_baseline"]),
        ({"min_abv_percent": 0}, [3], ["available", "abv_within_range", "deterministic_baseline"]),
    ],
)
def test_unknown_is_distinct_from_zero_and_reasons_use_only_requested_filters(
    client,
    constraints,
    expected,
    reasons,
):
    result = client.post(
        "/v1/recommendations/baseline",
        json={
            "catalog": [product(1), product(2, price_krw=0), product(3, abv_percent=0)],
            "constraints": constraints,
        },
    ).json()
    assert [item["product_id"] for item in result["items"]] == expected
    assert all(item["reasons"] == reasons for item in result["items"])


def test_omitted_and_null_unknown_attributes_are_equivalent(client):
    omitted = {"catalog": [product(1)], "constraints": {"max_price_krw": 2000}}
    explicit = {**omitted, "catalog": [product(1, category=None, price_krw=None, abv_percent=None)]}
    assert (
        client.post("/v1/recommendations/baseline", json=omitted).json()
        == client.post(
            "/v1/recommendations/baseline",
            json=explicit,
        ).json()
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"catalog": [product(1), product(1, available=False)]},
        {"catalog": [product(True)]},
        {"catalog": [product("1")]},
        {"catalog": [product(0)]},
        {"catalog": [product(2_147_483_648)]},
        {"catalog": [{"product_id": 1}]},
        {"catalog": [product(1, available=1)]},
        {"catalog": [product(1, price_krw=-1)]},
        {"catalog": [product(1, price_krw=1.5)]},
        {"catalog": [product(1, price_krw=True)]},
        {"catalog": [product(1, abv_percent=-0.1)]},
        {"catalog": [product(1, abv_percent=100.1)]},
        {"catalog": [product(1, category="  ")]},
        {"catalog": [product(1, category="x" * 65)]},
        {"catalog": [product(1, unknown_field="value")]},
        {"catalog": [], "limit": 0},
        {"catalog": [], "limit": 101},
        {"catalog": [], "limit": True},
        {"catalog": [], "unknown_field": "value"},
        {"catalog": [], "constraints": {"min_price_krw": 2, "max_price_krw": 1}},
        {"catalog": [], "constraints": {"min_abv_percent": 10, "max_abv_percent": 5}},
        {"catalog": [], "constraints": {"categories": ["x"] * 33}},
        {"catalog": [], "constraints": {"exclude_product_ids": [1] * 1001}},
        {"catalog": [product(pid) for pid in range(1, 1002)]},
    ],
)
def test_invalid_or_oversized_requests_are_rejected_without_echoing_inputs(client, payload):
    response = client.post("/v1/recommendations/baseline", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"]
    assert all(set(error) == {"loc", "msg", "type"} for error in response.json()["detail"])


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_numeric_input_has_a_valid_json_error_response(client, value):
    response = client.post(
        "/v1/recommendations/baseline",
        content='{"catalog":[{"product_id":1,"available":true,"abv_percent":' + value + "}] }",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "finite_number"


def test_boundary_size_and_full_constraint_ranges_are_supported(client):
    response = client.post(
        "/v1/recommendations/baseline",
        json={
            "catalog": [product(pid, price_krw=0, abv_percent=100) for pid in range(1000, 0, -1)],
            "constraints": {
                "min_price_krw": 0,
                "max_price_krw": 2_147_483_647,
                "min_abv_percent": 0,
                "max_abv_percent": 100,
            },
            "limit": 100,
        },
    )
    assert response.status_code == 200
    assert response.json()["eligible_count"] == 1000
    assert [item["product_id"] for item in response.json()["items"]] == list(range(1, 101))


def test_raw_request_byte_limit_is_inclusive(client):
    body = b'{"catalog":[]}'
    body += b" " * (524288 - len(body))
    assert (
        client.post(
            "/v1/recommendations/baseline",
            content=body,
            headers={"Content-Type": "application/json"},
        ).status_code
        == 200
    )
    response = client.post(
        "/v1/recommendations/baseline",
        content=body + b" ",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json() == {"detail": "Catalog request exceeds 524288 bytes"}


def test_chunked_body_cannot_bypass_the_raw_request_limit(client):
    def body_chunks():
        yield b'{"catalog":[]}'
        for _ in range(9):
            yield b" " * 65536

    response = client.post(
        "/v1/recommendations/baseline",
        content=body_chunks(),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413


def test_asgi_stream_enforces_cumulative_limit_before_parsing():
    async def scenario():
        messages = iter(
            [{"type": "http.request", "body": b" " * 65536, "more_body": True} for _ in range(9)]
        )
        sent = []

        async def receive():
            return next(messages)

        async def send(message):
            sent.append(message)

        async def downstream(_scope, _receive, _send):
            pytest.fail("Oversized body reached JSON parsing")

        await CatalogRequestLimit(downstream)(
            {"type": "http", "method": "POST", "path": "/v1/recommendations/baseline"},
            receive,
            send,
        )
        assert sent[0]["status"] == 413

    asyncio.run(scenario())
