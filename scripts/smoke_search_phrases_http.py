"""Runtime-only R06 literal query contract; no product catalog or external calls."""

import copy
import json
import socket
from http.client import HTTPResponse
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

PATH = "/v1/recommendations/search-phrases"


def verify_search_phrases_http(base_url, request_json):
    schema = request_json(base_url, "/openapi.json")
    if not set(schema["paths"][PATH]["post"]["responses"]) >= {"200", "408", "413", "422"}:
        raise RuntimeError("Installed R06 schema missed bounded HTTP responses")
    body = {
        "preferences": {
            "surveyStatus": "COMPLETED",
            "softPreferences": {
                "categories": ["탁주", "맥주"],
                "tasteTags": ["단,맛\n질감"],
                "aromaTags": None,
                "targetAbvPercent": 0,
            },
            "hardConstraints": {
                "minPriceKrw": 0,
                "maxPriceKrw": 0,
                "minAbvPercent": 0,
                "maxAbvPercent": 10,
            },
        },
        "search_opt_in_fields": ["categories", "tasteTags", "targetAbvPercent"],
    }
    value = request_json(base_url, PATH, body=body)
    if value["product_count"] is not None or (value["candidate_count"], value["omitted_count"]) != (
        2,
        0,
    ):
        raise RuntimeError("Installed R06 invented product counts or dropped a type branch")
    for category, item in zip(("맥주", "탁주"), value["items"], strict=True):
        pairs = [(pair["name"], pair["value"]) for pair in item["query_pairs"]]
        if (
            pairs
            != [
                ("type", category),
                ("minPriceKrw", "0"),
                ("maxPriceKrw", "0"),
                ("minAbvPercent", "0"),
                ("maxAbvPercent", "0"),
                ("tasteTag", "단,맛\n질감"),
            ]
            or not item["backend_unicode_revalidation_required"]
        ):
            raise RuntimeError("Installed R06 changed explicit AND bounds, zero or literal atoms")
    passive = copy.deepcopy(body)
    passive["search_opt_in_fields"] = []
    result = request_json(base_url, PATH, body=passive)
    if result["items"][0]["query_pairs"] != [
        {"name": "minPriceKrw", "value": "0"},
        {"name": "maxPriceKrw", "value": "0"},
        {"name": "minAbvPercent", "value": "0"},
        {"name": "maxAbvPercent", "value": "10"},
    ]:
        raise RuntimeError("Installed R06 automatically promoted a soft preference")
    conflict = copy.deepcopy(body)
    conflict["preferences"]["softPreferences"]["targetAbvPercent"] = 80
    result = request_json(base_url, PATH, body=conflict)
    if result["items"] or result["fallback_reason"] != "selected_target_outside_hard_bounds":
        raise RuntimeError("Installed R06 relaxed an explicitly selected target conflict")
    for empty, fallback in (
        (None, "selected_preferences_unknown"),
        ([], "selected_preferences_empty"),
    ):
        unavailable = copy.deepcopy(body)
        unavailable["preferences"]["softPreferences"]["tasteTags"] = empty
        result = request_json(base_url, PATH, body=unavailable)
        if result["items"] or result["fallback_reason"] != fallback:
            raise RuntimeError("Installed R06 hid a selected unknown/empty facet")
    raw = json.dumps(body).replace('"maxAbvPercent": 10', '"maxAbvPercent": 13.750')
    req = Request(base_url + PATH, data=raw.encode(), headers={"Content-Type": "application/json"})
    try:
        response = build_opener(ProxyHandler({})).open(req, timeout=1)
    except HTTPError as error:
        response = error
    with response:
        if response.status != 422:
            raise RuntimeError("Installed R06 rounded raw BigDecimal scale")
    request_json(base_url, PATH, body={"padding": "x" * 524288}, expected_status=413)
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
            raise RuntimeError("Installed R06 violated its production partial-body deadline")
