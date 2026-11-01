"""Installed opt-in exploration HTTP behavior with authored facts, no user-quality claims."""

import json
import math
import socket
from http.client import HTTPResponse
from urllib.parse import urlsplit

PATH = "/v1/recommendations/exploration"


def verify_exploration_http(base_url: str, request_json) -> None:
    schema = request_json(base_url, "/openapi.json")
    if not set(schema["paths"][PATH]["post"]["responses"]) >= {"200", "408", "413", "422"}:
        raise RuntimeError("Installed wheel omitted exploration/error OpenAPI contracts")
    body = {
        "catalog": [
            {
                "product_id": index,
                "available": index != 5,
                "sku_group": group,
                "taste_tags": ["authored wanted"],
                "price_krw": 1000,
            }
            for index, group in (
                (1, "same"),
                (2, "same"),
                (3, "different"),
                (4, "excluded"),
                (5, "unavailable"),
            )
        ],
        "profile": {"taste_tags": ["authored wanted"]},
        "constraints": {"exclude_product_ids": [4], "max_price_krw": 1500},
        "limit": 3,
    }
    regular = {key: value for key, value in body.items() if key != "policy"}
    base = request_json(base_url, "/v1/recommendations/content", body=regular, timeout=30)
    result = request_json(base_url, PATH, body=body, timeout=30)
    by_id = {item["product_id"]: item for item in base["items"]}
    if (
        result["reranking_algorithm"] != "r08-text-mmr-group-v1"
        or result["fit_scope"] != "request_catalog"
        or result["eligible_count"] != 3
        or result["candidate_pool_size"] != 3
        or result["pool_truncated"]
        or result["selected_count"] != 2
        or result["selected_group_count"] != 2
        or [item["product_id"] for item in result["items"]] != [1, 3]
        or result["exploration_reason"] != "selected"
        or any(item != by_id[item["product_id"]] for item in result["items"])
    ):
        raise RuntimeError("Installed exploration changed eligibility, groups or B1 contributions")
    if any(not math.isfinite(item["selection_score"]) for item in result["selections"]):
        raise RuntimeError("Installed exploration returned an invalid selection score")
    if request_json(base_url, PATH, body=body, timeout=30) != result:
        raise RuntimeError("Installed exploration request state was not isolated")
    for catalog in ([], body["catalog"]):
        cold = request_json(base_url, PATH, body={"catalog": catalog}, timeout=30)
        if cold["items"] or cold["selections"] or cold["exploration_reason"] != "baseline_fallback":
            raise RuntimeError("Installed exploration invented a cold-start preference")
    for invalid in (
        {**body, "policy": {"relevance_weight": True}},
        {**body, "catalog": [body["catalog"][0]] * 2},
    ):
        request_json(base_url, PATH, body=invalid, expected_status=422)
    request_json(base_url, PATH, body={"catalog": [], "padding": "x" * 524288}, expected_status=413)
    # Production ten-second receive deadline; no CPU-fit cancellation claim.
    target = urlsplit(base_url)
    with socket.create_connection((target.hostname, target.port), timeout=15) as connection:
        connection.sendall(
            (
                f"POST {PATH} HTTP/1.1\r\nHost: {target.netloc}\r\n"
                "Content-Type: application/json\r\nContent-Length: 20\r\nConnection: close\r\n\r\n{"
            ).encode()
        )
        response = HTTPResponse(connection)
        response.begin()
        if response.status != 408 or json.loads(response.read(1024)) != {
            "detail": "Catalog request body timed out"
        }:
            raise RuntimeError("Installed exploration failed its partial-body deadline")
