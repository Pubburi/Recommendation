"""Authored source shapes exercise the real fit; they are not public/catalogue observations."""

import json
import math
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from pubburi_recommendation.catalog_audit import (
    AuditError,
    ReviewManifest,
    SourceManifest,
    audit,
    read_json,
)
from pubburi_recommendation.source_family_experiment import (
    FamilyExperiment,
    fit_representation,
    verify_receipt,
    write_report,
)
from pubburi_recommendation.wikidata_collect import collect

ROOT = Path(__file__).resolve().parents[1]
HASH = "a" * 64


def quantity(value, unit="Q2080811"):
    return {
        "rank": "normal",
        "mainsnak": {
            "snaktype": "value",
            "datavalue": {
                "value": {"amount": str(value), "unit": "http://www.wikidata.org/entity/" + unit}
            },
        },
    }


def identifier(qid):
    return {"mainsnak": {"datavalue": {"value": {"id": qid}}}}


def raw_fixture():
    entities = {}
    for qid, style, abv in (("Q1", "Q10", 5), ("Q2", "Q11", 15), ("Q3", "Q99", 25)):
        entities[qid] = {
            "type": "item",
            "id": qid,
            "lastrevid": 7,
            "labels": {"mul": {"value": "Authored family, not a real beverage"}},
            "claims": {
                "P31": [identifier(style)],
                "P176": [identifier("Q20")],
                "P2665": [quantity(abv)],
            },
        }
    entities["Q3"]["claims"]["P2234"] = [quantity(500, "Q2332346")]
    return {"success": 1, "entities": entities}


def review_fixture(input_hash=HASH):
    return {
        "input_sha256": input_hash,
        "catalog_mode": "demo",
        "records": {
            qid: {"kind": "product_family", "evidence_url": "https://example.org/authored"}
            for qid in ("Q1", "Q2", "Q3")
        },
    }


def spec_fixture(**changes):
    return {
        "schema_version": 1,
        "experiment_id": "authored-source-family-regression",
        "evidence_kind": "authored_regression_fixture",
        "data_kind": "reviewed_source_product_families",
        "input_sha256": HASH,
        "review_sha256": HASH,
        "manifest_sha256": HASH,
        "receipt_sha256": HASH,
        "family_groups": {"Q1": "family-a", "Q2": "family-b", "Q3": "family-c"},
        "fit_groups": ["family-a", "family-b"],
        "transform_groups": ["family-c"],
        "expected_facts": {
            "Q1": {
                "instance_of_ids": ["Q10"],
                "producer_ids": ["Q20"],
                "abv_percent": 5,
                "volume_ml": None,
            },
            "Q2": {
                "instance_of_ids": ["Q11"],
                "producer_ids": ["Q20"],
                "abv_percent": 15,
                "volume_ml": None,
            },
            "Q3": {
                "instance_of_ids": ["Q99"],
                "producer_ids": ["Q20"],
                "abv_percent": 25,
                "volume_ml": 500,
            },
        },
        **changes,
    }


def records_fixture(raw=None, review=None):
    _, records, _ = audit(
        raw or raw_fixture(),
        HASH,
        ReviewManifest.model_validate(review or review_fixture()),
    )
    return records


def test_actual_tfidf_and_numeric_fit_use_only_the_declared_training_families():
    report = fit_representation(
        FamilyExperiment.model_validate(spec_fixture()), records_fixture(), {}
    )
    params = report["fitted_parameters"]
    assert report["fit_records"] == 2 and report["transform_records"] == 1
    assert params["vocabulary"] == ["instance_of:Q10", "instance_of:Q11", "producer:Q20"]
    assert params["idf"] == pytest.approx([math.log(3 / 2) + 1, math.log(3 / 2) + 1, 1])
    assert params["numeric_fit"]["abv_percent"] == {
        "observed_training_values": 2,
        "minimum": 5,
        "maximum": 15,
        "active": True,
        "inactive_reason": None,
    }
    assert params["numeric_fit"]["volume_ml"]["observed_training_values"] == 0
    transformed = report["transformed"][0]
    assert transformed["unknown_tokens"] == ["instance_of:Q99"]
    assert transformed["supported_tokens"] == 1
    assert transformed["text_vector_norm"] == pytest.approx(1)
    assert transformed["numeric"]["abv_percent"] == {
        "observed": True,
        "scaled_value": 2.0,
        "outside_fit_range": True,
    }
    assert transformed["numeric"]["volume_ml"] == {
        "observed": True,
        "scaled_value": None,
        "outside_fit_range": False,
    }
    assert report["passed_contract"]
    assert report["fit_text_matrix"]["rank"] == 2
    assert report["ranking_metrics"]["status"] == "not_calculated"
    assert not report["svd"]["fitted"]


