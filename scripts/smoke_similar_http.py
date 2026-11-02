"""Installed R03 reference contracts with authored facts, not user-quality labels."""

import json
import math
import socket
from http.client import HTTPResponse
from urllib.parse import urlsplit

PATH = "/v1/recommendations/similar"


def verify_similar_http(base_url: str, request_json) -> None:
    schema = request_json(base_url, "/openapi.json")
    if not set(schema["paths"][PATH]["post"]["responses"]) >= {"200", "408", "413", "422"}:
        raise RuntimeError("Installed wheel omitted similar/error OpenAPI contracts")
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
                (1, "reference"),
                (2, "reference"),
                (3, "other"),
                (4, "excluded"),
                (5, "unavailable"),
            )
        ],
        "reference_product_id": 1,
        "constraints": {"exclude_product_ids": [4], "max_price_krw": 1500},
        "limit": 3,
    }
    regular = {
        "catalog": body["catalog"],
        "profile": {"taste_tags": ["authored wanted"]},
        "constraints": body["constraints"],
        "limit": 100,
    }
    before = request_json(base_url, "/v1/recommendations/content", body=regular, timeout=30)
    result = request_json(base_url, PATH, body=body, timeout=30)
    original = next(item for item in before["items"] if item["product_id"] == 3)
    if (
        result["algorithm"] != "b1-tfidf-minmax-v1"
        or result["fit_scope"] != "request_catalog"
        or result["reference_state"] != "available"
        or result["reference_product_id"] != 1
        or result["reference_sku_group"] != "reference"
        or result["profile_source"] != "reference_product_facts"
        or result["reference_group_policy"] != "exclude_reference_group"
        or result["eligible_count"] != 1
        or result["excluded_reference_group_count"] != 2
        or result["items"] != [original]
        or result["fallback_reason"] is not None
        or not math.isclose(
            original["score"], sum(part["contribution"] for part in original["contributions"])
        )
    ):
        raise RuntimeError("Installed similar API changed reference, constraints or B1 evidence")
    for ref_id, state, reason in (
        (99, "missing", "reference_not_in_catalog"),
        (5, "unavailable", "reference_unavailable"),
    ):
        cold = request_json(base_url, PATH, body={**body, "reference_product_id": ref_id})
        if (
            cold["items"]
            or cold["reference_state"] != state
            or cold["fallback_reason"] != reason
            or cold["eligible_count"] is not None
            or cold["model_fingerprint"] is not None
            or cold["representation_fitted"]
        ):
            raise RuntimeError("Installed similar API invented an unusable reference")
    if request_json(base_url, PATH, body=body, timeout=30) != result:
        raise RuntimeError("Installed similar requests shared reference/model state")
    request_json(base_url, PATH, body={**body, "reference_product_id": True}, expected_status=422)
    request_json(base_url, PATH, body={"catalog": [], "padding": "x" * 524288}, expected_status=413)
    # Production receive budget, never a shortened timeout or a CPU-fit deadline claim.
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
            raise RuntimeError("Installed similar API failed its partial-body deadline")
