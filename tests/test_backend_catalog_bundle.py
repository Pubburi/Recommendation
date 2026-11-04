"""Fresh checked artifacts become a pinned DEMO bundle; no new rights/fit authority."""

import copy
import hashlib
import json
import subprocess
import sys
from argparse import Namespace
from datetime import timedelta
from pathlib import Path

import pytest
import test_checked_export as fixtures
from pydantic import ValidationError
from test_checked_export import load

from pubburi_recommendation import backend_catalog_bundle as module
from pubburi_recommendation.backend_catalog_bundle import BackendCatalogBundle, build_bundle
from pubburi_recommendation.catalog_audit import AuditError


@pytest.fixture
def bundle(tmp_path):
    return fixtures.bundle.__wrapped__(tmp_path)


def arguments(bundle, output=None):
    paths = bundle["args"]
    return Namespace(
        export_dir=paths[0],
        manifest=paths[1],
        input=paths[2],
        source_receipt=paths[3],
        curation=paths[4],
        business_snapshot=paths[5],
        mapping=paths[6],
        family_review=bundle["family_review"],
        output_dir=paths[0].parent / "backend-bundle" if output is None else output,
    )


def test_bundle_preserves_exact_catalog_full_original_responses_and_unpromoted_scope(bundle):
    checked = load(bundle, now=bundle["now"])
    value = build_bundle(checked, bundle["args"][5])
    assert set(value) == {
        "schema_version",
        "algorithm",
        "catalog",
        "records",
        "checked_export",
        "service_catalog_approved",
        "model_loaded",
        "current_business_revalidation_required",
        "valid_until_utc",
    }
    assert value["catalog"] == checked.request.model_dump()["catalog"]
    assert value["checked_export"] == checked.metadata
    assert value["service_catalog_approved"] is value["model_loaded"] is False
    assert value["current_business_revalidation_required"] is True
    assert (
        value["valid_until_utc"]
        == (
            module.utc_time(bundle["snapshot"]["capture_finished_at_utc"]) + timedelta(seconds=300)
        ).isoformat()
    )
    original = bundle["snapshot"]["records"]
    for actual, expected, product in zip(value["records"], original, value["catalog"], strict=True):
        assert set(actual) == {
            "catalog_record_id",
            "backend_product_id",
            "sku_group",
            "price_kind",
            "eligibility_scope",
            "product",
            "features",
        }
        assert (
            actual["product"] == expected["product"] and actual["features"] == expected["features"]
        )
        assert actual["backend_product_id"] == product["product_id"]
        assert actual["sku_group"] == product["sku_group"]
        assert product["taste_tags"] is product["aroma_tags"] is product["volume_ml"] is None
    assert value["catalog"][0]["abv_percent"] == 0
    assert BackendCatalogBundle.model_validate(value).catalog[0].abv_percent == 0


@pytest.mark.parametrize(
    "fault",
    [
        "history",
        "flag",
        "loaded",
        "revalidation",
        "extra",
        "missing_hash",
        "expiry_equal",
        "expiry_extended",
        "reverse",
        "duplicate_key",
        "id",
        "group",
        "price",
        "abv",
        "volume",
        "tags",
        "scope",
    ],
)
def test_typed_consumer_contract_rejects_unbound_or_promoted_fields(bundle, fault):
    value = copy.deepcopy(build_bundle(load(bundle, now=bundle["now"]), bundle["args"][5]))
    if fault == "history":
        value["checked_export"]["mode"] = "historical_demo_replay"
    elif fault == "flag":
        value["service_catalog_approved"] = True
    elif fault == "loaded":
        value["checked_export"]["model_loaded"] = True
    elif fault == "revalidation":
        value["current_business_revalidation_required"] = False
    elif fault == "extra":
        value["unreviewed"] = True
    elif fault == "missing_hash":
        value["checked_export"]["artifact_sha256"].pop("receipt.json")
    elif fault == "expiry_equal":
        value["valid_until_utc"] = value["checked_export"]["checked_at_utc"]
    elif fault == "expiry_extended":
        value["valid_until_utc"] = (bundle["now"] + timedelta(seconds=301)).isoformat()
    elif fault == "reverse":
        value["records"].reverse()
    elif fault == "duplicate_key":
        value["records"][1]["catalog_record_id"] = value["records"][0]["catalog_record_id"]
    elif fault == "id":
        value["records"][0]["features"]["data"]["productId"] = 38
    elif fault == "group":
        value["records"][0]["sku_group"] = "unbound"
    elif fault in ("price", "abv"):
        value["records"][0]["product"]["data"][fault] += 1
    elif fault == "volume":
        value["records"][0]["features"]["data"]["volumeMl"] = 500
    elif fault == "tags":
        value["catalog"][0]["taste_tags"] = []
    else:
        value["records"][0]["eligibility_scope"] = "public_browse_row_exists"
    with pytest.raises(ValidationError):
        BackendCatalogBundle.model_validate(value)


