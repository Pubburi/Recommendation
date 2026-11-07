"""Authored source/business boundaries for family browse only, never actual SKU evidence."""

import copy
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError
from test_business_export import mapping_fixture, snapshot_fixture
from test_source_catalog import claim

from pubburi_recommendation.business_export import ReviewedMapping, build_exports, content_hash
from pubburi_recommendation.catalog_audit import AuditError, SourceManifest, read_json
from pubburi_recommendation.catalog_authority import load_export_catalog
from pubburi_recommendation.family_browse_catalog import (
    ALGORITHM,
    AT_ALGORITHM,
    SCOPE,
    FamilyBrowseCuration,
    load_family_browse_catalog,
)
from pubburi_recommendation.wikidata_collect import collect

ROOT = Path(__file__).resolve().parents[1]


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False))
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs(tmp_path, change=None):
    payload = {"success": 1, "entities": {}}
    for qid, amount in (("Q1", "0"), ("Q2", "10")):
        payload["entities"][qid] = {
            "id": qid,
            "type": "item",
            "lastrevid": 7,
            "labels": {"mul": {"value": "Authored family " + qid}},
            "claims": {
                "P31": [claim({"id": "Q10"}, "wikibase-entityid")],
                "P176": [claim({"id": "Q20"}, "wikibase-entityid")],
                "P2665": [
                    claim(
                        {"amount": amount, "unit": "http://www.wikidata.org/entity/Q2080811"},
                        "quantity",
                    )
                ],
            },
        }
    if change:
        change(payload)
    raw = write(tmp_path / "raw.json", payload)
    manifest = ROOT / "sources/wikidata-structured.json"
    collection = tmp_path / ".pubburi" / "collected"
    collect(SourceManifest.model_validate(read_json(manifest)[0]), ["Q1", "Q2"], collection, raw)
    receipt = collection / "receipt.json"
    review = write(
        tmp_path / "review.json",
        {
            "input_sha256": sha(raw),
            "catalog_mode": "demo",
            "records": {
                qid: {"kind": "product_family", "evidence_url": "https://example.org/authored"}
                for qid in ("Q1", "Q2")
            },
        },
    )
    curation = {
        "schema_version": 1,
        "algorithm": ALGORITHM,
        "evidence_kind": "authored_regression_fixture",
        "input_sha256": sha(raw),
        "receipt_sha256": sha(receipt),
        "manifest_sha256": sha(manifest),
        "review_sha256": sha(review),
        "catalog_version": "authored-family-browse-v1",
        "reviewed_at_utc": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
        "records": {
            qid: {
                "catalog_record_id": "authored-family-" + qid.lower(),
                "source_variant_group": "authored-group-" + qid.lower(),
                "identity_scope": SCOPE,
                "checked_facts": {
                    "source_revision": 7,
                    "label": "Authored family " + qid,
                    "label_language": "mul",
                    "instance_of_ids": ["Q10"],
                    "producer_ids": ["Q20"],
                    "abv_percent": abv,
                    "volume_ml": None,
                },
                "review_note": "Authored facts only, not physical package/SKU approval.",
            }
            for qid, abv in (("Q1", 0), ("Q2", 10))
        },
    }
    path = write(tmp_path / "curation.json", curation)
    return [manifest, raw, receipt, path, review], curation


def business(catalog):
    snapshot = snapshot_fixture()
    now = datetime.now(UTC)
    captured = (now - timedelta(seconds=1)).isoformat()
    snapshot["capture_started_at_utc"] = snapshot["capture_finished_at_utc"] = captured
    original = snapshot["records"][0]
    snapshot["records"] = []
    mappings = []
    for pid, source in enumerate(catalog["records"], start=37):
        row = copy.deepcopy(original)
        row["product"]["data"].update(
            id=pid, name=source["facts"]["label"], abv=source["facts"]["abv_percent"]
        )
        row["features"]["data"].update(productId=pid, volumeMl=None, tasteTags=None)
        snapshot["records"].append(row)
        mapping = mapping_fixture(catalog, snapshot)["records"][0]
        mapping.update(
            catalog_record_id=source["catalog_record_id"],
            backend_product_id=pid,
            source_variant_group=source["source_variant_group"],
            eligibility_scope=SCOPE,
            product_response_sha256=content_hash(row["product"]),
            features_response_sha256=content_hash(row["features"]),
        )
        mappings.append(mapping)
    mapping = mapping_fixture(catalog, snapshot)
    mapping["records"] = mappings
    mapping["reviewed_at_utc"] = now.isoformat()
    return snapshot, mapping, now


