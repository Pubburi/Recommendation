"""Authored Backend input bridge expectations, independent of conversion helpers."""

import copy
import json
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from pubburi_recommendation.content_api import ContentRecommendationRequest
from pubburi_recommendation.content_model import FittedContentModel
from pubburi_recommendation.main import app

ROUTES = ("content", "exploration", "feedback")
CATALOG = [
    dict(
        product_id=1,
        available=True,
        sku_group="authored-a",
        category="맥주",
        price_krw=0,
        abv_percent=0,
        taste_tags=["단,맛\n질감"],
        aroma_tags=[],
    ),
    dict(
        product_id=2,
        available=True,
        sku_group="authored-b",
        category="맥주",
        price_krw=1000,
        abv_percent=10,
        taste_tags=["달콤"],
        aroma_tags=["곡물"],
    ),
    dict(
        product_id=3,
        available=True,
        sku_group="authored-c",
        category="과실주",
        price_krw=2000,
        abv_percent=20,
        taste_tags=None,
        aroma_tags=None,
    ),
    dict(
        product_id=4,
        available=True,
        sku_group="authored-d",
        category=None,
        price_krw=None,
        abv_percent=None,
        taste_tags=[],
        aroma_tags=[],
    ),
    dict(
        product_id=5,
        available=False,
        sku_group="authored-a",
        category="맥주",
        price_krw=0,
        abv_percent=0,
        taste_tags=["단,맛\n질감"],
        aroma_tags=[],
    ),
]


def snapshot():
    return {
        "surveyStatus": "COMPLETED",
        "softPreferences": {
            "categories": ["맥주"],
            "tasteTags": ["단,맛\n질감"],
            "aromaTags": None,
            "targetAbvPercent": 0,
        },
        "hardConstraints": {
            "minPriceKrw": 0,
            "maxPriceKrw": 1000,
            "minAbvPercent": 0,
            "maxAbvPercent": 10,
        },
    }


def unknown_snapshot(status="SKIPPED"):
    return {
        "surveyStatus": status,
        "softPreferences": dict(
            categories=None, tasteTags=None, aromaTags=None, targetAbvPercent=None
        ),
        "hardConstraints": dict(
            minPriceKrw=None, maxPriceKrw=None, minAbvPercent=None, maxAbvPercent=None
        ),
    }


def post(client, route, body, **kwargs):
    return client.post("/v1/recommendations/" + route, json=body, **kwargs)


@pytest.mark.parametrize("route", ROUTES)
def test_exact_legacy_request_equivalence_keeps_zero_literals_hard_intersection_and_one_fit(
    route, monkeypatch
):
    calls = []
    original = FittedContentModel.fit
    monkeypatch.setattr(
        FittedContentModel, "fit", lambda catalog: (calls.append(1), original(catalog))[1]
    )
    constraints = dict(
        categories=["맥주"], max_price_krw=500, max_abv_percent=5, exclude_product_ids=[2]
    )
    extra = {"feedback": {"not_interested_product_ids": [2]}} if route == "feedback" else {}
    enabled = dict(
        catalog=CATALOG,
        preferences=snapshot(),
        constraints=constraints,
        include_explanations=True,
        **extra,
    )
    legacy = dict(
        catalog=CATALOG,
        profile=dict(categories=["맥주"], taste_tags=["단,맛\n질감"], preferred_abv_percent=0),
        constraints=dict(
            categories=["맥주"],
            min_price_krw=0,
            max_price_krw=500,
            min_abv_percent=0,
            max_abv_percent=5,
            exclude_product_ids=[2],
        ),
        include_explanations=True,
        **extra,
    )
    with TestClient(app) as client:
        first = post(client, route, enabled)
        assert first.status_code == 200 and len(calls) == 1
        second = post(client, route, legacy)
    assert first.content == second.content and len(calls) == 2
    result = first.json()
    assert [p["product_id"] for p in result["items"]] == [1]
    assert result["eligible_count"] == 1 and result["fallback_reason"] is None
    evidence = result["items"][0]["explanation"]["score_evidence"]
    assert any(e["kind"] == "taste_match" and e["actual_value"] == "단,맛\n질감" for e in evidence)
    assert any(e["kind"] == "abv_comparison" and e["target_value"] == 0 for e in evidence)


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("status", ["NOT_STARTED", "SKIPPED", "COMPLETED"])
def test_unknown_survey_is_original_cold_fallback_without_invented_preferences(route, status):
    body = dict(catalog=CATALOG, preferences=unknown_snapshot(status))
    with TestClient(app) as client:
        actual = post(client, route, body)
        old = post(client, route, {"catalog": CATALOG})
    assert actual.status_code == 200 and actual.content == old.content
    assert actual.json()["fallback_reason"] == "no_supported_preferences"
    assert actual.json()["supported_profile_tokens"] == 0
    assert actual.json()["active_numeric_preferences"] == []
    assert [i["product_id"] for i in actual.json()["items"]] == (
        [] if route == "exploration" else [1, 2, 3, 4]
    )


