"""Independent authored R06 query expectations, not product/user-quality labels."""

import asyncio
import copy
import json
import subprocess
import sys
from decimal import InvalidOperation

import pytest
from fastapi.testclient import TestClient

from pubburi_recommendation.main import app
from pubburi_recommendation.request_limits import CatalogRequestLimit

PATH = "/v1/recommendations/search-phrases"


def request(soft=None, hard=None, selected=None, status="COMPLETED", limit=5):
    return {
        "preferences": {
            "surveyStatus": status,
            "softPreferences": dict(
                categories=None, tasteTags=None, aromaTags=None, targetAbvPercent=None
            )
            | (soft or {}),
            "hardConstraints": dict(
                minPriceKrw=None, maxPriceKrw=None, minAbvPercent=None, maxAbvPercent=None
            )
            | (hard or {}),
        },
        "search_opt_in_fields": selected or [],
        "limit": limit,
    }


@pytest.fixture
def client():
    with TestClient(app) as value:
        yield value


def pairs(item):
    return [(row["name"], row["value"]) for row in item["query_pairs"]]


@pytest.mark.parametrize("status", ["NOT_STARTED", "SKIPPED", "COMPLETED"])
def test_unknown_survey_has_one_explicit_unfiltered_template_not_fake_results(client, status):
    value = client.post(PATH, json=request(status=status)).json()
    assert value["fallback_reason"] == "no_explicit_search_conditions"
    assert value["candidate_count"] == 1 and value["omitted_count"] == 0
    assert value["product_count"] is None and value["diagnostics"] == []
    assert value["items"][0]["label"] == "전체 상품 보기"
    assert value["items"][0]["template_id"] == "all_products"
    assert pairs(value["items"][0]) == []


def test_soft_preferences_never_automatically_become_search_hard_filters(client):
    body = request(
        {"categories": ["맥주"], "tasteTags": ["dry"], "targetAbvPercent": 80},
        {"maxAbvPercent": 10},
    )
    value = client.post(PATH, json=body).json()
    assert value["fallback_reason"] == "no_search_opt_in"
    assert pairs(value["items"][0]) == [("maxAbvPercent", "10")]
    assert value["items"][0]["label"] == "지정 조건으로 상품 보기"
    assert value["diagnostics"] == [
        {"field": field, "code": "soft_not_selected"}
        for field in ("categories", "tasteTags", "targetAbvPercent")
    ]
    assert body["preferences"]["softPreferences"]["targetAbvPercent"] == 80


def test_selected_facets_are_one_and_query_with_all_hard_bounds_and_raw_atoms(client):
    body = request(
        {
            "categories": ["탁주", "맥주"],
            "tasteTags": ["단,맛", "가벼운\n질감"],
            "aromaTags": ["배:향"],
            "targetAbvPercent": 5.25,
        },
        {"minPriceKrw": 0, "maxPriceKrw": 2147483647, "minAbvPercent": 0, "maxAbvPercent": 10},
        ["aromaTags", "targetAbvPercent", "categories", "tasteTags"],
    )
    response = client.post(PATH, json=body)
    assert response.status_code == 200
    value = response.json()
    assert value["fallback_reason"] is None and value["candidate_count"] == 2
    assert [row["conditions"]["type"] for row in value["items"]] == ["맥주", "탁주"]
    for category, row in zip(("맥주", "탁주"), value["items"], strict=True):
        assert pairs(row) == [
            ("type", category),
            ("minPriceKrw", "0"),
            ("maxPriceKrw", "2147483647"),
            ("minAbvPercent", "5.25"),
            ("maxAbvPercent", "5.25"),
            ("tasteTag", "가벼운\n질감"),
            ("tasteTag", "단,맛"),
            ("aromaTag", "배:향"),
        ]
        assert row["conditions"]["tasteTag"] == ["가벼운\n질감", "단,맛"]
        assert row["backend_unicode_revalidation_required"] is True
    assert value["product_count"] is None
    shuffled = copy.deepcopy(body)
    shuffled["search_opt_in_fields"].reverse()
    shuffled["preferences"]["softPreferences"]["categories"].reverse()
    shuffled["preferences"]["softPreferences"]["tasteTags"].reverse()
    assert client.post(PATH, json=shuffled).content == response.content