@pytest.mark.parametrize(
    "flag", ["service_catalog_approved", "model_loaded", "current_business_revalidation_required"]
)
def test_flags_are_actual_booleans(bundle, flag):
    value = build_bundle(load(bundle, now=bundle["now"]), bundle["args"][5])
    value[flag] = int(value[flag])
    with pytest.raises(ValidationError):
        BackendCatalogBundle.model_validate(value)


@pytest.mark.parametrize(
    "scope", ["reviewed_mapped_business_demo_only", "reviewed_source_family_browse_demo_only"]
)
@pytest.mark.parametrize("evidence", ["authored_regression_fixture", "reviewed_public_source"])
@pytest.mark.parametrize(
    "origin",
    ["demo_fixture", "owned_demo_fixture", "existing_local_catalog", "owned_family_browse_demo"],
)
def test_scope_evidence_origin_matrix_matches_existing_export_contract(
    bundle, scope, evidence, origin
):
    # Structural DTO controls, not reapproval of the authored fixture as public source data.
    value = build_bundle(load(bundle, now=bundle["now"]), bundle["args"][5])
    value["checked_export"].update(data_scope=scope, evidence_kind=evidence, snapshot_origin=origin)
    if scope == "reviewed_mapped_business_demo_only":
        for product, row in zip(value["catalog"], value["records"], strict=True):
            product["volume_ml"] = row["features"]["data"]["volumeMl"] = 500
            row["eligibility_scope"] = "public_browse_row_exists"
    allowed = {
        ("reviewed_mapped_business_demo_only", "authored_regression_fixture", "demo_fixture"),
        ("reviewed_mapped_business_demo_only", "authored_regression_fixture", "owned_demo_fixture"),
        ("reviewed_mapped_business_demo_only", "reviewed_public_source", "existing_local_catalog"),
        ("reviewed_source_family_browse_demo_only", "authored_regression_fixture", "demo_fixture"),
        (
            "reviewed_source_family_browse_demo_only",
            "reviewed_public_source",
            "owned_family_browse_demo",
        ),
    }
    if (scope, evidence, origin) in allowed:
        BackendCatalogBundle.model_validate(value)
    else:
        with pytest.raises(ValidationError, match="bundle_scope_evidence_and_origin_conflict"):
            BackendCatalogBundle.model_validate(value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("volumeMl", 500),
        ("description", "unreviewed prose"),
        ("description", ""),
        ("tasteTags", ["unreviewed"]),
        ("tasteTags", []),
        ("aromaTags", ["unreviewed"]),
        ("aromaTags", []),
    ],
)
def test_family_raw_unknown_fields_cannot_be_filled_even_with_matching_catalog(
    bundle, field, value
):
    data = build_bundle(load(bundle, now=bundle["now"]), bundle["args"][5])
    data["records"][0]["features"]["data"][field] = value
    if field == "volumeMl":
        data["catalog"][0]["volume_ml"] = value
    with pytest.raises(ValidationError, match="bundle_scope_quantity_or_unknown_fields_conflict"):
        BackendCatalogBundle.model_validate(data)


@pytest.mark.parametrize("volume", [None, 500])
def test_container_requires_known_volume_but_preserves_unmodeled_original_fields(bundle, volume):
    data = build_bundle(load(bundle, now=bundle["now"]), bundle["args"][5])
    data["checked_export"]["data_scope"] = "reviewed_mapped_business_demo_only"
    for product, row in zip(data["catalog"], data["records"], strict=True):
        row["eligibility_scope"] = "public_browse_row_exists"
        product["volume_ml"] = row["features"]["data"]["volumeMl"] = volume
        row["features"]["data"].update(
            description="업무 원문 그대로", tasteTags=["원문,태그"], aromaTags=["원문\n향"]
        )
    if volume is None:
        with pytest.raises(
            ValidationError, match="bundle_scope_quantity_or_unknown_fields_conflict"
        ):
            BackendCatalogBundle.model_validate(data)
    else:
        result = BackendCatalogBundle.model_validate(data)
        assert result.records[0].features.data.description == "업무 원문 그대로"
        assert result.records[0].features.data.tasteTags == ["원문,태그"]
        assert result.records[0].features.data.aromaTags == ["원문\n향"]
        assert all(product.taste_tags is product.aroma_tags is None for product in result.catalog)