def export(catalog, snapshot, mapping, now):
    return build_exports(catalog, snapshot, "a" * 64, ReviewedMapping.model_validate(mapping), now)


def at_inputs(tmp_path):
    from test_at_source import EVIDENCE, raw_csv, receipt, review

    manifest = ROOT / "sources/at-traditional-liquor.json"
    raw = tmp_path / "at.csv"
    raw.write_bytes(raw_csv())
    captured = write(tmp_path / "at-receipt.json", receipt(raw.read_bytes()).model_dump())
    reviewed = review(raw.read_bytes()).model_dump()
    reviewed.update(manifest_sha256=sha(manifest), receipt_sha256=sha(captured))
    review_path = write(tmp_path / "at-review.json", reviewed)
    evidence = tmp_path / "at-provider.html"
    evidence.write_bytes(EVIDENCE)
    source_key = f"at:15048755:{sha(raw)}:row:1"
    curation = {
        "schema_version": 1,
        "algorithm": AT_ALGORITHM,
        "evidence_kind": "authored_regression_fixture",
        "input_sha256": sha(raw),
        "receipt_sha256": sha(captured),
        "manifest_sha256": sha(manifest),
        "review_sha256": sha(review_path),
        "catalog_version": "authored-at-browse-v1",
        "reviewed_at_utc": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
        "fact_evidence_files": [evidence.name],
        "records": {
            source_key: {
                "catalog_record_id": "at-browse-20260731-row1",
                "source_variant_group": "authored-at-browse-group",
                "identity_scope": SCOPE,
                "checked_facts": {
                    "source_row_number": 1,
                    "source_version": "20260731",
                    "label": "가상 원천 A",
                    "producer_name": "가상 양조장",
                    "category": "과실주",
                    "abv_percent": 0.0,
                    "volume_ml": None,
                },
                "review_note": "Explicit named source browse only; not a product_family/QID/SKU.",
            }
        },
    }
    path = write(tmp_path / "at-curation.json", curation)
    return (manifest, raw, captured, path, review_path), curation


def test_at_named_rows_reuse_browse_scope_without_fabricating_wikidata_or_business_identity(
    tmp_path,
):
    paths, _ = at_inputs(tmp_path)
    catalog, report = load_family_browse_catalog(*paths)
    assert report["selected_named_records"] == 1 and "selected_families" not in report
    row = catalog["records"][0]
    assert row["source"]["source_grain"] == "named_csv_product_record_not_verified_sku"
    assert row["source"]["input_sha256"] == sha(paths[1])
    assert row["facts"] == dict(
        label="가상 원천 A", category="과실주", abv_percent=0, volume_ml=None
    )
    assert all(value is None for value in row["unknown"].values())
    assert row["field_provenance"]["label"]["csv_column"] == "제품명"
    assert row["field_provenance"]["abv_percent"]["source_unit"] == "%"
    assert not (
        {"source_revision", "instance_of_ids", "producer_ids"} & row["reviewed_source_facts"].keys()
    )
    assert not row["physical_sku_or_service_catalog_approved"]
    loaded, _ = load_export_catalog(*paths[:4], family_review=paths[4])
    assert loaded == catalog
    with pytest.raises(AuditError, match="source_review_required"):
        load_export_catalog(*paths[:4])