def test_eight_exact_types_have_no_or_query_and_limit_reports_real_omissions(client):
    response = client.post(
        PATH,
        json=request(
            {
                "categories": [
                    "탁주",
                    "약 · 청주",
                    "과실주",
                    "증류주",
                    "위스키",
                    "양주",
                    "맥주",
                    "사케",
                ]
            },
            {"minPriceKrw": 0},
            ["categories"],
        ),
    ).json()
    assert (response["candidate_count"], response["omitted_count"]) == (8, 3)
    assert [row["conditions"]["type"] for row in response["items"]] == [
        "과실주",
        "맥주",
        "사케",
        "약 · 청주",
        "양주",
    ]
    assert all(
        len(pairs(row)) == 2 and pairs(row)[1] == ("minPriceKrw", "0") for row in response["items"]
    )


@pytest.mark.parametrize("value,code", [(None, "selected_unknown"), ([], "selected_empty")])
def test_selected_unknown_or_known_empty_never_silently_becomes_unconstrained(client, value, code):
    result = client.post(
        PATH, json=request({"tasteTags": value}, {"maxPriceKrw": 0}, ["tasteTags"])
    ).json()
    assert result["items"] == [] and result["candidate_count"] == result["omitted_count"] == 0
    assert result["fallback_reason"] == (
        "selected_preferences_unknown" if value is None else "selected_preferences_empty"
    )
    assert result["diagnostics"] == [{"field": "tasteTags", "code": code}]
    assert result["product_count"] is None


def test_all_selected_missing_fields_are_reported_and_zero_is_a_real_exact_target(client):
    missing = client.post(
        PATH, json=request({"aromaTags": []}, selected=["aromaTags", "tasteTags"])
    ).json()
    assert missing["items"] == []
    assert missing["diagnostics"] == [
        {"field": "tasteTags", "code": "selected_unknown"},
        {"field": "aromaTags", "code": "selected_empty"},
    ]
    zero = client.post(
        PATH, json=request({"targetAbvPercent": 0}, {"maxAbvPercent": 10}, ["targetAbvPercent"])
    ).json()
    assert zero["fallback_reason"] is None
    assert pairs(zero["items"][0]) == [("minAbvPercent", "0"), ("maxAbvPercent", "0")]
    hard_zero = client.post(
        PATH,
        json=request(
            hard={"minPriceKrw": 0, "maxPriceKrw": 0, "minAbvPercent": 0, "maxAbvPercent": 0}
        ),
    ).json()
    assert pairs(hard_zero["items"][0]) == [
        ("minPriceKrw", "0"),
        ("maxPriceKrw", "0"),
        ("minAbvPercent", "0"),
        ("maxAbvPercent", "0"),
    ]


@pytest.mark.parametrize("target", [0, 80])
def test_opted_in_target_outside_hard_bounds_returns_empty_conflict_without_relaxation(
    client, target
):
    value = client.post(
        PATH,
        json=request(
            {"targetAbvPercent": target},
            {"minAbvPercent": 5, "maxAbvPercent": 10},
            ["targetAbvPercent"],
        ),
    ).json()
    assert value["items"] == [] and value["candidate_count"] == 0
    assert value["fallback_reason"] == "selected_target_outside_hard_bounds"


def test_preserved_unicode_can_require_backend_normalization_revalidation(client):
    values = ["k", "K", "<b>단,맛\n질감</b>", "😀" * 20]
    result = client.post(PATH, json=request({"tasteTags": values}, selected=["tasteTags"])).json()
    assert set(result["items"][0]["conditions"]["tasteTag"]) == set(values)
    assert result["items"][0]["backend_unicode_revalidation_required"]
    assert result["diagnostics"] == [
        {"field": "tasteTags", "code": "backend_unicode_revalidation_required"}
    ]
    assert result["items"][0]["label"] == "선택한 취향 조건으로 검색"
    assert (
        result["product_count"] is None
    )  # No claim the Java-normalized query or any product matched.


