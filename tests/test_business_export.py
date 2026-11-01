"""Authored business/source contracts; no real source-to-service mapping or quality claims."""

import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from pubburi_recommendation import business_export
from pubburi_recommendation.baseline import RecommendationRequest
from pubburi_recommendation.business_export import (
    BusinessSnapshot,
    ReviewedMapping,
    build_exports,
    content_hash,
)
from pubburi_recommendation.catalog_audit import AuditError
from pubburi_recommendation.content_api import ContentRecommendationRequest

NOW = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
SNAPSHOT_HASH = "a" * 64


def catalog_fixture():
    return {
        "evidence_kind": "authored_regression_fixture",
        "records": [
            {
                "catalog_record_id": "fictional-can",
                "source_variant_group": "fictional-family",
                "facts": {"volume_ml": 500, "abv_percent": 5},
                "field_provenance": {
                    "volume_ml": {"license": "authored fixture", "property": "P2234"}
                },
            }
        ],
    }


def snapshot_fixture():
    return {
        "schema_version": 1,
        "snapshot_origin": "demo_fixture",
        "capture_method": "authored",
        "capture_started_at_utc": (NOW - timedelta(seconds=2)).isoformat(),
        "capture_finished_at_utc": (NOW - timedelta(seconds=1)).isoformat(),
        "records": [
            {
                "product": {
                    "data": {
                        "id": 37,
                        "name": "Fictional item, not matched by name",
                        "type": "맥주",
                        "price": 1000,
                        "img": "",
                        "abv": 5.0,
                        "orderCount": 0,
                    },
                    "message": "ok",
                    "error": None,
                },
                "features": {
                    "data": {
                        "productId": 37,
                        "volumeMl": 500,
                        "description": None,
                        "tasteTags": [],
                        "aromaTags": None,
                        "sourceName": "Authored fixture",
                        "sourceUrl": None,
                        "sourceNote": "Not a real beverage or license grant",
                    },
                    "message": "ok",
                    "error": None,
                },
            }
        ],
    }


def mapping_fixture(catalog=None, snapshot=None):
    catalog = catalog_fixture() if catalog is None else catalog
    snapshot = snapshot_fixture() if snapshot is None else snapshot
    row = snapshot["records"][0]
    return {
        "schema_version": 1,
        "algorithm": "reviewed-business-demo-export-v1",
        "source_catalog_sha256": content_hash(catalog),
        "business_snapshot_sha256": SNAPSHOT_HASH,
        "reviewed_at_utc": NOW.isoformat(),
        "records": [
            {
                "catalog_record_id": "fictional-can",
                "backend_product_id": 37,
                "product_response_sha256": content_hash(row["product"]),
                "features_response_sha256": content_hash(row["features"]),
                "source_variant_group": "fictional-family",
                "eligibility_scope": "public_browse_row_exists",
                "demo_browse_eligible": True,
                "price_kind": "demo_snapshot_krw",
                "identity_review_note": "Explicit fictional mapping.",
            }
        ],
    }


def run(catalog=None, snapshot=None, mapping=None, now=NOW):
    catalog = catalog_fixture() if catalog is None else catalog
    snapshot = snapshot_fixture() if snapshot is None else snapshot
    mapping = mapping_fixture(catalog, snapshot) if mapping is None else mapping
    return build_exports(
        catalog, snapshot, SNAPSHOT_HASH, ReviewedMapping.model_validate(mapping), now
    )


def test_explicit_mapping_exports_business_ids_price_scope_and_preserves_source_unknown():
    report, exports = run()
    b0 = RecommendationRequest.model_validate(exports["b0-demo-request.json"])
    b1 = ContentRecommendationRequest.model_validate(exports["b1-demo-request.json"])
    assert report["exported_products"] == 1 and report["fixture_contract_validation"]
    assert b0.catalog[0].product_id == b1.catalog[0].product_id == 37
    assert b1.catalog[0].sku_group == "fictional-family" and b1.catalog[0].volume_ml == 500
    assert b1.catalog[0].price_krw == 1000 and b1.catalog[0].taste_tags is None
    assert b1.catalog[0].aroma_tags is None and not report["snapshot_is_atomic_or_server_revision"]
    assert not report["service_training_or_quality_completed"]
    assert "sourceUrl" not in json.dumps(exports) and "description" not in json.dumps(exports)


