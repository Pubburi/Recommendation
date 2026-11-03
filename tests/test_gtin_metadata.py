"""Authored P3962 metadata checks do not certify a barcode assignment or real SKU."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from test_package_identity_audit import claim, inspect, package, payload
from test_source_catalog import HASHES, curation_fixture, source_fixture, source_rows

from pubburi_recommendation.catalog_audit import AuditError, SourceManifest, read_json
from pubburi_recommendation.source_catalog import CatalogCuration, curate_catalog
from pubburi_recommendation.wikidata_collect import collect


def canonical_gtin():
    row = claim("12345670")
    row["mainsnak"].update(property="P3962", datatype="external-id")
    return row


@pytest.mark.parametrize(
    "field,value",
    [
        ("property", "P31"),
        ("property", None),
        ("property", True),
        ("property", ""),
        ("datatype", "wikibase-item"),
        ("datatype", "string"),
        ("datatype", None),
        ("datatype", True),
    ],
)
def test_explicit_metadata_conflicts_hold_without_discarding_barcode_integrity(field, value):
    statement = canonical_gtin()
    statement["mainsnak"][field] = value
    report, rows = inspect(payload(package(P3962=[statement])))
    gtin = rows[0]["gtin_claims"][0]
    assert gtin["value"] == "12345670" and gtin["check_digit_valid"] is True
    assert gtin["comparison_key_14"] == "00000012345670" and gtin["structurally_usable"]
    assert gtin["issue"] == "gtin_statement_requires_review"
    assert not gtin["usable_without_context"]
    assert "single_unambiguous_gtin_required" in rows[0]["hold_reasons"]
    assert not rows[0]["package_field_combination_present"]
    assert report["checksum_valid_claims"] == 1 and report["feature_fit_promotions"] == 0


@pytest.mark.parametrize("omitted", [[], ["property"], ["datatype"], ["property", "datatype"]])
def test_explicit_external_identifier_and_legacy_omissions_keep_normal_evidence(omitted):
    statement = canonical_gtin()
    for field in omitted:
        del statement["mainsnak"][field]
    report, rows = inspect(payload(package(P3962=[statement])))
    assert rows[0]["gtin_claims"][0]["issue"] is None
    assert rows[0]["gtin_claims"][0]["usable_without_context"]
    assert rows[0]["hold_reasons"] == [] and report["package_field_combination_entities"] == 1
    assert not rows[0]["backend_mapping_approved"]


@pytest.mark.parametrize("field,value", [("property", "P31"), ("datatype", "wikibase-item")])
def test_curation_scope_cannot_override_conflicting_gtin_metadata(field, value):
    raw = source_fixture()
    snak = raw["entities"]["Q1"]["claims"]["P3962"][0]["mainsnak"]
    snak[field] = value
    rows = source_rows(raw)
    assert rows[0]["gtin_claims"][0]["issue"] == "gtin_statement_requires_review"
    with pytest.raises(AuditError, match="curation_cannot_override_unresolved_source_hold"):
        curate_catalog(CatalogCuration.model_validate(curation_fixture()), rows, HASHES)


@pytest.mark.parametrize("field,value", [("property", "P31"), ("datatype", "wikibase-item")])
def test_invalid_metadata_still_holds_all_items_sharing_the_structural_identifier(field, value):
    other = canonical_gtin()
    other["mainsnak"]["datavalue"]["value"] = "00000012345670"
    other["mainsnak"][field] = value
    source = payload(package(), package("Q2", P3962=[other]))
    report, rows = inspect(source)
    assert report["shared_identifier_groups"] == 1
    assert all("identifier_shared_across_source_items" in row["hold_reasons"] for row in rows)
    assert not rows[1]["gtin_claims"][0]["usable_without_context"]
    assert (
        rows[1]["gtin_claims"][0]["comparison_key_14"]
        == rows[0]["gtin_claims"][0]["comparison_key_14"]
    )
    assert inspect({**source, "entities": dict(reversed(list(source["entities"].items())))}) == (
        report,
        rows,
    )


@pytest.mark.parametrize("field,value", [("property", "P31"), ("datatype", "wikibase-item")])
def test_bad_active_neighbor_is_not_hidden_by_a_valid_statement_with_the_same_digits(field, value):
    good = canonical_gtin()
    bad = copy.deepcopy(good)
    bad["mainsnak"][field] = value
    report, rows = inspect(payload(package(P3962=[good, bad])))
    assert report["checksum_valid_claims"] == 2
    assert "single_unambiguous_gtin_required" in rows[0]["hold_reasons"]
    assert not rows[0]["package_field_combination_present"]


@pytest.mark.parametrize("field,value", [("property", "P31"), ("datatype", "wikibase-item")])
def test_deprecated_conflicting_metadata_does_not_create_an_active_shared_identifier(field, value):
    other = canonical_gtin()
    other["mainsnak"][field] = value
    other["rank"] = "deprecated"
    report, rows = inspect(payload(package(), package("Q2", P3962=[other])))
    assert report["shared_identifier_groups"] == 0
    assert rows[0]["hold_reasons"] == [] and rows[1]["deprecated_gtin_statements"] == 1


@pytest.mark.parametrize("field,value", [("property", "P31"), ("datatype", "wikibase-item")])
def test_real_offline_receipt_and_curation_cli_reject_matching_hash_but_wrong_gtin_metadata(
    tmp_path, field, value
):
    root = Path(__file__).resolve().parents[1]
    manifest_path = root / "sources/wikidata-structured.json"
    manifest = SourceManifest.model_validate(read_json(manifest_path)[0])
    data = source_fixture()
    data["entities"]["Q1"]["claims"]["P3962"][0]["mainsnak"][field] = value
    source = tmp_path / "source.json"
    source.write_text(json.dumps(data))
    collected = tmp_path / ".pubburi" / "collected"
    receipt = collect(manifest, ["Q1"], collected, source)
    assert receipt["accepted"] is True
    curation = curation_fixture()
    curation.update(
        input_sha256=read_json(source)[1],
        receipt_sha256=read_json(collected / "receipt.json")[1],
        manifest_sha256=read_json(manifest_path)[1],
    )
    curation_path = tmp_path / "curation.json"
    curation_path.write_text(json.dumps(curation))
    destination = tmp_path / ".pubburi" / "must-not-curate"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pubburi_recommendation.source_catalog",
            "--manifest",
            str(manifest_path),
            "--input",
            str(source),
            "--receipt",
            str(collected / "receipt.json"),
            "--curation",
            str(curation_path),
            "--output-dir",
            str(destination),
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 2 and not destination.exists()
    assert (
        result.stderr.strip()
        == "Source catalog curation failed: curation_cannot_override_unresolved_source_hold"
    )