def test_original_snapshot_unknown_and_known_empty_are_retained_without_mutation():
    unknown = unknown_snapshot("COMPLETED")
    known_empty = copy.deepcopy(unknown)
    for field in ("categories", "tasteTags", "aromaTags"):
        known_empty["softPreferences"][field] = []
    for supplied in (unknown, known_empty):
        before = copy.deepcopy(supplied)
        request = ContentRecommendationRequest.model_validate(
            dict(catalog=CATALOG, preferences=supplied)
        )
        assert request.preferences.model_dump() == before
        resolved = request.resolved()
        assert (
            resolved.profile.categories
            == resolved.profile.taste_tags
            == resolved.profile.aroma_tags
            == []
        )
        assert resolved.preferences is None and request.preferences.model_dump() == before
        assert supplied == before
        assert (
            request.model_dump()["profile"]
            == ContentRecommendationRequest(catalog=[]).profile.model_dump()
        )


@pytest.mark.parametrize("route", ["content", "feedback"])
@pytest.mark.parametrize("status", ["NOT_STARTED", "SKIPPED", "COMPLETED"])
def test_activity_categories_fill_only_missing_soft_categories(route, status, monkeypatch):
    calls = []
    original = FittedContentModel.fit
    monkeypatch.setattr(
        FittedContentModel, "fit", lambda catalog: (calls.append(1), original(catalog))[1]
    )
    preferences = unknown_snapshot(status)
    body = dict(
        catalog=CATALOG,
        preferences=preferences,
        activity_categories=dict(
            favorite_categories=["과실주"], highly_rated_categories=["과실주"]
        ),
        include_explanations=True,
    )
    request = ContentRecommendationRequest.model_validate(body)
    assert request.resolved().profile.categories == ["과실주"]
    assert request.preferences.model_dump() == preferences == unknown_snapshot(status)

    with TestClient(app) as client:
        actual = post(client, route, body)
        assert actual.status_code == 200 and len(calls) == 1
        direct = post(
            client,
            route,
            dict(catalog=CATALOG, profile={"categories": ["과실주"]}, include_explanations=True),
        )
        cold = post(
            client,
            route,
            dict(catalog=CATALOG, preferences=preferences, include_explanations=True),
        )
    assert actual.content == direct.content
    result = actual.json()
    assert "activity_categories" not in result
    assert result["fallback_reason"] is None and result["supported_profile_tokens"] == 1
    assert [item["product_id"] for item in result["items"]] == [3, 1, 2, 4]
    assert [item["product_id"] for item in cold.json()["items"]] == [1, 2, 3, 4]
    assert cold.json()["fallback_reason"] == "no_supported_preferences"
    category = result["items"][0]["explanation"]["score_evidence"]
    assert len(category) == 1 and category[0]["kind"] == "category_match"
    assert category[0]["actual_value"] == category[0]["target_value"] == "과실주"