def test_no_mapping_does_not_infer_ids_from_names_source_ids_or_order_and_reports_zero():
    data = snapshot_fixture()
    data["capture_started_at_utc"] = (NOW - timedelta(days=1)).isoformat()
    data["capture_finished_at_utc"] = (NOW - timedelta(days=1)).isoformat()
    report, exports = build_exports(catalog_fixture(), data, SNAPSHOT_HASH, None, NOW)
    assert report["exported_products"] == 0 and exports == {}


@pytest.mark.parametrize("value", [True, 37.0, 0, -1, "37"])
def test_business_ids_are_strict_positive_integers(value):
    data = snapshot_fixture()
    data["records"][0]["product"]["data"]["id"] = value
    with pytest.raises(ValidationError):
        BusinessSnapshot.model_validate(data)
    mapping = mapping_fixture()
    mapping["records"][0]["backend_product_id"] = value
    with pytest.raises(ValidationError):
        ReviewedMapping.model_validate(mapping)


@pytest.mark.parametrize(
    "mutation", ["different_feature_id", "duplicate", "origin", "span", "reversed", "future"]
)
def test_incoherent_or_future_snapshots_are_rejected(mutation):
    data = snapshot_fixture()
    if mutation == "different_feature_id":
        data["records"][0]["features"]["data"]["productId"] = 38
    elif mutation == "duplicate":
        data["records"] *= 2
    elif mutation == "origin":
        data["snapshot_origin"] = "existing_local_catalog"
    elif mutation == "span":
        data["capture_started_at_utc"] = (NOW - timedelta(seconds=62)).isoformat()
    elif mutation == "reversed":
        data["capture_started_at_utc"] = NOW.isoformat()
    else:
        data["capture_started_at_utc"] = data["capture_finished_at_utc"] = (
            NOW + timedelta(seconds=1)
        ).isoformat()
    with pytest.raises((ValidationError, AuditError)):
        run(snapshot=data)


def test_stale_capture_and_future_or_pre_capture_review_do_not_export():
    with pytest.raises(AuditError, match="stale"):
        run(now=NOW + timedelta(seconds=300))
    for reviewed in (NOW + timedelta(seconds=1), NOW - timedelta(seconds=2)):
        mapping = mapping_fixture()
        mapping["reviewed_at_utc"] = reviewed.isoformat()
        with pytest.raises(AuditError, match="review_must_follow"):
            run(mapping=mapping)


@pytest.mark.parametrize("field", ["source_catalog_sha256", "business_snapshot_sha256"])
def test_changed_source_and_business_files_invalidate_mapping(field):
    mapping = mapping_fixture()
    mapping[field] = "b" * 64
    with pytest.raises(AuditError, match="snapshot_hash_mismatch"):
        run(mapping=mapping)


def test_entire_original_response_hashes_are_checked_before_any_business_fields_are_used():
    mapping = mapping_fixture()
    data = snapshot_fixture()
    data["records"][0]["product"]["message"] = "changed response metadata"
    with pytest.raises(AuditError, match="whole_response_content_hash"):
        run(snapshot=data, mapping=mapping)
    data = snapshot_fixture()
    data["records"][0]["features"]["data"]["sourceNote"] = "changed"
    with pytest.raises(AuditError, match="whole_response_content_hash"):
        run(snapshot=data, mapping=mapping)