def test_offline_reviewed_volume_does_not_enter_family_browse_as_unknown(tmp_path):
    paths, curation = at_inputs(tmp_path)
    reviewed = json.loads(paths[4].read_text())
    reviewed["records"][0].update(volume_ml=750, volume_unit="mL", volume_scope="single_container")
    write(paths[4], reviewed)
    curation["review_sha256"] = sha(paths[4])
    write(paths[3], curation)
    with pytest.raises(AuditError, match="at_browse_facts_conflict_with_reviewed_source"):
        load_family_browse_catalog(*paths)


@pytest.mark.parametrize(
    "field", ["input_sha256", "receipt_sha256", "review_sha256", "manifest_sha256"]
)
def test_at_browse_requires_exact_original_authority_hashes(tmp_path, field):
    paths, curation = at_inputs(tmp_path)
    curation[field] = "f" * 64
    write(paths[3], curation)
    with pytest.raises(AuditError, match="authority_hash_mismatch"):
        load_family_browse_catalog(*paths)


def test_at_browse_cannot_mix_audited_fixture_receipt_with_later_public_kind(tmp_path, monkeypatch):
    from pubburi_recommendation import at_source

    paths, curation = at_inputs(tmp_path)
    curation["evidence_kind"] = "reviewed_public_source"
    write(paths[3], curation)
    original = paths[2].read_bytes()
    (tmp_path / "receipt-before-replacement.json").write_bytes(original)
    audit = at_source.audit_at_source

    def audit_then_replace(*args):
        result = audit(*args)
        changed = json.loads(original)
        changed["evidence_kind"] = "operator_public_download_receipt"
        write(paths[2], changed)
        return result

    monkeypatch.setattr(at_source, "audit_at_source", audit_then_replace)
    with pytest.raises(AuditError, match="receipt_evidence_kind_mismatch"):
        load_family_browse_catalog(*paths)
    assert sha(paths[2]) != curation["receipt_sha256"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_row_number", 2),
        ("source_version", "20260101"),
        ("label", "다른 이름"),
        ("producer_name", "다른 양조장"),
        ("category", "증류주"),
        ("abv_percent", 10.0),
    ],
)
def test_at_browse_checked_facts_cannot_override_the_original_row_review(tmp_path, field, value):
    paths, curation = at_inputs(tmp_path)
    next(iter(curation["records"].values()))["checked_facts"][field] = value
    write(paths[3], curation)
    with pytest.raises(AuditError, match="facts_conflict"):
        load_family_browse_catalog(*paths)


@pytest.mark.parametrize(
    "mode", ["unreviewed", "wrong-key", "fixture-as-public", "future", "evidence", "path", "QID"]
)
def test_at_browse_never_promotes_other_rows_evidence_or_source_grain(tmp_path, mode):
    paths, curation = at_inputs(tmp_path)
    selected = next(iter(curation["records"].values()))
    if mode == "unreviewed":
        curation["records"] = {f"at:15048755:{sha(paths[1])}:row:2": selected}
    elif mode == "wrong-key":
        selected["catalog_record_id"] = "at-browse-20260731-row2"
    elif mode == "fixture-as-public":
        curation["evidence_kind"] = "reviewed_public_source"
    elif mode == "future":
        curation["reviewed_at_utc"] = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    elif mode == "evidence":
        (tmp_path / "at-provider.html").write_bytes(b"changed")
    elif mode == "path":
        curation["fact_evidence_files"] = ["../at-provider.html"]
    else:
        curation["records"] = {"Q1": selected}
    write(paths[3], curation)
    with pytest.raises((AuditError, ValidationError)):
        load_family_browse_catalog(*paths)


