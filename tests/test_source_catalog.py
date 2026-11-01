"""Authored container facts exercise curation, not actual products or website rights."""

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from pubburi_recommendation.catalog_audit import AuditError, SourceManifest, read_json
from pubburi_recommendation.package_identity_audit import audit_packages
from pubburi_recommendation.source_catalog import CatalogCuration, curate_catalog, main
from pubburi_recommendation.wikidata_collect import check_payload, collect

ROOT = Path(__file__).resolve().parents[1]
HASHES = {
    name: letter * 64
    for name, letter in zip(
        ("input_sha256", "receipt_sha256", "manifest_sha256", "curation_sha256"),
        "abcd",
        strict=True,
    )
}


def claim(value, datatype):
    return {
        "rank": "normal",
        "mainsnak": {"snaktype": "value", "datavalue": {"type": datatype, "value": value}},
    }


def source_fixture(mixed=True):
    def quantity(amount, unit):
        return claim(
            {"amount": amount, "unit": "http://www.wikidata.org/entity/" + unit}, "quantity"
        )

    kinds = [claim({"id": "Q1121690"}, "wikibase-entityid")]
    if mixed:
        kinds.append(claim({"id": "Q15075508"}, "wikibase-entityid"))
    return {
        "success": 1,
        "entities": {
            "Q1": {
                "id": "Q1",
                "type": "item",
                "lastrevid": 7,
                "labels": {"mul": {"value": "Authored fictional package"}},
                "claims": {
                    "P31": kinds,
                    "P3962": [claim("12345670", "string")],
                    "P2234": [quantity("0.5", "Q11582")],
                    "P2665": [quantity("5", "Q2080811")],
                },
            }
        },
    }


def curation_fixture(**changes):
    return {
        "schema_version": 1,
        "algorithm": "source-container-curation-v1",
        "evidence_kind": "authored_regression_fixture",
        **HASHES_WITHOUT_CURATION,
        "catalog_version": "authored-catalog-v1",
        "reviewed_at_utc": "2026-11-01T00:00:00Z",
        "records": {
            "Q1": {
                "catalog_record_id": "authored-can-1",
                "source_variant_group": "authored-family",
                "identity_scope": "single_container_source_candidate",
                "checked_facts": {
                    "gtin": "12345670",
                    "container_class_id": "Q1121690",
                    "volume_ml": 500,
                    "abv_percent": 5,
                },
                "corroboration_url": "https://example.org/authored-facts-not-a-real-listing",
                "corroboration_publisher": "Authored fixture publisher",
                "review_note": "Fictional matching facts; not a real source review.",
                "mixed_type_interpretation": "Only this authored container; retain original types.",
            }
        },
        **changes,
    }


HASHES_WITHOUT_CURATION = {
    name: value for name, value in HASHES.items() if name != "curation_sha256"
}


def source_rows(payload):
    _, rows = audit_packages(
        payload,
        check_payload(payload, sorted(payload["entities"])),
        HASHES,
        "authored_regression_fixture",
    )
    return rows


def test_curated_source_fields_keep_cc0_provenance_original_conflict_and_no_business_promotion():
    original = source_rows(source_fixture())
    before = copy.deepcopy(original)
    catalog, report = curate_catalog(
        CatalogCuration.model_validate(curation_fixture()), original, HASHES
    )
    assert original == before
    row = catalog["records"][0]
    assert row["facts"]["volume_ml"] == 500 and row["facts"]["abv_percent"] == 5
    assert row["original_source_holds"] == ["mixed_brand_and_container_types"]
    assert "Q15075508" in row["original_instance_of_ids"]
    assert all(
        p["license"] == "CC0-1.0" and p["input_sha256"] == HASHES["input_sha256"]
        for p in row["field_provenance"].values()
    )
    assert row["field_provenance"]["label"]["property"] == "labels:mul"
    assert all(value is None for value in row["unreviewed_or_unknown"].values())
    assert row["backend_product_id"] is None and not row["service_feature_fit_eligible"]
    assert report["selected_source_candidates"] == report["source_variant_groups"] == 1
    assert report["b0_wire_exports"] == report["b1_wire_exports"] == 0


