"""Installed R05 explicit-feedback facts, fallback labels and hard-boundary contracts."""

import copy
import json
import socket
from http.client import HTTPResponse
from urllib.parse import urlsplit

PATH = "/v1/recommendations/feedback"


def verify_feedback_http(base_url: str, request_json) -> None:
    schema = request_json(base_url, "/openapi.json")
    if not set(schema["paths"][PATH]["post"]["responses"]) >= {"200", "408", "413", "422"}:
        raise RuntimeError("Installed wheel omitted feedback/error OpenAPI contracts")
    body = {
        "catalog": [
            {
                "product_id": pid,
                "sku_group": group,
                "taste_tags": ["authored " + taste],
                "available": pid not in (5, 8),
                "price_krw": None if pid == 7 else 1000,
            }
            for pid, group, taste in (
                (1, "anchor", "dry"),
                (2, "anchor", "dry"),
                (3, "candidate", "dry"),
                (4, "profile", "fruity"),
                (5, "negative", "dry"),
                (6, "negative", "dry"),
                (7, "unknown-price", "dry"),
                (8, "off", "sweet"),
                (9, "off", "sweet"),
                (10, "excluded", "dry"),
                (11, "unrelated", "other"),
            )
        ],
        "profile": {"taste_tags": ["authored fruity"]},
        "feedback": {"positive_product_ids": [8, 1, 99], "not_interested_product_ids": [5]},
        "constraints": {"max_price_krw": 1500, "exclude_product_ids": [10]},
    }
    result = request_json(base_url, PATH, body=body, timeout=30)
    if (
        result["feedback_algorithm"] != "r05-max-explicit-feedback-v1"
        or result["ranking_mode"] != "positive_feedback"
        or [row["product_id"] for row in result["items"]] != [3, 4]
        or result["matches"]
        != [
            {"product_id": 3, "source": "positive_feedback", "positive_product_id": 1},
            {"product_id": 4, "source": "profile", "positive_product_id": None},
        ]
        or result["eligible_count"] != 3
        or result["excluded_not_interested_count"] != 2
        or result["excluded_positive_group_count"] != 4
        or result["evaluated_positive_count"] != 1
        or result["informative_positive_count"] != 1
        or [row["state"] for row in result["positive_references"]]
        != ["available", "unavailable", "missing"]
    ):
        raise RuntimeError("Installed feedback changed max evidence, exclusions or state counts")
    base = {key: value for key, value in body.items() if key != "feedback"}
    for item, match in zip(result["items"], result["matches"], strict=True):
        endpoint = "/v1/recommendations/content"
        original_body = base
        if match["source"] == "positive_feedback":
            endpoint = "/v1/recommendations/similar"
            original_body = {key: value for key, value in base.items() if key != "profile"}
            original_body["reference_product_id"] = match["positive_product_id"]
        original = request_json(base_url, endpoint, body=original_body, timeout=30)
        evidence = next(row for row in original["items"] if row["product_id"] == item["product_id"])
        if item != evidence or result["model_fingerprint"] != original["model_fingerprint"]:
            raise RuntimeError("Installed feedback changed original B1 winning contributions")
    reverse = copy.deepcopy(body)
    reverse["catalog"].reverse()
    reverse["feedback"]["positive_product_ids"].reverse()
    if request_json(base_url, PATH, body=reverse, timeout=30) != result:
        raise RuntimeError("Installed feedback retained request order/state")
    cold = request_json(
        base_url,
        PATH,
        body={
            **body,
            "profile": {},
            "feedback": {"positive_product_ids": [8, 99], "not_interested_product_ids": [5]},
        },
        timeout=30,
    )
    if (
        cold["ranking_mode"] != "profile_fallback"
        or cold["fallback_reason"] != "no_supported_preferences"
        or not cold["items"]
        or any(row["source"] != "baseline" for row in cold["matches"])
        or any(row["score"] != 0 for row in cold["items"])
    ):
        raise RuntimeError("Installed feedback mislabeled B0 fallback as positive evidence")
    blocked = copy.deepcopy(body)
    blocked["feedback"]["not_interested_product_ids"].append(2)
    conflict = request_json(base_url, PATH, body=blocked, timeout=30)
    if (
        conflict["positive_references"][0]["state"] != "blocked"
        or conflict["evaluated_positive_count"]
    ):
        raise RuntimeError("Installed feedback ignored a negative group conflict")
    blocked["feedback"]["not_interested_product_ids"] = [
        row["product_id"] for row in body["catalog"]
    ]
    empty = request_json(base_url, PATH, body=blocked, timeout=30)
    if (
        empty["items"]
        or empty["eligible_count"]
        or empty["fallback_reason"] != "no_eligible_products"
    ):
        raise RuntimeError("Installed feedback relaxed exclusions to fill an empty result")
    for ids in ([True], [1, 1], list(range(1, 22))):
        request_json(
            base_url,
            PATH,
            body={**body, "feedback": {"positive_product_ids": ids}},
            expected_status=422,
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
            raise RuntimeError("Installed feedback violated its production partial-body deadline")