def test_held_out_facts_never_change_fitted_parameters_or_training_fingerprint():
    original = FamilyExperiment.model_validate(spec_fixture())
    old = fit_representation(original, records_fixture(), {})
    changed_spec = spec_fixture()
    changed_spec["expected_facts"]["Q3"]["instance_of_ids"] = ["Q100"]
    changed_spec["expected_facts"]["Q3"]["abv_percent"] = 100
    raw = raw_fixture()
    raw["entities"]["Q3"]["claims"]["P31"] = [identifier("Q100")]
    raw["entities"]["Q3"]["claims"]["P2665"] = [quantity(100)]
    new = fit_representation(
        FamilyExperiment.model_validate(changed_spec), records_fixture(raw), {}
    )
    assert old["fitted_parameters"] == new["fitted_parameters"]
    assert old["fit_fingerprint"] == new["fit_fingerprint"]
    assert old["transformed"] != new["transformed"]


def test_names_prices_ratings_and_unknown_values_do_not_become_training_features():
    raw = raw_fixture()
    for entity in raw["entities"].values():
        entity["labels"] = {"en": {"value": "Different authored name"}}
        entity["descriptions"] = {"en": {"value": "Unverified sweet aroma and popular rating"}}
        entity["claims"]["P2665"] = []
    spec = spec_fixture()
    for facts in spec["expected_facts"].values():
        facts["abv_percent"] = None
    report = fit_representation(FamilyExperiment.model_validate(spec), records_fixture(raw), {})
    assert (
        report["fitted_parameters"]["numeric_fit"]["abv_percent"]["inactive_reason"]
        == "all_unknown"
    )
    assert report["transformed"][0]["numeric"]["abv_percent"] == {
        "observed": False,
        "scaled_value": None,
        "outside_fit_range": False,
    }
    assert all("name" not in term for term in report["fitted_parameters"]["vocabulary"])


@pytest.mark.parametrize(
    "changes",
    [
        {"fit_groups": ["family-a", "family-a"]},
        {"fit_groups": ["family-a", "family-c"]},
        {"transform_groups": ["unknown"]},
        {"family_groups": {"Q1": "family-a", "Q2": "family-b"}},
        {"expected_facts": {}},
        {"family_groups": {"Q1": "family-a", "Q2": "family-b", "Q3": "family-a"}},
    ],
)
def test_missing_duplicate_or_cross_partition_families_are_rejected(changes):
    with pytest.raises(ValidationError):
        FamilyExperiment.model_validate(spec_fixture(**changes))


def test_brand_cannot_be_reclassified_by_the_experiment_and_manual_facts_are_independent():
    spec = FamilyExperiment.model_validate(spec_fixture())
    review = review_fixture()
    review["records"]["Q3"]["kind"] = "brand"
    with pytest.raises(AuditError, match="reviewed_named_product_families"):
        fit_representation(spec, records_fixture(review=review), {})
    changed = spec_fixture()
    changed["expected_facts"]["Q3"]["abv_percent"] = 10
    with pytest.raises(AuditError, match="manual_facts_conflict"):
        fit_representation(FamilyExperiment.model_validate(changed), records_fixture(), {})


def receipt_fixture():
    return {
        "schema_version": 1,
        "mode": "offline_replay",
        "accepted": True,
        "error_code": None,
        "http_status": None,
        "requested_ids": ["Q1", "Q2", "Q3"],
        "revisions": {"Q1": 7, "Q2": 7, "Q3": 7},
        "response_sha256": HASH,
        "manifest_sha256": HASH,
        "structured_data_license": "CC0-1.0",
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("accepted", False),
        ("response_sha256", "b" * 64),
        ("manifest_sha256", "b" * 64),
        ("revisions", {"Q1": 7}),
        ("requested_ids", ["Q1", "Q2", "Q2"]),
        ("error_code", "api_maxlag"),
        ("mode", "unverified"),
        ("http_status", 200),
        ("schema_version", True),
    ],
)
def test_failed_or_changed_acquisition_receipt_never_approves_fit(field, value):
    receipt = receipt_fixture()
    receipt[field] = value
    with pytest.raises(AuditError, match="accepted_matching_source_receipt_required"):
        verify_receipt(
            receipt, raw_fixture(), FamilyExperiment.model_validate(spec_fixture()), HASH
        )


def test_boolean_revision_and_api_error_cannot_be_reinterpreted_as_valid_collection():
    receipt = receipt_fixture()
    raw = raw_fixture()
    for entity in raw["entities"].values():
        entity["lastrevid"] = 1
    receipt["revisions"] = {qid: True for qid in raw["entities"]}
    with pytest.raises(AuditError, match="accepted_matching_source_receipt_required"):
        verify_receipt(receipt, raw, FamilyExperiment.model_validate(spec_fixture()), HASH)
    raw = raw_fixture()
    raw["error"] = {"code": "maxlag"}
    with pytest.raises(AuditError, match="api_maxlag"):
        verify_receipt(
            receipt_fixture(), raw, FamilyExperiment.model_validate(spec_fixture()), HASH
        )