@pytest.mark.parametrize(
    "mutation", ["group", "id", "source_id", "unknown_volume", "volume", "abv"]
)
def test_manual_mapping_does_not_fill_unknown_or_override_conflicting_fields(mutation):
    snapshot = snapshot_fixture()
    mapping = mapping_fixture()
    if mutation == "group":
        mapping["records"][0]["source_variant_group"] = "other-family"
    elif mutation == "id":
        mapping["records"][0]["backend_product_id"] = 38
    elif mutation == "source_id":
        mapping["records"][0]["catalog_record_id"] = "other-source"
    else:
        if mutation == "unknown_volume":
            snapshot["records"][0]["features"]["data"]["volumeMl"] = None
        elif mutation == "volume":
            snapshot["records"][0]["features"]["data"]["volumeMl"] = 330
        else:
            snapshot["records"][0]["product"]["data"]["abv"] = 6
        mapping = mapping_fixture(snapshot=snapshot)
    with pytest.raises(AuditError):
        run(snapshot=snapshot, mapping=mapping)


def test_public_sources_and_fixtures_cannot_be_promoted_by_origin_labels():
    data = snapshot_fixture()
    data["snapshot_origin"] = "existing_local_catalog"
    data["capture_method"] = "http_read"
    with pytest.raises(AuditError, match="origins_must_not_mix"):
        run(snapshot=data)
    public = catalog_fixture()
    public["evidence_kind"] = "reviewed_public_source"
    with pytest.raises(AuditError, match="origins_must_not_mix"):
        run(catalog=public)
    data["snapshot_origin"] = "owned_demo_fixture"
    report, _ = run(snapshot=data)
    assert report["fixture_contract_validation"]


def test_mapping_is_one_to_one_and_availability_is_an_explicit_demo_choice():
    mapping = mapping_fixture()
    mapping["records"] *= 2
    with pytest.raises(ValidationError):
        ReviewedMapping.model_validate(mapping)
    mapping = mapping_fixture()
    mapping["records"][0]["demo_browse_eligible"] = False
    _, exports = run(mapping=mapping)
    assert exports["b1-demo-request.json"]["catalog"][0]["available"] is False


def test_real_cli_persists_complete_exports_and_hash_failures_do_not_leak_or_publish(
    tmp_path, monkeypatch, capsys
):
    catalog = catalog_fixture()
    snapshot = snapshot_fixture()
    captured = datetime.now(UTC).isoformat()
    snapshot["capture_started_at_utc"] = snapshot["capture_finished_at_utc"] = captured
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot))
    mapping = mapping_fixture(catalog, snapshot)
    mapping["business_snapshot_sha256"] = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
    mapping["reviewed_at_utc"] = datetime.now(UTC).isoformat()
    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text(json.dumps(mapping))
    monkeypatch.setattr(business_export, "load_source_catalog", lambda *_: (catalog, {}))
    output = tmp_path / ".pubburi" / "export"
    command = ["business_export"]
    for name, path in {
        "manifest": "unused",
        "input": "unused",
        "source-receipt": "unused",
        "curation": "unused",
        "business-snapshot": snapshot_path,
        "mapping": mapping_path,
        "output-dir": output,
    }.items():
        command += ["--" + name, str(path)]
    monkeypatch.setattr(sys, "argv", command)
    assert business_export.main() == 0
    assert json.loads((output / "receipt.json").read_text())["completed"] is True
    original = (output / "b1-demo-request.json").read_bytes()
    assert business_export.main() == 2
    assert (output / "b1-demo-request.json").read_bytes() == original
    snapshot["records"][0]["product"]["message"] = "private-payload-must-not-leak"
    snapshot_path.write_text(json.dumps(snapshot))
    command[-1] = str(tmp_path / ".pubburi" / "held")
    assert business_export.main() == 2
    captured_output = capsys.readouterr()
    assert "private-payload" not in captured_output.err and "Traceback" not in captured_output.err
    assert not (tmp_path / ".pubburi" / "held").exists()
