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
        if "preferences" not in schema["components"]["schemas"][ref]["properties"]:
            raise RuntimeError("Installed B1 schema missed opt-in Backend preferences")
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
        skipped = {
            "surveyStatus": "SKIPPED",
            "softPreferences": dict(
                categories=None, tasteTags=None, aromaTags=None, targetAbvPercent=None
            ),
            "hardConstraints": dict(
                minPriceKrw=None, maxPriceKrw=None, minAbvPercent=None, maxAbvPercent=None
            ),
        }
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