def test_at_browse_current_product_category_and_unknown_features_remain_hard_boundaries(tmp_path):
    paths, _ = at_inputs(tmp_path)
    catalog, _ = load_family_browse_catalog(*paths)
    snapshot, mapping, now = business(catalog)
    # Fresh hashes cannot approve an actual business category conflicting with the source fact.
    with pytest.raises(AuditError, match="source_and_business_category_conflict"):
        export(catalog, snapshot, mapping, now)
    snapshot["records"][0]["product"]["data"]["type"] = " 과실주 "
    mapping["records"][0]["product_response_sha256"] = content_hash(
        snapshot["records"][0]["product"]
    )
    with pytest.raises(AuditError, match="source_and_business_category_conflict"):
        export(catalog, snapshot, mapping, now)
    snapshot["records"][0]["product"]["data"]["type"] = "과실주"
    mapping["records"][0]["product_response_sha256"] = content_hash(
        snapshot["records"][0]["product"]
    )
    report, requests = export(catalog, snapshot, mapping, now)
    assert (
        report["data_scope"] == SCOPE
        and report["physical_sku_or_service_catalog_approved"] is False
    )
    row = requests["b1-demo-request.json"]["catalog"][0]
    assert row["product_id"] == 37 and row["abv_percent"] == 0 and row["volume_ml"] is None
    assert row["taste_tags"] is row["aroma_tags"] is None
    assert (
        report["mapping_provenance"][0]["category_and_price_authority"]
        == "reviewed_source_category_and_captured_business_demo_price"
    )
    snapshot["records"][0]["features"]["data"]["tasteTags"] = []
    mapping["records"][0]["features_response_sha256"] = content_hash(
        snapshot["records"][0]["features"]
    )
    with pytest.raises(AuditError, match="unknown_fields_conflict"):
        export(catalog, snapshot, mapping, now)


def test_actual_authority_preserves_facts_language_relations_unknowns_and_separate_scope(tmp_path):
    paths, _ = inputs(tmp_path)
    catalog, report = load_family_browse_catalog(*paths)
    assert catalog["data_kind"] == SCOPE and report["selected_families"] == 2
    assert [r["facts"]["abv_percent"] for r in catalog["records"]] == [0, 10]
    for row in catalog["records"]:
        assert row["facts"]["volume_ml"] is None
        assert all(value is None for value in row["unknown"].values())
        assert row["reviewed_source_facts"]["instance_of_ids"] == ["Q10"]
        assert row["field_provenance"]["label"]["property"] == "labels:mul"
        assert not row["physical_sku_or_service_catalog_approved"]
    loaded, _ = load_export_catalog(*paths[:4], family_review=paths[4])
    assert loaded == catalog
    with pytest.raises(AuditError, match="source_review_required"):
        load_export_catalog(*paths[:4])


@pytest.mark.parametrize(
    "field", ["input_sha256", "receipt_sha256", "review_sha256", "manifest_sha256"]
)
def test_each_authority_hash_is_required_before_curation(tmp_path, field):
    paths, curation = inputs(tmp_path)
    curation[field] = "f" * 64
    write(paths[3], curation)
    with pytest.raises(AuditError, match="authority_hash_mismatch"):
        load_family_browse_catalog(*paths)


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_revision", 8),
        ("label", "Different"),
        ("label_language", "en"),
        ("abv_percent", 5),
        ("instance_of_ids", ["Q99"]),
        ("producer_ids", ["Q99"]),
    ],
)
def test_checked_facts_cannot_replace_raw_facts(tmp_path, field, value):
    paths, curation = inputs(tmp_path)
    curation["records"]["Q1"]["checked_facts"][field] = value
    write(paths[3], curation)
    with pytest.raises(AuditError, match="facts_conflict"):
        load_family_browse_catalog(*paths)


@pytest.mark.parametrize("mode", ["unknown-abv", "unit", "relation-property", "qualified-relation"])
def test_accepted_receipt_cannot_approve_unknown_numeric_or_false_relations(tmp_path, mode):
    def change(payload):
        claims = payload["entities"]["Q1"]["claims"]
        if mode == "unknown-abv":
            del claims["P2665"]
        elif mode == "unit":
            claims["P2665"][0]["mainsnak"]["datavalue"]["value"]["unit"] = "Q2080811"
        elif mode == "relation-property":
            claims["P31"][0]["mainsnak"]["property"] = "P176"
        else:
            claims["P176"][0]["qualifiers"] = {"P1": []}

    paths, _ = inputs(tmp_path, change)
    with pytest.raises(AuditError, match="facts_conflict|facts_require_review"):
        load_family_browse_catalog(*paths)