@pytest.mark.parametrize(
    "tags",
    [
        ["😀" * 21],
        ["dry", "dry"],
        ["dry", "DRY"],
        [" dry"],
        ["\n"],
        ["\u3000"],
        ["\ud800"],
        [1],
        [True],
    ],
)
def test_invalid_or_noncanonical_confirmed_tag_inputs_are_rejected_without_echo(client, tags):
    body = json.dumps(request({"tasteTags": tags}, selected=["tasteTags"]))
    response = client.post(PATH, content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert all(set(error) == {"type", "loc", "msg"} for error in response.json()["detail"])


@pytest.mark.parametrize(
    "raw",
    [
        "13.755",
        "13.750",
        "0.1000000000000000000000001",
        "1e-999",
        "-0.001",
        "true",
        '"5.25"',
        "101",
        "NaN",
    ],
)
def test_exact_raw_numeric_scale_and_type_are_validated_without_binary_float_rounding(client, raw):
    body = json.dumps(request(hard={"maxAbvPercent": 99})).replace(
        '"maxAbvPercent": 99', '"maxAbvPercent": ' + raw
    )
    response = client.post(PATH, content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 422


def test_exact_raw_two_place_decimal_is_serialized_as_ascii_without_rounding(client):
    body = json.dumps(request(hard={"maxAbvPercent": 99})).replace(
        '"maxAbvPercent": 99', '"maxAbvPercent": 13.70'
    )
    response = client.post(PATH, content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 200
    assert pairs(response.json()["items"][0]) == [("maxAbvPercent", "13.70")]


def test_signed_zero_is_real_zero_with_backend_compatible_query_not_negative_ascii(client):
    body = json.dumps(request(hard={"maxAbvPercent": 99})).replace(
        '"maxAbvPercent": 99', '"maxAbvPercent": -0.00'
    )
    response = client.post(PATH, content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 200
    assert pairs(response.json()["items"][0]) == [("maxAbvPercent", "0.00")]


@pytest.mark.parametrize("field", ["minAbvPercent", "maxAbvPercent", "targetAbvPercent"])
@pytest.mark.parametrize(
    "raw",
    [
        "0e9999999999999999999",
        "0e-9999999999999999999",
        "0.0e9999999999999999999",
        "0.0e-9999999999999999999",
    ],
)
def test_decimal_reparse_extreme_exponents_are_fixed_422_in_every_abv_field(client, field, raw):
    body = request()
    group = "softPreferences" if field == "targetAbvPercent" else "hardConstraints"
    body["preferences"][group][field] = 99
    encoded = json.dumps(body).replace('"' + field + '": 99', '"' + field + '": ' + raw)
    response = client.post(PATH, content=encoded, headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            {
                "type": "decimal_parsing",
                "loc": ["body"],
                "msg": "JSON decimal exponent exceeds the supported range",
            }
        ]
    }
    assert raw not in response.text


@pytest.mark.parametrize(
    "raw,expected", [("0", "0"), ("0.0", "0.0"), ("0e1000", "0"), ("13.70", "13.70")]
)
def test_decimal_reparse_exception_gate_keeps_valid_zero_and_exact_precision(client, raw, expected):
    encoded = json.dumps(request(hard={"maxAbvPercent": 99})).replace(
        '"maxAbvPercent": 99', '"maxAbvPercent": ' + raw
    )
    response = client.post(PATH, content=encoded, headers={"Content-Type": "application/json"})
    assert response.status_code == 200
    assert pairs(response.json()["items"][0]) == [("maxAbvPercent", expected)]


def test_decimal_reparse_does_not_mask_duplicate_or_malformed_json_priority(client):
    body = (
        json.dumps(request(hard={"maxAbvPercent": 99}))
        .replace('"maxAbvPercent": 99', '"maxAbvPercent": 0e9999999999999999999')
        .encode()
    )
    duplicate = body[:-1] + b',"limit":5}'
    for payload, expected in (
        (duplicate, "duplicate_json_key"),
        (duplicate + b"broken", "json_invalid"),
    ):
        response = client.post(PATH, content=payload, headers={"Content-Type": "application/json"})
        assert response.status_code == 422 and response.json()["detail"][0]["type"] == expected


def test_decimal_exception_catch_is_limited_to_raw_number_decoding(client, monkeypatch):
    import pubburi_recommendation.main as main

    def unrelated_failure(request):
        raise InvalidOperation("unrelated provider defect")

    monkeypatch.setattr(main, "recommend_search_phrases", unrelated_failure)
    with pytest.raises(InvalidOperation, match="unrelated provider defect"):
        client.post(PATH, json=request())


@pytest.mark.parametrize(
    "modify",
    [
        lambda b: b.update(limit=True),
        lambda b: b.update(limit=0),
        lambda b: b.update(limit=6),
        lambda b: b.update(search_opt_in_fields=None),
        lambda b: b.update(search_opt_in_fields=["tasteTags", "tasteTags"]),
        lambda b: b.update(search_opt_in_fields=["low_abv"]),
        lambda b: b.update(userId="secret"),
        lambda b: b["preferences"].pop("hardConstraints"),
        lambda b: b["preferences"]["softPreferences"].pop("tasteTags"),
        lambda b: b["preferences"]["softPreferences"].update(categories=["beer"]),
        lambda b: b["preferences"]["hardConstraints"].update(minPriceKrw=2, maxPriceKrw=1),
        lambda b: b["preferences"]["hardConstraints"].update(maxPriceKrw=0.0),
        lambda b: b["preferences"]["hardConstraints"].update(minAbvPercent=10, maxAbvPercent=0),
        lambda b: b["preferences"].update(
            surveyStatus="SKIPPED",
            softPreferences=dict(
                categories=[], tasteTags=None, aromaTags=None, targetAbvPercent=None
            ),
        ),
        lambda b: b["preferences"].update(
            surveyStatus="NOT_STARTED",
            hardConstraints=dict(
                minPriceKrw=0, maxPriceKrw=None, minAbvPercent=None, maxAbvPercent=None
            ),
        ),
    ],
)
def test_strict_complete_be_snapshot_shape_ranges_status_and_opt_in(client, modify):
    body = request()
    modify(body)
    assert client.post(PATH, json=body).status_code == 422


def test_boundary_json_duplicate_and_schema_are_existing_bounded_contracts(client):
    body = json.dumps(request()).encode()
    assert (
        client.post(
            PATH,
            content=body + b" " * (524288 - len(body)),
            headers={"Content-Type": "application/json"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            PATH,
            content=body + b" " * (524289 - len(body)),
            headers={"Content-Type": "application/json"},
        ).status_code
        == 413
    )
    duplicate = body[:-1] + b',"limit":5}'
    error = client.post(
        PATH, content=duplicate, headers={"Content-Type": "application/problem+json"}
    )
    assert error.status_code == 422 and error.json()["detail"][0]["type"] == "duplicate_json_key"
    malformed = client.post(
        PATH, content=duplicate + b"broken", headers={"Content-Type": "application/json"}
    )
    assert malformed.status_code == 422 and malformed.json()["detail"][0]["type"] == "json_invalid"
    schema = client.get("/openapi.json").json()["components"]["schemas"]
    assert schema["SearchPhraseRequest"]["properties"]["search_opt_in_fields"]["default"] == []
    assert "맥주 조건으로 검색" in schema["SearchPhraseItem"]["properties"]["label"]["enum"]
    assert "product_count" in schema["SearchPhraseResponse"]["properties"]


def test_new_route_body_deadline_and_disconnect_precede_any_provider_execution():
    async def run():
        invoked, messages = [], []

        async def downstream(scope, receive, send):
            invoked.append(True)

        async def receive():
            await asyncio.sleep(0.1)
            return {"type": "http.request", "body": b"{}", "more_body": False}

        async def send(message):
            messages.append(message)

        scope = {"type": "http", "method": "POST", "path": PATH, "headers": []}
        await CatalogRequestLimit(downstream, body_timeout_seconds=0.01)(scope, receive, send)
        assert not invoked and messages[0]["status"] == 408

        async def disconnect():
            return {"type": "http.disconnect"}

        messages.clear()
        await CatalogRequestLimit(downstream)(scope, disconnect, send)
        assert not invoked and messages == []

    asyncio.run(run())


def test_search_phrase_modes_and_openapi_do_not_retry_unavailable_model_runtime():
    code = f"""
import sys,importlib.abc
attempts=[]
class UnavailableModel(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname=='pubburi_recommendation.content_model':
            attempts.append(fullname)
            raise ImportError('authored unavailable dependency')
sys.meta_path.insert(0,UnavailableModel())
from fastapi.testclient import TestClient
from pubburi_recommendation.main import app
with TestClient(app) as client:
    assert len(attempts)==1
    assert client.get('/openapi.json').status_code == 200
    body = {request()!r}
    assert client.post({PATH!r},json=body).status_code == 200
    body['search_opt_in_fields']=['tasteTags']
    assert client.post({PATH!r},json=body).json()['items'] == []
    assert len(attempts)==1
assert not {{'numpy','sklearn','pubburi_recommendation.content_model'}} & set(sys.modules)
"""
    subprocess.run([sys.executable, "-I", "-c", code], check=True, capture_output=True, text=True)