@pytest.mark.parametrize("field", ["gtin", "container_class_id", "volume_ml", "abv_percent"])
def test_manual_corroboration_cannot_replace_or_infer_allowed_source_facts(field):
    spec = curation_fixture()
    spec["records"]["Q1"]["checked_facts"][field] = {
        "gtin": "12345671",
        "container_class_id": "Q2",
        "volume_ml": 330,
        "abv_percent": 6,
    }[field]
    with pytest.raises(AuditError, match="manual_corroboration_conflicts"):
        curate_catalog(CatalogCuration.model_validate(spec), source_rows(source_fixture()), HASHES)


def test_mixed_type_scope_is_explicit_and_cannot_override_collision_or_unknown():
    spec = curation_fixture()
    spec["records"]["Q1"].pop("mixed_type_interpretation")
    with pytest.raises(AuditError, match="explicit_scoped_interpretation"):
        curate_catalog(CatalogCuration.model_validate(spec), source_rows(source_fixture()), HASHES)
    valid = CatalogCuration.model_validate(curation_fixture())
    for hold in (
        "identifier_shared_across_source_items",
        "volume_unknown",
        "abv_percent_statement_requires_review",
    ):
        rows = source_rows(source_fixture())
        rows[0]["hold_reasons"].append(hold)
        with pytest.raises(AuditError, match="cannot_override_unresolved"):
            curate_catalog(valid, rows, HASHES)


@pytest.mark.parametrize("key", ["input_sha256", "receipt_sha256", "manifest_sha256"])
def test_curation_cannot_be_reused_after_any_bound_source_file_changes(key):
    spec = curation_fixture(**{key: "f" * 64})
    with pytest.raises(AuditError, match="snapshot_hash_mismatch"):
        curate_catalog(CatalogCuration.model_validate(spec), source_rows(source_fixture()), HASHES)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.org",
        "https://www.wikidata.org/wiki/Q1",
        "https://www.wikidata.org./wiki/Q1",
        "https://user:secret@example.org",
    ],
)
def test_corroboration_is_separate_from_source_and_carries_no_embedded_credentials(url):
    spec = curation_fixture()
    spec["records"]["Q1"]["corroboration_url"] = url
    with pytest.raises(ValidationError):
        CatalogCuration.model_validate(spec)


def test_unknown_selection_duplicate_catalog_keys_and_business_fields_are_not_accepted():
    valid = curation_fixture()
    selected = valid["records"].pop("Q1")
    valid["records"]["Q2"] = selected
    with pytest.raises(AuditError, match="unknown_source_item"):
        curate_catalog(CatalogCuration.model_validate(valid), source_rows(source_fixture()), HASHES)
    duplicate = curation_fixture()
    duplicate["records"]["Q2"] = copy.deepcopy(duplicate["records"]["Q1"])
    with pytest.raises(ValidationError, match="catalog_record_ids_must_be_unique"):
        CatalogCuration.model_validate(duplicate)
    business_id = curation_fixture()
    business_id["records"]["Q1"]["backend_product_id"] = 1
    with pytest.raises(ValidationError):
        CatalogCuration.model_validate(business_id)