def test_brand_review_future_timestamp_and_duplicate_groups_do_not_promote(tmp_path):
    paths, curation = inputs(tmp_path)
    review = json.loads(paths[4].read_text())
    review["records"]["Q1"]["kind"] = "brand"
    write(paths[4], review)
    curation["review_sha256"] = sha(paths[4])
    write(paths[3], curation)
    with pytest.raises(AuditError, match="reviewed_product_family"):
        load_family_browse_catalog(*paths)
    curation["reviewed_at_utc"] = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    write(paths[3], curation)
    with pytest.raises(AuditError, match="must_not_be_future"):
        load_family_browse_catalog(*paths)
    curation["records"]["Q2"]["source_variant_group"] = curation["records"]["Q1"][
        "source_variant_group"
    ]
    with pytest.raises(ValidationError):
        FamilyBrowseCuration.model_validate(curation)


def test_mapping_retains_null_volume_actual_zero_and_requires_owned_origin_and_full_mapping(
    tmp_path,
):
    paths, _ = inputs(tmp_path)
    catalog, _ = load_family_browse_catalog(*paths)
    snapshot, mapping, now = business(catalog)
    report, exports = export(catalog, snapshot, mapping, now)
    rows = exports["b1-demo-request.json"]["catalog"]
    assert [r["product_id"] for r in rows] == [37, 38]
    assert [r["abv_percent"] for r in rows] == [0, 10]
    assert all(r["volume_ml"] is r["taste_tags"] is r["aroma_tags"] is None for r in rows)
    assert report["data_scope"] == SCOPE and not report["physical_sku_or_service_catalog_approved"]
    with pytest.raises(AuditError, match="complete_explicit_mapping"):
        build_exports(catalog, snapshot, "a" * 64, None, now)
    mapping["records"].pop()
    with pytest.raises(AuditError, match="complete_explicit_mapping"):
        export(catalog, snapshot, mapping, now)
    catalog["evidence_kind"] = "reviewed_public_source"
    snapshot, mapping, now = business(catalog)
    snapshot.update(snapshot_origin="existing_local_catalog", capture_method="http_read")
    with pytest.raises(AuditError, match="owned_offline_demo_origin"):
        export(catalog, snapshot, mapping, now)
    snapshot["snapshot_origin"] = "owned_family_browse_demo"
    assert export(catalog, snapshot, mapping, now)[0]["exported_products"] == 2


@pytest.mark.parametrize(
    "field,value",
    [
        ("volumeMl", 500),
        ("tasteTags", []),
        ("aromaTags", ["inferred"]),
        ("description", "unreviewed prose"),
    ],
)
def test_family_scope_cannot_fill_unknown_fields_even_with_new_response_hash(
    tmp_path, field, value
):
    paths, _ = inputs(tmp_path)
    catalog, _ = load_family_browse_catalog(*paths)
    snapshot, mapping, now = business(catalog)
    snapshot["records"][0]["features"]["data"][field] = value
    mapping["records"][0]["features_response_sha256"] = content_hash(
        snapshot["records"][0]["features"]
    )
    with pytest.raises(AuditError, match="scope_or_unknown_fields_conflict"):
        export(catalog, snapshot, mapping, now)


def test_mixed_container_scope_and_changed_abv_cannot_pass_fresh_mapping(tmp_path):
    paths, _ = inputs(tmp_path)
    catalog, _ = load_family_browse_catalog(*paths)
    snapshot, mapping, now = business(catalog)
    catalog["records"][0]["identity_scope"] = "single_container_source_candidate"
    mapping["source_catalog_sha256"] = content_hash(catalog)
    with pytest.raises(AuditError, match="must_not_mix"):
        export(catalog, snapshot, mapping, now)
    catalog["records"][0]["identity_scope"] = SCOPE
    mapping["source_catalog_sha256"] = content_hash(catalog)
    snapshot["records"][0]["product"]["data"]["abv"] = 1
    mapping["records"][0]["product_response_sha256"] = content_hash(
        snapshot["records"][0]["product"]
    )
    with pytest.raises(AuditError, match="explicit_quantity_conflicts"):
        export(catalog, snapshot, mapping, now)


