"""Exercise installed B1 HTTP contracts with authored requests, never a real catalog."""

import json
import math
import socket
from http.client import HTTPResponse
from urllib.parse import urlsplit

PATH = "/v1/recommendations/content"


def verify_content_http(base_url: str, request_json) -> None:
    # The first nonempty request lazily imports the fit runtime. This is a client bound,
    # not a claim that a CPU worker is cancelled/completed after a server-side timeout.
    original_request_json = request_json

    def request_json(base_url, path, **kwargs):
        return original_request_json(base_url, path, timeout=30, **kwargs)

    schema = request_json(base_url, "/openapi.json")
    if not set(schema["paths"][PATH]["post"]["responses"]) >= {"200", "408", "413", "422"}:
        raise RuntimeError("Installed wheel omitted content/error OpenAPI contracts")
    body = {
        "catalog": [
            {
                "product_id": 3,
                "available": True,
                "sku_group": "authored-c",
                "taste_tags": ["other"],
                "abv_percent": 15,
                "price_krw": 2000,
            },
            {
                "product_id": 1,
                "available": True,
                "sku_group": "authored-a",
                "taste_tags": ["wanted"],
                "abv_percent": 5,
                "price_krw": 1000,
            },
            {"product_id": 2, "available": True, "sku_group": "authored-b"},
        ],
        "profile": {"taste_tags": ["wanted"], "preferred_abv_percent": 5},
        "constraints": {"max_price_krw": 1000},
    }
    result = request_json(base_url, PATH, body=body)
    if (
        result["algorithm"] != "b1-tfidf-minmax-v1"
        or result["fit_scope"] != "request_catalog"
        or not result["representation_fitted"]
        or len(result["model_fingerprint"]) != 64
        or result["eligible_count"] != 1
        or [item["product_id"] for item in result["items"]] != [1]
        or not math.isclose(result["items"][0]["score"], 1)
        or not math.isclose(
            sum(part["contribution"] for part in result["items"][0]["contributions"]),
            result["items"][0]["score"],
        )
    ):
        raise RuntimeError(
            "Installed content engine violated eligibility or contribution contracts"
        )
    other = request_json(
        base_url,
        PATH,
        body={
            "catalog": [
                {
                    "product_id": 11,
                    "available": True,
                    "sku_group": "other",
                    "taste_tags": ["unrelated"],
                }
            ],
            "profile": {"taste_tags": ["wanted"]},
        },
    )
    if (
        other["supported_profile_tokens"] != 0
        or other["fallback_reason"] != "no_supported_preferences"
    ):
        raise RuntimeError("Installed content requests shared vocabulary")
    if request_json(base_url, PATH, body=body) != result:
        raise RuntimeError("Installed content request state was not isolated")
    for catalog in ([], [{"product_id": 1, "available": True, "sku_group": "unknown"}]):
        empty = request_json(base_url, PATH, body={"catalog": catalog})
        if empty["representation_fitted"] or empty["model_fingerprint"] is not None:
            raise RuntimeError("Installed content API claimed a fitted empty representation")
    for invalid in (
        {"catalog": [body["catalog"][0]] * 2},
        {"catalog": [], "profile": {"preferred_abv_percent": float("nan")}},
    ):
        if not request_json(base_url, PATH, body=invalid, expected_status=422).get("detail"):
            raise RuntimeError("Installed content API accepted invalid inputs")
    request_json(base_url, PATH, body={"catalog": [], "padding": "x" * 524288}, expected_status=413)

    # Real partial HTTP body: production ten-second budget, no shortened server configuration.
    target = urlsplit(base_url)
    with socket.create_connection((target.hostname, target.port), timeout=15) as connection:
        connection.sendall(
            (
                f"POST {PATH} HTTP/1.1\r\nHost: {target.netloc}\r\n"
                "Content-Type: application/json\r\nContent-Length: 20\r\n"
                "Connection: close\r\n\r\n{"
            ).encode()
        )
        response = HTTPResponse(connection)
        response.begin()
        content = response.read(1024)
        if response.status != 408 or json.loads(content) != {
            "detail": "Catalog request body timed out"
        }:
            raise RuntimeError("Installed content API failed its partial-body deadline")