def test_publication_is_complete_only_after_recheck_and_sha_matches_whole_file(bundle, monkeypatch):
    monkeypatch.setattr(module, "utc_now", lambda: bundle["now"])
    args = arguments(bundle)
    before = {p: p.read_bytes() for p in bundle["export"].iterdir()}
    receipt = module.publish_bundle(args)
    assert receipt["completed"] is True and receipt["records"] == 2
    data = (args.output_dir / "catalog-bundle.json").read_bytes()
    assert receipt["bundle_sha256"] == hashlib.sha256(data).hexdigest()
    assert {p.name for p in args.output_dir.iterdir()} == {"catalog-bundle.json", "receipt.json"}
    assert json.loads(data)["checked_export"]["mode"] == "fresh_demo_snapshot"
    assert {p: p.read_bytes() for p in bundle["export"].iterdir()} == before
    assert (args.output_dir.stat().st_mode & 0o777) == 0o700
    assert ((args.output_dir / "catalog-bundle.json").stat().st_mode & 0o777) == 0o600


@pytest.mark.parametrize("fault", ["stale", "tampered", "partial", "preexisting", "nonprivate"])
def test_invalid_inputs_never_create_an_approved_bundle(bundle, monkeypatch, fault):
    monkeypatch.setattr(module, "utc_now", lambda: bundle["now"])
    args = arguments(bundle)
    if fault == "stale":
        monkeypatch.setattr(module, "utc_now", lambda: bundle["now"] + timedelta(seconds=301))
    elif fault == "tampered":
        p = bundle["export"] / "b1-demo-request.json"
        p.write_bytes(p.read_bytes() + b" ")
    elif fault == "partial":
        (bundle["export"] / "receipt.json").unlink()
    elif fault == "preexisting":
        args.output_dir.mkdir()
        (args.output_dir / "keep").write_text("preserve")
    else:
        args.output_dir = args.output_dir.parent.parent / "public"
    with pytest.raises(AuditError):
        module.publish_bundle(args)
    assert not (args.output_dir / "catalog-bundle.json").exists()
    if fault == "preexisting":
        assert (args.output_dir / "keep").read_text() == "preserve"
    else:
        assert not args.output_dir.exists()


@pytest.mark.parametrize("fault", ["input_changed", "expiry", "write_failed", "foreign_target"])
def test_failure_during_publication_stays_incomplete_and_does_not_replace_files(
    bundle, monkeypatch, fault
):
    monkeypatch.setattr(module, "utc_now", lambda: bundle["now"])
    args = arguments(bundle)
    original = module.write_receipt

    def receipt(folder, data):
        original(folder, data)
        if not data["completed"]:
            if fault == "input_changed":
                p = bundle["args"][5]
                p.write_bytes(p.read_bytes() + b" ")
            elif fault == "expiry":
                monkeypatch.setattr(
                    module, "utc_now", lambda: bundle["now"] + timedelta(seconds=301)
                )

    monkeypatch.setattr(module, "write_receipt", receipt)
    if fault in ("write_failed", "foreign_target"):

        def link(source, target):
            if fault == "foreign_target":
                Path(target).write_text("foreign preserved")
            raise OSError("controlled link failure")

        monkeypatch.setattr(module.os, "link", link)
    with pytest.raises((AuditError, OSError)):
        module.publish_bundle(args)
    assert json.loads((args.output_dir / "receipt.json").read_text())["completed"] is False
    target = args.output_dir / "catalog-bundle.json"
    if fault == "foreign_target":
        assert target.read_text() == "foreign preserved"
    else:
        assert not target.exists()


def test_producer_import_does_not_load_numerical_model():
    subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; import pubburi_recommendation.backend_catalog_bundle; "
            "assert not {'numpy','sklearn','pubburi_recommendation.content_model'} "
            "& set(sys.modules)",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(
    "fault",
    [
        "expiry_after_final_check",
        "final_receipt_failure",
        "expiry_during_link",
        "receipt_written_then_error",
    ],
)
def test_last_publication_boundary_never_marks_an_expired_or_failed_file_complete(
    bundle, monkeypatch, fault
):
    times = iter([bundle["now"], bundle["now"], bundle["now"] + timedelta(seconds=301)])
    monkeypatch.setattr(
        module,
        "utc_now",
        lambda: next(times) if fault == "expiry_after_final_check" else bundle["now"],
    )
    original = module.write_receipt
    original_link = module.os.link

    def link(source, target):
        original_link(source, target)
        if fault == "expiry_during_link":
            monkeypatch.setattr(module, "utc_now", lambda: bundle["now"] + timedelta(seconds=301))

    monkeypatch.setattr(module.os, "link", link)

    def write(folder, data):
        if data["completed"] and fault == "final_receipt_failure":
            raise OSError("controlled final receipt failure")
        result = original(folder, data)
        if data["completed"] and fault == "receipt_written_then_error":
            raise OSError("controlled error after completed receipt write")
        return result

    monkeypatch.setattr(module, "write_receipt", write)
    args = arguments(bundle)
    with pytest.raises((AuditError, OSError)):
        module.publish_bundle(args)
    assert json.loads((args.output_dir / "receipt.json").read_text())["completed"] is False
    assert not (args.output_dir / "catalog-bundle.json").exists()