def test_activity_categories_union_preserves_explicit_tags_zero_and_hard_exclusions():
    preferences = snapshot()
    preferences["softPreferences"].update(categories=None, aromaTags=[])
    body = dict(
        catalog=CATALOG,
        preferences=preferences,
        activity_categories=dict(favorite_categories=["과실주"], highly_rated_categories=["맥주"]),
        constraints=dict(max_price_krw=0, max_abv_percent=0),
        include_explanations=True,
    )
    with TestClient(app) as client:
        actual = post(client, "content", body)
        body["constraints"]["exclude_product_ids"] = [1]
        excluded = post(client, "content", body)
    assert actual.status_code == 200
    result = actual.json()
    assert result["supported_profile_tokens"] == 3
    assert result["eligible_count"] == 1
    assert [item["product_id"] for item in result["items"]] == [1]
    evidence = result["items"][0]["explanation"]["score_evidence"]
    assert {e["kind"]: e["target_value"] for e in evidence} == {
        "category_match": "맥주",
        "taste_match": "단,맛\n질감",
        "abv_comparison": 0,
    }
    assert excluded.status_code == 200 and excluded.json()["items"] == []
    assert excluded.json()["fallback_reason"] == "no_eligible_products"


@pytest.mark.parametrize(
    "activity, message",
    [
        (None, "activity_categories_require_two_lists"),
        ({"favorite_categories": []}, "Field required"),
        ({"favorite_categories": ["맥주"], "highly_rated_categories": None}, "valid list"),
        ({"favorite_categories": [], "highly_rated_categories": []}, "nonempty_union"),
        (
            {"favorite_categories": ["맥주", "맥주"], "highly_rated_categories": []},
            "must_be_unique",
        ),
        ({"favorite_categories": ["맥주"] * 9, "highly_rated_categories": []}, "at most 8"),
        ({"favorite_categories": [" 맥주 "], "highly_rated_categories": []}, "Input should be"),
        ({"favorite_categories": [True], "highly_rated_categories": []}, "Input should be"),
        ({"favorite_categories": ["사케"], "highly_rated_categories": []}, "available_catalog"),
        (
            {"favorite_categories": ["맥주"], "highly_rated_categories": [], "rating": "private"},
            "Extra inputs",
        ),
    ],
)
def test_invalid_activity_categories_fail_before_fit(activity, message, monkeypatch):
    monkeypatch.setattr(FittedContentModel, "fit", lambda *_: pytest.fail("invalid activity fit"))
    catalog = [
        *CATALOG,
        dict(product_id=6, sku_group="authored-f", available=False, category="사케"),
    ]
    with TestClient(app) as client:
        response = post(
            client,
            "content",
            dict(catalog=catalog, preferences=unknown_snapshot(), activity_categories=activity),
        )
    assert response.status_code == 422 and message in response.text
    assert "private" not in response.text and "authored-" not in response.text


@pytest.mark.parametrize("route", ["content", "feedback"])
@pytest.mark.parametrize("fault", ["omitted", "partial", "profile", "explicit", "empty"])
def test_activity_needs_complete_preferences_and_never_overwrites_explicit_categories(
    route, fault, monkeypatch
):
    monkeypatch.setattr(
        FittedContentModel, "fit", lambda *_: pytest.fail("conflicting activity fit")
    )
    preferences = unknown_snapshot("COMPLETED")
    body = dict(
        catalog=CATALOG,
        preferences=preferences,
        activity_categories=dict(favorite_categories=["맥주"], highly_rated_categories=[]),
    )
    if fault == "omitted":
        del body["preferences"]
    elif fault == "partial":
        del preferences["softPreferences"]["categories"]
    elif fault == "profile":
        body["profile"] = {}
    else:
        preferences["softPreferences"]["categories"] = ["맥주"] if fault == "explicit" else []
    with TestClient(app) as client:
        response = post(client, route, body)
    assert response.status_code == 422


def test_exploration_does_not_accept_activity_categories(monkeypatch):
    monkeypatch.setattr(
        FittedContentModel, "fit", lambda *_: pytest.fail("other route fit activity")
    )
    with TestClient(app) as client:
        response = post(
            client,
            "exploration",
            dict(
                catalog=CATALOG,
                preferences=unknown_snapshot(),
                activity_categories=dict(favorite_categories=["맥주"], highly_rated_categories=[]),
            ),
        )
    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["type"] == "extra_forbidden" and error["loc"] == ["body", "activity_categories"]