def cli_inputs(tmp_path, payload=None):
    raw = tmp_path / "source.json"
    collected = source_fixture() if payload is None else payload
    raw.write_text(json.dumps(collected))
    manifest = ROOT / "sources/wikidata-structured.json"
    collection = tmp_path / ".pubburi" / "collection"
    collect(
        SourceManifest.model_validate(read_json(manifest)[0]),
        sorted(collected["entities"]),
        collection,
        raw,
    )
    receipt = collection / "receipt.json"
    spec = curation_fixture(
        **{
            name: hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in {
                "input_sha256": raw,
                "receipt_sha256": receipt,
                "manifest_sha256": manifest,
            }.items()
        }
    )
    curation = tmp_path / "curation.json"
    curation.write_text(json.dumps(spec))
    command = [sys.executable, "-m", "pubburi_recommendation.source_catalog"]
    for name, path in {
        "manifest": manifest,
        "input": raw,
        "receipt": receipt,
        "curation": curation,
    }.items():
        command += ["--" + name, str(path)]
    return command, curation, raw


def test_real_cli_creates_only_private_source_catalog_with_complete_receipt_and_no_model_requests(
    tmp_path,
):
    command, _, _ = cli_inputs(tmp_path)
    output = tmp_path / ".pubburi" / "catalog"
    result = subprocess.run(
        [*command, "--output-dir", str(output)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert json.loads((output / "receipt.json").read_text())["completed"] is True
    assert {path.name for path in output.iterdir()} == {
        "source-catalog.json",
        "curation-report.json",
        "receipt.json",
    }
    original = (output / "source-catalog.json").read_bytes()
    again = subprocess.run(
        [*command, "--output-dir", str(output)], capture_output=True, text=True, check=False
    )
    assert again.returncode == 2 and "FileExistsError" in again.stderr
    assert (output / "source-catalog.json").read_bytes() == original


def test_cli_changed_source_and_public_path_fail_closed_without_raw_diagnostics(tmp_path):
    command, curation, raw = cli_inputs(tmp_path)
    public = subprocess.run(
        [*command, "--output-dir", str(tmp_path / "public")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert public.returncode == 2 and not (tmp_path / "public").exists()
    raw.write_text('{"private-payload-must-not-leak":true}')
    result = subprocess.run(
        [*command, "--output-dir", str(tmp_path / ".pubburi" / "held")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2 and "accepted_matching_source_receipt_required" in result.stderr
    assert "private-payload" not in result.stderr and "Traceback" not in result.stderr
    assert not (tmp_path / ".pubburi" / "held").exists()
    assert curation.exists()


def test_cli_cannot_curate_one_item_when_an_unselected_item_has_its_contextual_gtin(tmp_path):
    payload = source_fixture()
    other = copy.deepcopy(payload["entities"]["Q1"])
    other["id"] = "Q2"
    other["claims"]["P3962"][0]["qualifiers"] = {"P518": [{}]}
    payload["entities"]["Q2"] = other
    command, _, _ = cli_inputs(tmp_path, payload)
    output = tmp_path / ".pubburi" / "held-collision"
    result = subprocess.run(
        [*command, "--output-dir", str(output)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 2 and "cannot_override_unresolved_source_hold" in result.stderr
    assert not output.exists()


def test_partial_write_never_publishes_a_completed_catalog_receipt(tmp_path, monkeypatch, capsys):
    command, _, _ = cli_inputs(tmp_path)
    output = tmp_path / ".pubburi" / "partial"
    original_write = Path.write_text

    def fail_report(self, *args, **kwargs):
        if self.name == "curation-report.json":
            raise OSError("private-local-path-must-not-leak")
        return original_write(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_report)
    monkeypatch.setattr(sys, "argv", [command[2], *command[3:], "--output-dir", str(output)])
    assert main() == 2
    assert json.loads((output / "receipt.json").read_text())["completed"] is False
    assert (output / "source-catalog.json").exists()
    assert "private-local-path" not in capsys.readouterr().err


@pytest.mark.parametrize(
    "timestamp", ["2026-11-01T00:00:00", "2026-11-01T00:00:00+09:00", "2026-02-30T00:00:00Z"]
)
def test_review_time_is_a_valid_explicit_utc_timestamp(timestamp):
    with pytest.raises(ValidationError):
        CatalogCuration.model_validate(curation_fixture(reviewed_at_utc=timestamp))