def test_zero_constant_and_empty_text_are_distinct_from_unobserved_features():
    raw = raw_fixture()
    spec = spec_fixture()
    for qid, entity in raw["entities"].items():
        entity["claims"]["P31"] = []
        entity["claims"]["P176"] = []
        entity["claims"]["P2665"] = [quantity(0)] if qid != "Q3" else []
        spec["expected_facts"][qid].update(
            instance_of_ids=[], producer_ids=[], abv_percent=0 if qid != "Q3" else None
        )
    report = fit_representation(FamilyExperiment.model_validate(spec), records_fixture(raw), {})
    assert report["fitted_parameters"]["vocabulary"] == []
    assert report["fit_text_matrix"]["fit_performed"] is False
    assert report["fit_text_matrix"]["rank_upper_bound"] == 0
    assert report["fitted_parameters"]["numeric_fit"]["abv_percent"] == {
        "observed_training_values": 2,
        "minimum": 0,
        "maximum": 0,
        "active": False,
        "inactive_reason": "constant",
    }
    assert report["transformed"][0]["text_vector_norm"] == 0
    assert report["transformed"][0]["numeric"]["abv_percent"]["observed"] is False


def test_incomplete_or_racing_report_never_overwrites_a_model(tmp_path, monkeypatch):
    output = tmp_path / ".pubburi" / "model.json"
    output.parent.mkdir()

    def failed_dump(*args, **kwargs):
        args[1].write("partial")
        raise OSError("must-not-leak-local-detail")

    monkeypatch.setattr(json, "dump", failed_dump)
    with pytest.raises(OSError):
        write_report(output, {"parameters": "authored"})
    assert list(output.parent.iterdir()) == []
    monkeypatch.undo()
    output.write_text("preserve existing user model")
    with pytest.raises(FileExistsError):
        write_report(output, {"parameters": "authored"})
    assert output.read_text() == "preserve existing user model"
    assert list(output.parent.iterdir()) == [output]


def write_inputs(tmp_path):
    paths = {name: tmp_path / f"{name}.json" for name in ("input", "review", "receipt", "spec")}
    paths["manifest"] = ROOT / "sources/wikidata-structured.json"
    paths["input"].write_text(json.dumps(raw_fixture()))
    input_hash = read_json(paths["input"])[1]
    paths["review"].write_text(json.dumps(review_fixture(input_hash)))
    collection = tmp_path / ".pubburi" / "authored-collection"
    collect(
        SourceManifest.model_validate(read_json(paths["manifest"])[0]),
        ["Q1", "Q2", "Q3"],
        collection,
        paths["input"],
    )
    paths["receipt"] = collection / "receipt.json"
    spec = spec_fixture(
        **{
            f"{name}_sha256": read_json(paths[name])[1]
            for name in ("input", "review", "manifest", "receipt")
        }
    )
    paths["spec"].write_text(json.dumps(spec))
    return paths


def command(paths, output):
    args = [sys.executable, "-m", "pubburi_recommendation.source_family_experiment"]
    for name, path in paths.items():
        args += ["--" + name, str(path)]
    return [*args, "--output", str(output)]


def test_real_cli_fits_private_output_and_preserves_existing_report(tmp_path):
    paths = write_inputs(tmp_path)
    output = tmp_path / ".pubburi" / "fit.json"
    result = subprocess.run(command(paths, output), capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text())
    assert report["evidence_kind"] == "authored_regression_fixture" and report["passed_contract"]
    assert report["grain"] == "reviewed_source_product_family_not_sellable_sku"
    again = subprocess.run(command(paths, output), capture_output=True, text=True, check=False)
    assert again.returncode == 2 and "existing_model_report_must_be_preserved" in again.stderr
    assert json.loads(output.read_text()) == report


def test_real_cli_rejects_changed_inputs_without_raw_values_or_partial_model(tmp_path):
    paths = write_inputs(tmp_path)
    source = json.loads(paths["input"].read_text())
    source["private-source-string-must-not-leak"] = "unreviewed"
    paths["input"].write_text(json.dumps(source))
    output = tmp_path / ".pubburi" / "rejected.json"
    result = subprocess.run(command(paths, output), capture_output=True, text=True, check=False)
    assert result.returncode == 2 and "experiment_input_hash_mismatch" in result.stderr
    assert "private-source-string" not in result.stderr and "Traceback" not in result.stderr
    assert not output.exists()


def test_real_cli_checks_fit_rights_before_source_read_and_rejects_public_model_output(tmp_path):
    paths = write_inputs(tmp_path)
    manifest = json.loads(paths["manifest"].read_text())
    manifest["structured_feature_fit"] = False
    paths["manifest"] = tmp_path / "held-manifest.json"
    paths["manifest"].write_text(json.dumps(manifest))
    paths["input"] = tmp_path / "nonexistent-private-path"
    output = tmp_path / ".pubburi" / "rejected.json"
    result = subprocess.run(command(paths, output), capture_output=True, text=True, check=False)
    assert result.returncode == 2 and "source_structured_feature_fit_not_approved" in result.stderr
    assert "nonexistent-private-path" not in result.stderr and not output.exists()
    result = subprocess.run(
        command(paths, tmp_path / "public.json"), capture_output=True, text=True, check=False
    )
    assert (
        result.returncode == 2
        and "model_report_requires_private_pubburi_directory" in result.stderr
    )