@pytest.mark.parametrize("route", ROUTES)
def test_soft_target_outside_hard_range_remains_soft_and_all_hard_directions_intersect(route):
    preferences = snapshot()
    preferences["softPreferences"] = dict(
        categories=["과실주"], tasteTags=None, aromaTags=None, targetAbvPercent=20
    )
    # Stored bounds are tighter below; request bounds are tighter above. Neither
    # soft category nor soft target may become an eligibility requirement.
    constraints = dict(min_price_krw=0, max_price_krw=500, min_abv_percent=0, max_abv_percent=5)
    old_constraints = dict(min_price_krw=0, max_price_krw=500, min_abv_percent=0, max_abv_percent=5)
    with TestClient(app) as client:
        actual = post(
            client, route, dict(catalog=CATALOG, preferences=preferences, constraints=constraints)
        )
        old = post(
            client,
            route,
            dict(
                catalog=CATALOG,
                profile=dict(categories=["과실주"], preferred_abv_percent=20),
                constraints=old_constraints,
            ),
        )
    assert actual.status_code == 200 and actual.content == old.content
    assert (
        [i["product_id"] for i in actual.json()["items"]] == [1]
        if route != "exploration"
        else actual.json()["items"] == []
    )
    assert actual.json()["eligible_count"] == 1


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("constraints", [dict(min_price_krw=1001), dict(min_abv_percent=11)])
def test_conflicting_hard_intersection_is_422_before_fit(route, constraints, monkeypatch):
    monkeypatch.setattr(
        FittedContentModel, "fit", lambda *_: pytest.fail("conflicting bounds reached fit")
    )
    with TestClient(app) as client:
        response = post(
            client, route, dict(catalog=CATALOG, preferences=snapshot(), constraints=constraints)
        )
    assert response.status_code == 422
    assert "preferences_and_request_hard_bounds_conflict" in response.text


@pytest.mark.parametrize("route", ROUTES)
def test_explicit_zero_hard_ceiling_and_negative_group_exclusion_never_relax(route):
    preferences = snapshot()
    preferences["hardConstraints"].update(maxPriceKrw=0, maxAbvPercent=0)
    extra = (
        {"feedback": {"not_interested_product_ids": [5]}}
        if route == "feedback"
        else {"constraints": {"exclude_product_ids": [1]}}
    )
    with TestClient(app) as client:
        actual = post(client, route, dict(catalog=CATALOG, preferences=preferences, **extra))
    assert actual.status_code == 200 and actual.json()["items"] == []
    assert actual.json()["eligible_count"] == 0
    assert actual.json()["fallback_reason"] == "no_eligible_products"


def test_feedback_positive_source_and_negative_priority_remain_existing_engine():
    preferences = unknown_snapshot("COMPLETED")
    preferences["hardConstraints"]["maxPriceKrw"] = 2000
    feedback = dict(positive_product_ids=[2], not_interested_product_ids=[1])
    with TestClient(app) as client:
        actual = post(
            client,
            "feedback",
            dict(
                catalog=CATALOG,
                preferences=preferences,
                feedback=feedback,
                include_explanations=True,
            ),
        )
        old = post(
            client,
            "feedback",
            dict(
                catalog=CATALOG,
                constraints={"max_price_krw": 2000},
                feedback=feedback,
                include_explanations=True,
            ),
        )
    assert actual.status_code == 200 and actual.content == old.content
    result = actual.json()
    assert [i["product_id"] for i in result["items"]] == [3]
    assert result["matches"] == [
        dict(product_id=3, source="positive_feedback", positive_product_id=2)
    ]
    assert result["excluded_not_interested_count"] == 2
    assert result["evaluated_positive_count"] == result["informative_positive_count"] == 1


