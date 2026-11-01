"""Self-authored package shapes and digits; never real products or GS1 assignment claims."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from pubburi_recommendation.catalog_audit import AuditError, SourceManifest, read_json
from pubburi_recommendation.collection_snapshot import verify_collection_snapshot
from pubburi_recommendation.package_identity_audit import (
    PackageReview,
    audit_packages,
    inspect_gtin,
)
from pubburi_recommendation.wikidata_collect import check_payload, collect

ROOT = Path(__file__).resolve().parents[1]
HASHES = {"input_sha256": "a" * 64, "receipt_sha256": "b" * 64}


def claim(value, datatype="string", **changes):
    return {
        "rank": "normal",
        "id": "Q1$authored",
        "mainsnak": {"snaktype": "value", "datavalue": {"type": datatype, "value": value}},
        **changes,
    }


def quantity(amount, unit):
    return claim(
        {"amount": str(amount), "unit": "http://www.wikidata.org/entity/" + unit}, "quantity"
    )


def package(qid="Q1", gtin="12345670", **claims):
    return {
        "id": qid,
        "type": "item",
        "lastrevid": 7,
        "labels": {"mul": {"value": "Authored fictional can"}},
        "claims": {
            "P3962": [claim(gtin)],
            "P31": [claim({"id": "Q1121690"}, "wikibase-entityid")],
            "P2665": [quantity(5, "Q2080811")],
            "P2234": [quantity("0.5", "Q11582")],
            **claims,
        },
    }


def payload(*entities):
    return {"success": 1, "entities": {row["id"]: row for row in entities}}


def inspect(source, review=None):
    records = check_payload(source, sorted(source["entities"]))
    return audit_packages(source, records, HASHES, "authored_regression_fixture", review)


@pytest.mark.parametrize("value", ["12345670", "012345678905", "1234567890128", "12345678901231"])
def test_gtin_supported_lengths_and_check_digit_do_not_certify_a_product(value):
    result = inspect_gtin(value)
    assert result["syntax_valid"] and result["check_digit_valid"]
    assert result["comparison_key_14"] == value.zfill(14)
    assert result["value"] == value
    assert result["assignment_or_product_authenticity_verified"] is False


@pytest.mark.parametrize(
    "value",
    [
        12345670,
        True,
        None,
        "１２３４５６７０",
        " 12345670",
        "+12345670",
        "1234567",
        "123456789",
        "12345670\n",
        "9" * 1000,
    ],
)
def test_gtin_invalid_syntax_is_not_silently_coerced_or_trimmed(value):
    result = inspect_gtin(value)
    assert not result["syntax_valid"] and result["check_digit_valid"] is None
    assert not result["structurally_usable"]


def test_bad_checksum_and_all_zero_are_distinct_and_leading_zeros_remain_strings():
    assert inspect_gtin("12345671")["check_digit_valid"] is False
    zero = inspect_gtin("00000000")
    assert zero["check_digit_valid"] is True and not zero["structurally_usable"]
    assert inspect_gtin("012345678905")["value"].startswith("0")


def test_same_item_package_signals_are_not_backend_mapping_or_model_approval():
    report, rows = inspect(payload(package()))
    row = rows[0]
    assert (
        report["checksum_valid_claims"] == 1 and report["package_field_combination_entities"] == 1
    )
    assert row["volume_ml"] == 500 and row["abv_percent"] == 5
    assert row["producer_ids"] == [] and row["package_count"] is None
    assert row["manual_review"] == "not_performed" and row["hold_reasons"] == []
    assert row["backend_product_id"] is None and not row["backend_mapping_approved"]
    assert not row["feature_fit_eligible"] and report["feature_fit_promotions"] == 0
    assert row["warnings"] == ["unreferenced_gtin_statement"]


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"P3962": [claim("12345671")]}, "single_unambiguous_gtin_required"),
        (
            {"P3962": [claim("12345670", qualifiers={"P585": []})]},
            "single_unambiguous_gtin_required",
        ),
        ({"P3962": [claim("12345670", rank="deprecated")]}, "single_unambiguous_gtin_required"),
        ({"P3962": [claim("12345670"), claim("012345678905")]}, "single_unambiguous_gtin_required"),
        ({"P2234": [quantity(500, "Q999")]}, "volume_unknown"),
        ({"P2234": [quantity(500, "Q2332346"), quantity(750, "Q2332346")]}, "volume_unknown"),
        ({"P2665": [quantity(5, "Q11229")]}, "abv_unknown"),
        (
            {"P31": [claim({"id": "Q15075508"}, "wikibase-entityid")]},
            "explicit_container_type_unknown",
        ),
        (
            {"P31": [claim({"id": "Q1121690"}, "wikibase-entityid", qualifiers={"P518": [{}]})]},
            "container_context_requires_review",
        ),
    ],
)
def test_variants_units_context_and_brand_never_become_confirmed_packages(changes, reason):
    _, rows = inspect(payload(package(**changes)))
    assert reason in rows[0]["hold_reasons"]
    assert rows[0]["feature_fit_eligible"] is False


def test_mixed_brand_container_grain_and_shared_identifier_are_independent_holds():
    first = package(
        P31=[
            claim({"id": "Q1121690"}, "wikibase-entityid"),
            claim({"id": "Q15075508"}, "wikibase-entityid"),
        ]
    )
    report, rows = inspect(payload(first, package("Q2", gtin="00000012345670")))
    assert report["shared_identifier_groups"] == 1
    assert "mixed_brand_and_container_types" in rows[0]["hold_reasons"]
    assert all("identifier_shared_across_source_items" in row["hold_reasons"] for row in rows)
    assert rows[1]["gtin_claims"][0]["value"] == "00000012345670"


def test_contextual_active_gtin_still_blocks_a_shared_identifier_on_the_other_item():
    source = payload(
        package(),
        package("Q2", P3962=[claim("00000012345670", qualifiers={"P518": [{}]})]),
    )
    report, rows = inspect(source)
    assert rows[1]["gtin_claims"][0]["structurally_usable"]
    assert not rows[1]["gtin_claims"][0]["usable_without_context"]
    assert report["shared_identifier_groups"] == 1
    assert all("identifier_shared_across_source_items" in row["hold_reasons"] for row in rows)
    with pytest.raises(AuditError, match="manual_candidate_conflicts_with_source_hold"):
        inspect(source, review("candidate_for_manual_mapping"))


def test_deprecated_identifier_does_not_create_an_active_collision():
    source = payload(
        package(),
        package("Q2", P3962=[claim("00000012345670", rank="deprecated")]),
    )
    report, rows = inspect(source, review("candidate_for_manual_mapping"))
    assert report["shared_identifier_groups"] == 0
    assert rows[0]["hold_reasons"] == []
    assert rows[1]["deprecated_gtin_statements"] == 1
    assert rows[0]["manual_review"] == "candidate_for_manual_mapping"
    assert not rows[0]["backend_mapping_approved"]


@pytest.mark.parametrize("prop,field", [("P2665", "abv_percent"), ("P2234", "volume_ml")])
@pytest.mark.parametrize("mutation", ["unsupported_rank", "nonquantity_value"])
def test_unsupported_quantity_statements_stay_unknown_and_cannot_support_manual_candidates(
    prop, field, mutation
):
    entity = package()
    statement = entity["claims"][prop][0]
    if mutation == "unsupported_rank":
        statement["rank"] = "unsupported"
    else:
        statement["mainsnak"]["datavalue"]["type"] = "string"
    source = payload(entity)
    report, rows = inspect(source)
    assert rows[0][field] is None
    assert f"{field}_statement_requires_review" in rows[0]["hold_reasons"]
    assert report["package_field_combination_entities"] == 0
    with pytest.raises(AuditError, match="manual_candidate_conflicts_with_source_hold"):
        inspect(source, review("candidate_for_manual_mapping"))


@pytest.mark.parametrize(
    "prop,field,unit",
    [
        ("P2234", "volume_ml", "Q11582"),
        ("P2234", "volume_ml", "https://example.invalid/Q11582"),
        ("P2665", "abv_percent", "Q2080811"),
        ("P2665", "abv_percent", "http://www.wikidata.org.evil.invalid/entity/Q2080811"),
    ],
)
def test_a_unit_id_suffix_without_the_inspected_wikidata_namespace_is_unknown(prop, field, unit):
    entity = package()
    entity["claims"][prop][0]["mainsnak"]["datavalue"]["value"]["unit"] = unit
    source = payload(entity)
    report, rows = inspect(source)
    assert rows[0][field] is None
    assert f"{field}_statement_requires_review" in rows[0]["hold_reasons"]
    assert report["package_field_combination_entities"] == 0
    with pytest.raises(AuditError, match="manual_candidate_conflicts_with_source_hold"):
        inspect(source, review("candidate_for_manual_mapping"))


def test_inspected_https_wikidata_units_preserve_the_same_explicit_measurements():
    entity = package()
    for prop in ("P2665", "P2234"):
        quantity_value = entity["claims"][prop][0]["mainsnak"]["datavalue"]["value"]
        quantity_value["unit"] = quantity_value["unit"].replace("http://", "https://")
    report, rows = inspect(payload(entity))
    assert rows[0]["volume_ml"] == 500 and rows[0]["abv_percent"] == 5
    assert rows[0]["hold_reasons"] == [] and report["package_field_combination_entities"] == 1


def review(decision="hold", **changes):
    return PackageReview.model_validate(
        {
            **HASHES,
            "records": {
                "Q1": {
                    "decision": decision,
                    "evidence_url": "https://www.wikidata.org/wiki/Q1?oldid=7",
                    "rationale": "Authored review, not a real item",
                }
            },
            **changes,
        }
    )


def test_manual_review_binds_source_receipt_revision_and_cannot_override_a_hold():
    with pytest.raises(AuditError, match="package_review_snapshot_hash_mismatch"):
        inspect(payload(package()), review(input_sha256="c" * 64))
    with pytest.raises(AuditError, match="package_review_snapshot_hash_mismatch"):
        inspect(payload(package()), review(receipt_sha256="c" * 64))
    wrong_revision = review().model_dump()
    wrong_revision["records"]["Q1"]["evidence_url"] += "0"
    with pytest.raises(AuditError, match="exact_source_revision_url"):
        inspect(payload(package()), PackageReview.model_validate(wrong_revision))
    with pytest.raises(AuditError, match="manual_candidate_conflicts_with_source_hold"):
        inspect(payload(package(P2234=[])), review("candidate_for_manual_mapping"))
    report, rows = inspect(payload(package()), review("candidate_for_manual_mapping"))
    assert report["manual_decisions"] == {"candidate_for_manual_mapping": 1}
    assert not rows[0]["backend_mapping_approved"] and not rows[0]["feature_fit_eligible"]


def inputs(tmp_path):
    source = tmp_path / "source.json"
    source.write_text(json.dumps(payload(package())))
    manifest_path = ROOT / "sources/wikidata-structured.json"
    collection = tmp_path / ".pubburi" / "collection"
    collect(SourceManifest.model_validate(read_json(manifest_path)[0]), ["Q1"], collection, source)
    return [
        sys.executable,
        "-m",
        "pubburi_recommendation.package_identity_audit",
        "--manifest",
        str(manifest_path),
        "--input",
        str(source),
        "--receipt",
        str(collection / "receipt.json"),
        "--evidence-kind",
        "authored_regression_fixture",
    ]


def test_real_cli_completes_private_audit_and_preserves_existing_outputs(tmp_path):
    command = inputs(tmp_path)
    output = tmp_path / ".pubburi" / "audit"
    first = subprocess.run(
        [*command, "--output-dir", str(output)], capture_output=True, text=True, check=False
    )
    assert first.returncode == 0, first.stderr
    assert json.loads((output / "receipt.json").read_text())["completed"] is True
    report = json.loads((output / "audit-report.json").read_text())
    assert (
        report["evidence_kind"] == "authored_regression_fixture"
        and report["checksum_valid_claims"] == 1
    )
    again = subprocess.run(
        [*command, "--output-dir", str(output)], capture_output=True, text=True, check=False
    )
    assert again.returncode == 2 and "FileExistsError" in again.stderr
    assert json.loads((output / "audit-report.json").read_text()) == report
    public = subprocess.run(
        [*command, "--output-dir", str(tmp_path / "public")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert public.returncode == 2 and "private_pubburi" in public.stderr


def test_changed_or_unapproved_source_fails_before_output_and_keeps_diagnostic_fixed(tmp_path):
    command = inputs(tmp_path)
    source = tmp_path / "source.json"
    source.write_text('{"private-original-must-not-leak":true}')
    result = subprocess.run(
        [*command, "--output-dir", str(tmp_path / ".pubburi" / "held")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2 and "accepted_matching_source_receipt_required" in result.stderr
    assert "private-original" not in result.stderr and "Traceback" not in result.stderr
    assert not (tmp_path / ".pubburi" / "held").exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"accepted": False},
        {"error_code": "source_delay"},
        {"mode": "live_get", "http_status": 200.0},
        {"mode": "offline_replay", "http_status": 200},
        {"requested_ids": ["Q1", "Q1"]},
        {"revisions": {"Q1": True}},
        {"revisions": {"Q1": 8}},
        {"manifest_sha256": "c" * 64},
    ],
)
def test_accepted_http_or_a_matching_raw_hash_cannot_replace_the_complete_receipt(
    tmp_path, changes
):
    command = inputs(tmp_path)
    source, raw_hash = read_json(Path(command[command.index("--input") + 1]))
    receipt, _ = read_json(Path(command[command.index("--receipt") + 1]))
    with pytest.raises(AuditError, match="accepted_matching_source_receipt_required"):
        verify_collection_snapshot(
            {**receipt, **changes}, source, raw_hash, receipt["manifest_sha256"]
        )