def test_real_cli_and_existing_output_preserve_private_receipt(tmp_path):
    paths, _ = inputs(tmp_path)
    command = [sys.executable, "-m", "pubburi_recommendation.family_browse_catalog"]
    for name, path in zip(
        ("manifest", "input", "receipt", "curation", "review"), paths, strict=True
    ):
        command += ["--" + name, str(path)]
    output = tmp_path / ".pubburi" / "family-catalog"
    result = subprocess.run([*command, "--output-dir", str(output)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads((output / "receipt.json").read_text())["completed"]
    before = (output / "source-catalog.json").read_bytes()
    again = subprocess.run([*command, "--output-dir", str(output)], capture_output=True, text=True)
    assert again.returncode == 2 and again.stderr == "family_browse_preparation_failed\n"
    assert (output / "source-catalog.json").read_bytes() == before


def test_family_demo_uses_existing_fit_and_independent_inspector_before_any_model_fit(
    tmp_path, monkeypatch
):
    from pubburi_recommendation.content_model import FittedContentModel
    from pubburi_recommendation.reviewed_catalog_fit import ReviewedFitSpec, run_reviewed_fit

    paths, _ = inputs(tmp_path)
    catalog, _ = load_family_browse_catalog(*paths)
    snapshot, mapping, now = business(catalog)
    mapped = ReviewedMapping.model_validate(mapping)
    report, exports = build_exports(catalog, snapshot, "a" * 64, mapped, now)
    keys = ["authored-family-q1", "authored-family-q2"]
    spec = {
        "schema_version": 1,
        "experiment_id": "authored-family-browse-fit",
        "evidence_kind": "authored_regression_fixture",
        "source_catalog_sha256": content_hash(catalog),
        "frozen_at_utc": (now - timedelta(seconds=1)).isoformat(),
        "expected_facts": {
            key: {
                "available": True,
                "category": "맥주",
                "price_krw": 1000,
                "abv_percent": abv,
                "volume_ml": None,
                "sku_group": "authored-group-q" + str(i),
                "taste_tags": None,
                "aroma_tags": None,
            }
            for i, key, abv in ((1, keys[0], 0), (2, keys[1], 10))
        },
        "scenarios": [
            {
                "case_id": "actual-zero-hard",
                "constraints": {"max_abv_percent": 0},
                "expected_eligible_keys": [keys[0]],
                "expected_item_count": 1,
                "expected_b1_fallback": "no_supported_preferences",
                "fact_basis": "Authored explicit zero differs from ten; volume is unknown.",
            }
        ],
    }
    fit = FittedContentModel.fit
    calls = []

    def counted(products):
        calls.append(products)
        return fit(products)

    monkeypatch.setattr(FittedContentModel, "fit", counted)
    result = run_reviewed_fit(
        ReviewedFitSpec.model_validate(spec), catalog, exports, mapped, report, now
    )
    assert len(calls) == 1 and result["passed"]
    assert result["fit_scope"] == "known_mapped_family_browse_demo"
    assert result["data_scope"] == SCOPE and not result["physical_sku_or_service_catalog_approved"]
    assert result["fit_summary"]["numeric_fit"]["abv_percent"]["active"]
    assert not result["fit_summary"]["numeric_fit"]["volume_ml"]["active"]
    assert result["ranking_metrics"]["status"] == "not_calculated"
    spec["expected_facts"][keys[0]]["volume_ml"] = 330
    with pytest.raises(AuditError, match="facts_conflict_before_fit"):
        run_reviewed_fit(
            ReviewedFitSpec.model_validate(spec), catalog, exports, mapped, report, now
        )
    assert len(calls) == 1
