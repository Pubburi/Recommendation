"""Installed R07 explicit-context contracts using authored facts and original B1 evidence."""

import json
import socket
from http.client import HTTPResponse
from urllib.parse import urlsplit

PATH = "/v1/recommendations/context"


def verify_context_http(base_url: str, request_json) -> None:
    schema = request_json(base_url, "/openapi.json")
    if not set(schema["paths"][PATH]["post"]["responses"]) >= {"200", "408", "413", "422"}:
        raise RuntimeError("Installed wheel omitted context/error OpenAPI contracts")
    body = {
        "catalog": [
            {
                "product_id": pid,
                "sku_group": group,
                "available": pid not in (7, 10),
                "taste_tags": [taste],
                "price_krw": None if pid == 9 else 1000,
            }
            for pid, group, taste in (
                (1, "a", "authored dry"),
                (2, "a", "authored dry"),
                (3, "b", "authored sweet"),
                (4, "b", "authored sweet"),
                (5, "c", "authored dry"),
                (6, "d", "authored sweet"),
                (7, "off", "authored dry"),
                (8, "off", "authored dry"),
                (9, "unknown-price", "authored dry"),
                (10, "unavailable", "authored dry"),
                (11, "excluded", "authored dry"),
            )
        ],
        "reference_product_ids": [3, 1, 7, 99],
        "constraints": {"exclude_product_ids": [11], "max_price_krw": 1500},
        "limit": 4,
    }
    result = request_json(base_url, PATH, body=body, timeout=30)
    if (
        result["aggregation_algorithm"] != "r07-max-reference-v1"
        or result["fit_scope"] != "request_catalog"
        or result["profile_source"] != "explicit_context_product_facts"
        or result["reference_group_policy"] != "exclude_all_known_reference_groups"
        or [item["product_id"] for item in result["items"]] != [5, 6]
        or result["matches"]
        != [
            {"product_id": 5, "reference_product_id": 1},
            {"product_id": 6, "reference_product_id": 3},
        ]
        or result["eligible_count"] != 2
        or result["excluded_reference_group_count"] != 6
        or result["evaluated_reference_count"] != 2
        or [row["state"] for row in result["references"]]
        != ["available", "available", "unavailable", "missing"]
        or result["fallback_reason"] is not None
    ):
        raise RuntimeError("Installed context changed references, hard bounds or max aggregation")
    for item, match in zip(result["items"], result["matches"], strict=True):
        single = request_json(
            base_url,
            "/v1/recommendations/similar",
            body={key: value for key, value in body.items() if key != "reference_product_ids"}
            | {"reference_product_id": match["reference_product_id"]},
            timeout=30,
        )
        original = next(row for row in single["items"] if row["product_id"] == item["product_id"])
        if item != original or result["model_fingerprint"] != single["model_fingerprint"]:
            raise RuntimeError("Installed context changed original winning B1 score/contributions")
    reversed_body = {
        **body,
        "catalog": list(reversed(body["catalog"])),
        "reference_product_ids": list(reversed(body["reference_product_ids"])),
    }
    if request_json(base_url, PATH, body=reversed_body, timeout=30) != result:
        raise RuntimeError("Installed context request order changed model/results")
    cold = request_json(base_url, PATH, body={**body, "reference_product_ids": [7, 99]})
    if (
        cold["items"]
        or cold["matches"]
        or cold["eligible_count"] is not None
        or cold["excluded_reference_group_count"] is not None
        or cold["model_fingerprint"] is not None
        or cold["representation_fitted"]
        or cold["fallback_reason"] != "no_usable_references"
    ):
        raise RuntimeError("Installed context invented usable reference facts or evaluated counts")
    for refs in ([True], [1, 1], []):
        request_json(
            base_url, PATH, body={**body, "reference_product_ids": refs}, expected_status=422
        )
    request_json(base_url, PATH, body={"catalog": [], "padding": "x" * 524288}, expected_status=413)
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
            raise RuntimeError("Installed context failed its production partial-body deadline")
