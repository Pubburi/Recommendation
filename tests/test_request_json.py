"""Authored malformed requests preserve unambiguous identity/constraint boundaries."""

import asyncio
import json
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from pubburi_recommendation.main import app
from pubburi_recommendation.request_limits import CatalogRequestLimit

EXPECTED = {
    "detail": [
        {
            "type": "duplicate_json_key",
            "loc": ["body"],
            "msg": "Catalog JSON object keys must be unique",
        }
    ]
}


def body_for(endpoint, mutation):
    group = ',"sku_group":"authored"' if endpoint == "content" else ""
    product = '{"product_id":1,"available":true,"abv_percent":40' + group + "}"
    if mutation == "identity":
        return (
            '{"catalog":['
            + product.replace('"product_id":1', '"product_id":1,"product_id":2')
            + "]}"
        )
    if mutation == "root":
        return '{"catalog":[' + product + '],"catalog":[]}'
    if mutation == "escaped":
        return (
            '{"catalog":['
            + product
            + '],"constraints":{"max_abv_percent":5,"m\\u0061x_abv_percent":50}}'
        )
    if mutation == "private":
        return '{"catalog":[],"private_catalog_key":1,"private_catalog_key":2}'
    value = 5 if mutation == "identical" else 50
    return (
        '{"catalog":['
        + product
        + '],"constraints":{"max_abv_percent":5,"max_abv_percent":'
        + str(value)
        + "}}"
    )


@pytest.mark.parametrize("endpoint", ["baseline", "content"])
@pytest.mark.parametrize(
    "mutation", ["hard", "identity", "root", "escaped", "private", "identical"]
)
def test_duplicate_object_names_are_rejected_without_echoing_key_or_values(endpoint, mutation):
    with TestClient(app) as client:
        response = client.post(
            "/v1/recommendations/" + endpoint,
            content=body_for(endpoint, mutation),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 422
    assert response.json() == EXPECTED


@pytest.mark.parametrize(
    "media",
    [None, "application/json", "Application/JSON; charset=utf-8", "application/vnd.pubburi+json"],
)
def test_json_media_and_missing_content_type_share_the_duplicate_boundary(media):
    headers = {} if media is None else {"Content-Type": media}
    with TestClient(app) as client:
        response = client.post(
            "/v1/recommendations/baseline", content=body_for("baseline", "hard"), headers=headers
        )
    assert response.status_code == 422 and response.json() == EXPECTED


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-32"])
def test_decoded_equivalent_names_cannot_bypass_the_boundary_in_supported_json_encodings(encoding):
    with TestClient(app) as client:
        response = client.post(
            "/v1/recommendations/baseline",
            content=body_for("baseline", "escaped").encode(encoding),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 422 and response.json() == EXPECTED


def test_duplicate_name_split_across_raw_chunks_never_reaches_the_route():
    async def exercise():
        messages = iter(
            [
                {"type": "http.request", "body": b'{"catalog":[],"cata', "more_body": True},
                {"type": "http.request", "body": b'log":[]}', "more_body": False},
            ]
        )
        sent = []

        async def receive():
            return next(messages)

        async def send(message):
            sent.append(message)

        async def downstream(*_args):
            pytest.fail("Ambiguous JSON reached the schema/model route")

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/v1/recommendations/content",
            "headers": [],
        }
        await CatalogRequestLimit(downstream)(scope, receive, send)
        assert sent[0]["status"] == 422
        assert json.loads(sent[1]["body"]) == EXPECTED

    asyncio.run(exercise())


@pytest.mark.parametrize("endpoint", ["baseline", "content"])
def test_same_names_in_different_objects_and_strings_are_valid(endpoint):
    products = [
        {
            "product_id": pid,
            "available": True,
            "category": "product_id product_id",
            "abv_percent": 5,
        }
        for pid in (1, 2)
    ]
    if endpoint == "content":
        for row in products:
            row["sku_group"] = "authored-" + str(row["product_id"])
    with TestClient(app) as client:
        response = client.post(
            "/v1/recommendations/" + endpoint,
            json={"catalog": products, "constraints": {"max_abv_percent": 5}},
        )
    assert response.status_code == 200
    assert [row["product_id"] for row in response.json()["items"]] == [1, 2]


def test_size_limit_still_precedes_json_ambiguity_and_other_parse_failures_stay_client_errors():
    with TestClient(app, raise_server_exceptions=False) as client:
        oversized = body_for("baseline", "hard").encode() + b" " * 524288
        assert (
            client.post(
                "/v1/recommendations/baseline",
                content=oversized,
                headers={"Content-Type": "application/json"},
            ).status_code
            == 413
        )
        for body in (b'{"catalog":', b"\xff", b'{"x":' + b"[" * 2000 + b"0" + b"]" * 2000 + b"}"):
            response = client.post(
                "/v1/recommendations/baseline",
                content=body,
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code in (400, 422)
            assert "Internal Server Error" not in response.text
        nonjson = client.post(
            "/v1/recommendations/baseline",
            content=body_for("baseline", "hard"),
            headers={"Content-Type": "text/plain"},
        )
        assert nonjson.status_code == 422 and nonjson.json() != EXPECTED


def test_rejected_nonempty_content_does_not_load_or_execute_model_runtime():
    code = """import sys
from fastapi.testclient import TestClient
from pubburi_recommendation.main import app
with TestClient(app) as client:
 response=client.post('/v1/recommendations/content',content='{"catalog":[],"catalog":[]}',headers={'Content-Type':'application/json'})
 assert response.status_code==422
 assert client.get('/health').status_code==200
names=('numpy','sklearn','pubburi_recommendation.content_model')
assert not any(name in sys.modules for name in names)
"""
    subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, timeout=10)