def test_feedback_keeps_activity_and_positive_reference_evidence_separate():
    matching_candidate = dict(CATALOG[1], product_id=6, sku_group="authored-f")
    body = dict(
        catalog=[*CATALOG, matching_candidate],
        preferences=unknown_snapshot(),
        activity_categories=dict(favorite_categories=["과실주"], highly_rated_categories=[]),
        feedback=dict(positive_product_ids=[1, 2], not_interested_product_ids=[5]),
        include_explanations=True,
    )
    with TestClient(app) as client:
        actual = post(client, "feedback", body)
        excluded_activity = post(
            client,
            "feedback",
            dict(body, feedback=dict(not_interested_product_ids=[3, 5])),
        )
    assert actual.status_code == 200
    result = actual.json()
    assert result["ranking_mode"] == "positive_feedback"
    assert result["positive_references"][0]["state"] == "blocked"
    assert result["excluded_not_interested_count"] == 2
    assert result["evaluated_positive_count"] == result["informative_positive_count"] == 1
    assert result["matches"] == [
        dict(product_id=3, source="profile", positive_product_id=None),
        dict(product_id=6, source="positive_feedback", positive_product_id=2),
    ]
    assert [i["explanation"]["comparison"] for i in result["items"]] == [
        {"kind": "profile"},
        {"kind": "reference_product", "product_id": 2},
    ]
    assert excluded_activity.status_code == 200
    fallback = excluded_activity.json()
    assert fallback["ranking_mode"] == "profile_fallback"
    assert fallback["fallback_reason"] == "no_matching_features"
    assert [i["product_id"] for i in fallback["items"]] == [2, 4, 6]
    assert all(m["source"] == "baseline" for m in fallback["matches"])


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize(
    "fault",
    [
        "null",
        "incomplete",
        "profile",
        "unknown_status",
        "stale_skipped",
        "extra",
        "ascii_case",
        "unicode_loss",
        "unicode_trim",
        "duplicate",
    ],
)
def test_ambiguous_or_lossy_input_is_rejected_without_field_dropping_or_fit(
    route, fault, monkeypatch
):
    monkeypatch.setattr(
        FittedContentModel, "fit", lambda *_: pytest.fail("invalid preferences reached fit")
    )
    body = dict(catalog=CATALOG, preferences=snapshot())
    if fault == "null":
        body["preferences"] = None
    elif fault == "incomplete":
        body["preferences"]["softPreferences"].pop("aromaTags")
    elif fault == "profile":
        body["profile"] = {}
    elif fault == "unknown_status":
        body["preferences"]["surveyStatus"] = "unknown"
    elif fault == "stale_skipped":
        body["preferences"]["surveyStatus"] = "SKIPPED"
    elif fault == "extra":
        body["preferences"]["softPreferences"]["preferredVolumeMl"] = 330
    else:
        body["preferences"]["softPreferences"]["tasteTags"] = {
            "ascii_case": ["UPPER"],
            "unicode_loss": ["İ"],
            "unicode_trim": ["\u00a0달콤"],
            "duplicate": ["달콤", "달콤"],
        }[fault]
    with TestClient(app) as client:
        response = post(client, route, body)
    assert response.status_code == 422
    assert "authored-" not in response.text and "UPPER" not in response.text


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("field", ["targetAbvPercent", "minAbvPercent", "maxAbvPercent"])
@pytest.mark.parametrize(
    "number", ["0.000", "13.750", "0e9999999999999999999", "0e-9999999999999999999"]
)
def test_raw_decimal_scale_and_conversion_errors_are_422_before_fit(
    route, field, number, monkeypatch
):
    monkeypatch.setattr(
        FittedContentModel, "fit", lambda *_: pytest.fail("invalid raw precision reached fit")
    )
    preferences = unknown_snapshot("COMPLETED")
    group = "softPreferences" if field == "targetAbvPercent" else "hardConstraints"
    preferences[group][field] = "NUMBER_MARKER"
    raw = json.dumps(dict(catalog=CATALOG, preferences=preferences)).replace(
        '"NUMBER_MARKER"', number
    )
    with TestClient(app) as client:
        response = client.post(
            "/v1/recommendations/" + route,
            content=raw,
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 422 and number not in response.text


@pytest.mark.parametrize("route", ROUTES)
def test_legacy_precision_and_schema_remain_unchanged_and_raw_valid_zero_is_accepted(route):
    with TestClient(app) as client:
        old = post(
            client,
            route,
            dict(
                catalog=CATALOG,
                profile={"preferred_abv_percent": 13.755},
                constraints={"max_abv_percent": 13.755},
            ),
        )
        assert old.status_code == 200
        raw = json.dumps(dict(catalog=CATALOG, preferences=snapshot())).replace(
            '"targetAbvPercent": 0', '"targetAbvPercent": 0.00'
        )
        response = client.post(
            "/v1/recommendations/" + route,
            content=raw,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200
        schema = client.get("/openapi.json").json()
    op = schema["paths"]["/v1/recommendations/" + route]["post"]
    ref = op["requestBody"]["content"]["application/json"]["schema"]["$ref"].split("/")[-1]
    prop = schema["components"]["schemas"][ref]["properties"]["preferences"]
    assert prop["$ref"].endswith("/SearchPreferenceSnapshot") and "default" not in prop
    assert "preferences" not in schema["components"]["schemas"][ref].get("required", [])


@pytest.mark.parametrize("route", ROUTES)
def test_bounded_duplicate_and_malformed_raw_priority_is_preserved(route):
    raw = json.dumps(dict(catalog=CATALOG, preferences=snapshot()))
    duplicate = raw.replace(
        '"surveyStatus": "COMPLETED"', '"surveyStatus": "COMPLETED", "surveyStatus": "COMPLETED"'
    )
    with TestClient(app) as client:
        path = "/v1/recommendations/" + route
        assert (
            client.post(
                path,
                content=raw + " " * (524289 - len(raw)),
                headers={"Content-Type": "application/json"},
            ).status_code
            == 413
        )
        d = client.post(path, content=duplicate, headers={"Content-Type": "application/json"})
        assert d.status_code == 422 and d.json()["detail"][0]["type"] == "duplicate_json_key"
        malformed = client.post(
            path, content=duplicate + "!", headers={"Content-Type": "application/json"}
        )
        assert (
            malformed.status_code == 422 and malformed.json()["detail"][0]["type"] == "json_invalid"
        )


def test_preference_schema_startup_and_empty_requests_remain_model_independent():
    subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; from fastapi.testclient import TestClient; "
            "from pubburi_recommendation.main import app; c=TestClient(app); "
            "assert c.get('/health').status_code==200; "
            "assert c.get('/openapi.json').status_code==200; "
            "p={'surveyStatus':'SKIPPED','softPreferences':dict(categories=None,tasteTags=None,"
            "aromaTags=None,targetAbvPercent=None),"
            "'hardConstraints':dict(minPriceKrw=None,maxPriceKrw=None,"
            "minAbvPercent=None,maxAbvPercent=None)}; "
            "[c.post('/v1/recommendations/'+r,json={'catalog':[],"
            "'preferences':p}).raise_for_status() "
            "for r in ('content','exploration','feedback')]; "
            "assert not {'numpy','sklearn','pubburi_recommendation.content_model'} "
            "& set(sys.modules)",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("route", ROUTES)
def test_stored_lower_bounds_remain_stronger_than_request_lower_bounds(route):
    preferences = snapshot()
    preferences["hardConstraints"].update(minPriceKrw=500, minAbvPercent=5)
    with TestClient(app) as client:
        response = post(
            client,
            route,
            dict(
                catalog=CATALOG,
                preferences=preferences,
                constraints=dict(min_price_krw=0, min_abv_percent=0),
            ),
        )
    assert response.status_code == 200
    assert [i["product_id"] for i in response.json()["items"]] == [2]
    assert response.json()["eligible_count"] == 1


@pytest.mark.parametrize("route", ROUTES)
def test_oov_stored_soft_atom_remains_explicit_unknown_original_fallback(route):
    preferences = unknown_snapshot("COMPLETED")
    preferences["softPreferences"]["tasteTags"] = ["미등록 원자 태그"]
    with TestClient(app) as client:
        actual = post(client, route, dict(catalog=CATALOG, preferences=preferences))
        old = post(
            client, route, dict(catalog=CATALOG, profile={"taste_tags": ["미등록 원자 태그"]})
        )
    assert actual.status_code == 200 and actual.content == old.content
    assert actual.json()["supported_profile_tokens"] == 0
    assert actual.json()["unknown_profile_tokens"] == 1
    assert actual.json()["fallback_reason"] == "no_supported_preferences"
