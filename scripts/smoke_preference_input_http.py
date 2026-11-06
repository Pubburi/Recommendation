"""Installed Backend-shaped input on the three existing B1 routes; authored facts only."""

import copy
import json
import socket
from http.client import HTTPResponse
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener


def verify_preference_input_http(base_url, request_json):
    catalog = [
        dict(
            product_id=1,
            available=True,
            sku_group="authored-a",
            category="맥주",
            price_krw=0,
            abv_percent=0,
            taste_tags=["단,맛\n질감"],
        ),
        dict(
            product_id=2,
            available=True,
            sku_group="authored-b",
            category="과실주",
            price_krw=1000,
            abv_percent=10,
            taste_tags=None,
        ),
    ]
    preferences = {
        "surveyStatus": "COMPLETED",
        "softPreferences": dict(
            categories=["맥주"], tasteTags=["단,맛\n질감"], aromaTags=None, targetAbvPercent=0
        ),
        "hardConstraints": dict(minPriceKrw=0, maxPriceKrw=1000, minAbvPercent=0, maxAbvPercent=10),
    }
    skipped = {
        "surveyStatus": "SKIPPED",
        "softPreferences": dict(
            categories=None, tasteTags=None, aromaTags=None, targetAbvPercent=None
        ),
        "hardConstraints": dict(
            minPriceKrw=None, maxPriceKrw=None, minAbvPercent=None, maxAbvPercent=None
        ),
    }
    schema = request_json(base_url, "/openapi.json")

    def raw_post(path, raw):
        request = Request(
            base_url + path, data=raw.encode(), headers={"Content-Type": "application/json"}
        )
        try:
            response = build_opener(ProxyHandler({})).open(request, timeout=30)
        except HTTPError as error:
            response = error
        with response:
            return response.status, response.read()

    for route in ("content", "exploration", "feedback"):
        path = "/v1/recommendations/" + route
        ref = schema["paths"][path]["post"]["requestBody"]["content"]["application/json"]["schema"][
            "$ref"
        ].split("/")[-1]
        request_schema = schema["components"]["schemas"][ref]
        properties = request_schema["properties"]
        if "preferences" not in properties:
            raise RuntimeError("Installed B1 schema missed opt-in Backend preferences")
        supports_activity = route in ("content", "feedback")
        if ("activity_categories" in properties) != supports_activity:
            raise RuntimeError("Installed activity scope changed")
        if supports_activity and (
            properties["activity_categories"].get("$ref", "").split("/")[-1] != "ActivityCategories"
            or "activity_categories" in request_schema.get("required", [])
        ):
            raise RuntimeError("Installed activity schema must be omittable and non-null")
        if not supports_activity:
            rejected = request_json(
                base_url,
                path,
                body=dict(
                    catalog=catalog,
                    preferences=skipped,
                    activity_categories=dict(
                        favorite_categories=["과실주"], highly_rated_categories=[]
                    ),
                ),
                expected_status=422,
            )
            if rejected["detail"][0]["type"] != "extra_forbidden":
                raise RuntimeError("Installed exploration accepted activity input schema")
        extra = {"feedback": {"not_interested_product_ids": [2]}} if route == "feedback" else {}
        enabled = dict(
            catalog=catalog,
            preferences=preferences,
            constraints={"max_price_krw": 0},
            include_explanations=True,
            **extra,
        )
        legacy = dict(
            catalog=catalog,
            profile=dict(categories=["맥주"], taste_tags=["단,맛\n질감"], preferred_abv_percent=0),
            constraints=dict(
                min_price_krw=0, max_price_krw=0, min_abv_percent=0, max_abv_percent=10
            ),
            include_explanations=True,
            **extra,
        )
        status, actual = raw_post(path, json.dumps(enabled))
        old_status, old = raw_post(path, json.dumps(legacy))
        value = json.loads(actual)
        if (
            status != 200
            or old_status != 200
            or actual != old
            or [i["product_id"] for i in value["items"]] != [1]
        ):
            raise RuntimeError("Installed B1 changed explicit legacy equivalence/zero/hard bounds")
        cold = request_json(base_url, path, body=dict(catalog=catalog, preferences=skipped))
        if cold != request_json(base_url, path, body=dict(catalog=catalog)):
            raise RuntimeError("Installed B1 changed skipped cold fallback")
        for mutation in ("profile", "conflict", "literal"):
            bad = copy.deepcopy(enabled)
            if mutation == "profile":
                bad["profile"] = {}
            elif mutation == "conflict":
                bad["constraints"] = {"min_price_krw": 1001}
            else:
                bad["preferences"]["softPreferences"]["tasteTags"] = ["\u00a0원문"]
            request_json(base_url, path, body=bad, expected_status=422)
        for number in ("0.000", "13.750", "0e9999999999999999999", "0e-9999999999999999999"):
            raw = json.dumps(enabled).replace(
                '"targetAbvPercent": 0', '"targetAbvPercent": ' + number
            )
            status, response = raw_post(path, raw)
            if status != 422 or number.encode() in response:
                raise RuntimeError("Installed B1 lost raw Decimal precision/error sanitization")
        request_json(base_url, path, body={"padding": "x" * 524288}, expected_status=413)
        target = urlsplit(base_url)
        fragment = b'{"preferences":'
        with socket.create_connection((target.hostname, target.port), timeout=15) as connection:
            connection.sendall(
                (
                    f"POST {path} HTTP/1.1\r\nHost: {target.netloc}\r\n"
                    "Content-Type: application/json\r\n"
                    f"Content-Length: {len(fragment) + 1}\r\nConnection: close\r\n\r\n"
                ).encode()
                + fragment
            )
            response = HTTPResponse(connection)
            response.begin()
            if response.status != 408 or json.loads(response.read(1024)) != {
                "detail": "Catalog request body timed out"
            }:
                raise RuntimeError("Installed opt-in B1 violated the production body deadline")

    path = "/v1/recommendations/content"
    activity = dict(favorite_categories=["과실주"], highly_rated_categories=["과실주"])
    common = dict(catalog=catalog, include_explanations=True)
    enabled = dict(common, preferences=skipped, activity_categories=activity)
    status, actual = raw_post(path, json.dumps(enabled))
    direct_status, direct = raw_post(
        path, json.dumps(dict(common, profile={"categories": ["과실주"]}))
    )
    result = json.loads(actual)
    if (
        status != 200
        or direct_status != 200
        or actual != direct
        or [item["product_id"] for item in result["items"]] != [2, 1]
        or result["items"][0]["explanation"]["score_evidence"][0]["actual_value"] != "과실주"
        or result["supported_profile_tokens"] != 1
    ):
        raise RuntimeError("Installed activity ranking diverged from the existing B1 profile")
    bounded = request_json(
        base_url, path, body=dict(enabled, constraints={"max_price_krw": 0, "max_abv_percent": 0})
    )
    if [item["product_id"] for item in bounded["items"]] != [1] or bounded[
        "fallback_reason"
    ] != "no_matching_features":
        raise RuntimeError("Installed activity relaxed hard zero bounds or changed fallback")
    for bad in (
        dict(enabled, activity_categories=None),
        dict(enabled, preferences=preferences),
        dict(enabled, activity_categories=dict(activity, favorite_categories=["사케"])),
    ):
        request_json(base_url, path, body=bad, expected_status=422)

    path = "/v1/recommendations/feedback"
    active = request_json(
        base_url, path, body=dict(enabled, feedback={"not_interested_product_ids": [1]})
    )
    fallback = request_json(
        base_url, path, body=dict(enabled, feedback={"not_interested_product_ids": [2]})
    )
    if (
        active["matches"] != [dict(product_id=2, source="profile", positive_product_id=None)]
        or active["items"][0]["explanation"]["comparison"] != {"kind": "profile"}
        or fallback["matches"] != [dict(product_id=1, source="baseline", positive_product_id=None)]
        or fallback["fallback_reason"] != "no_matching_features"
    ):
        raise RuntimeError("Installed feedback lost activity provenance or negative exclusion")
