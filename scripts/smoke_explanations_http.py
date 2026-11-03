"""Installed opt-in R04 factual labels, source identity and unchanged default decisions."""

import copy
import json
from urllib.request import ProxyHandler, Request, build_opener


def verify_explanations_http(base_url, request_json):
    def post(endpoint, body):
        request = Request(
            base_url + "/v1/recommendations/" + endpoint,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        with build_opener(ProxyHandler({})).open(request, timeout=30) as response:
            return response.read()

    catalog = [
        dict(
            product_id=pid,
            sku_group=str(pid),
            available=True,
            category="과실주" if pid == 3 else "맥주",
            price_krw=price,
            taste_tags=None if pid == 4 else ["드라이"] if pid == 3 else ["단,맛\n질감"],
            abv_percent=abv,
            volume_ml=volume,
        )
        for pid, abv, volume, price in (
            (1, 0, 330, 0),
            (2, 5, 500, 1000),
            (3, 10, 750, 2000),
            (4, None, None, None),
        )
    ]
    common = {
        "catalog": catalog,
        "constraints": {"categories": ["맥주"], "max_price_krw": 1500, "max_abv_percent": 5},
    }
    profile = {
        "categories": ["맥주"],
        "taste_tags": ["단,맛\n질감"],
        "preferred_abv_percent": 0,
        "preferred_volume_ml": 330,
    }
    for endpoint in ("content", "exploration", "similar", "context", "feedback"):
        body = copy.deepcopy(common)
        if endpoint in ("content", "exploration"):
            body["profile"] = profile
        elif endpoint == "similar":
            body["reference_product_id"] = 1
        elif endpoint == "context":
            body["reference_product_ids"] = [1]
        else:
            body["feedback"] = {"positive_product_ids": [1]}
        original = post(endpoint, body)
        if post(endpoint, body | {"include_explanations": False}) != original:
            raise RuntimeError("Installed explanation opt-out changed original wire")
        enabled = json.loads(post(endpoint, body | {"include_explanations": True}))
        explained = copy.deepcopy(enabled)
        for item in enabled["items"]:
            explanation = item["explanation"]
            expected_comparison = (
                {"kind": "profile"}
                if endpoint in ("content", "exploration")
                else {"kind": "reference_product", "product_id": 1}
            )
            if (
                explanation["comparison"] != expected_comparison
                or explanation["basis"] != "content_similarity"
                or len(explanation["score_evidence"]) != 3
                or not explanation["score_evidence_truncated"]
                or len(json.dumps(explanation, ensure_ascii=False, separators=(",", ":")).encode())
                > 4096
            ):
                raise RuntimeError("Installed explanation changed bounded score/source evidence")
            for evidence in explanation["score_evidence"]:
                if evidence["kind"] == "abv_comparison" and (
                    evidence["actual_value"] != (5 if item["product_id"] == 2 else 0)
                    or evidence["target_value"] != 0
                    or evidence["unit"] != "vol%"
                ):
                    raise RuntimeError("Installed explanation invented numeric facts/target")
            price = next(
                row for row in explanation["filter_evidence"] if row["kind"] == "price_filter"
            )
            if price["label"] != "입력 가격 조건 충족" or price["maximum"] != 1500:
                raise RuntimeError("Installed explanation invented price authority/constraint")
        for item in explained["items"]:
            item.pop("explanation")
        if explained != json.loads(original):
            raise RuntimeError("Installed explanation changed scores/order/reasons/fit fingerprint")
        request_json(
            base_url,
            "/v1/recommendations/" + endpoint,
            body=body | {"include_explanations": None},
            expected_status=422,
        )
    literal = request_json(
        base_url,
        "/v1/recommendations/content",
        body={
            "catalog": catalog,
            "profile": {"taste_tags": ["단,맛\n질감"]},
            "include_explanations": True,
        },
        timeout=30,
    )
    first = literal["items"][0]["explanation"]["score_evidence"][0]
    if first["actual_value"] != "단,맛\n질감" or first["target_value"] != first["actual_value"]:
        raise RuntimeError("Installed explanation split or rewrote an atomic tag")
    fallback = request_json(
        base_url,
        "/v1/recommendations/content",
        body={"catalog": catalog, "profile": {"taste_tags": ["OOV"]}, "include_explanations": True},
        timeout=30,
    )
    for item in fallback["items"]:
        if (
            item["explanation"]["score_evidence"]
            or item["explanation"]["basis"] != "deterministic_baseline"
            or item["explanation"]["fallback_reason"] != "no_supported_preferences"
        ):
            raise RuntimeError("Installed explanation mislabeled baseline/OOV as preference")
    schema = request_json(base_url, "/openapi.json")["components"]["schemas"]["ItemExplanation"]
    if schema["properties"]["score_evidence"]["items"]["discriminator"]["propertyName"] != "kind":
        raise RuntimeError("Installed OpenAPI omitted factual explanation discriminators")
