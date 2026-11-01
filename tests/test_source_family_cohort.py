"""Authored independent authorities exercise a source-family, not service-SKU, cohort."""

import copy
import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from test_source_family_experiment import raw_fixture, spec_fixture

from pubburi_recommendation import source_family_cohort
from pubburi_recommendation.catalog_audit import AuditError, SourceManifest, read_json
from pubburi_recommendation.source_family_cohort import (
    CohortExperiment,
    checked_relation_ids,
    load_cohort,
    run_cohort,
)
from pubburi_recommendation.wikidata_collect import collect

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relation(qid):
    return {
        "rank": "normal",
        "mainsnak": {
            "snaktype": "value",
            "datavalue": {
                "type": "wikibase-entityid",
                "value": {"id": qid, "entity-type": "item", "numeric-id": int(qid[1:])},
            },
        },
    }


def inputs(tmp_path):
    manifest = SourceManifest.model_validate(
        read_json(ROOT / "sources/wikidata-structured.json")[0]
    )
    raw = raw_fixture()
    for qid, style in (("Q1", "Q10"), ("Q2", "Q11"), ("Q3", "Q11")):
        raw["entities"][qid]["claims"]["P31"] = [relation(style)]
        raw["entities"][qid]["claims"]["P176"] = [relation("Q99" if qid == "Q3" else "Q20")]
    snapshots, bindings = {}, []
    for name, ids in (("train", ["Q1", "Q2"]), ("holdout", ["Q3"])):
        source = tmp_path / (name + ".json")
        source.write_text(
            json.dumps({"success": 1, "entities": {qid: raw["entities"][qid] for qid in ids}})
        )
        output = tmp_path / ".pubburi" / name
        collect(manifest, ids, output, source)
        review = tmp_path / (name + "-review.json")
        review.write_text(
            json.dumps(
                {
                    "input_sha256": sha(source),
                    "catalog_mode": "demo",
                    "records": {
                        qid: {
                            "kind": "product_family",
                            "evidence_url": "https://example.org/authored",
                        }
                        for qid in ids
                    },
                }
            )
        )
        snapshots[name] = (source, output / "receipt.json", review)
        bindings.append(
            {
                "snapshot_id": name,
                "input_sha256": sha(source),
                "receipt_sha256": sha(output / "receipt.json"),
                "review_sha256": sha(review),
                "selected_ids": ids,
            }
        )
    spec = spec_fixture()
    for key in ("input_sha256", "receipt_sha256", "review_sha256"):
        del spec[key]
    spec.update(
        snapshot_bindings=bindings,
        split_policy="unseen_producer",
        manifest_sha256=sha(ROOT / "sources/wikidata-structured.json"),
    )
    spec["expected_facts"]["Q3"].update(instance_of_ids=["Q11"], producer_ids=["Q99"])
    spec["retrieval_cases"] = [
        {
            "case_id": "authored-cross-producer",
            "query_id": "Q3",
            "candidate_ids": ["Q1", "Q2"],
            "relevant_ids": ["Q2"],
            "cutoffs": [1, 2],
            "fact_basis": "Manually declared exact Q11 source fact, not user preference.",
        }
    ]
    return CohortExperiment.model_validate(spec), manifest, snapshots


def test_distinct_authorities_reuse_existing_fit_with_unseen_producer_and_no_sku_promotion(
    tmp_path,
):
    spec, manifest, paths = inputs(tmp_path)
    records, authorities = load_cohort(spec, manifest, paths)
    report = run_cohort(spec, records, authorities)
    assert report["fit_records"] == 2 and report["transform_records"] == 1
    assert report["cohort"]["training_producers"] == report["cohort"]["transform_producers"] == 1
    assert report["cohort"]["producer_overlap"] == 0 and not report["cohort"]["network_performed"]
    assert len(report["hashes"]["snapshots"]) == 2
    assert report["transformed"][0]["unknown_tokens"] == ["producer:Q99"]
    assert report["transformed"][0]["numeric"]["abv_percent"]["outside_fit_range"]
    assert (
        report["ranking_metrics"]["cases"][0]["representation_cosine"][0]["source_record_id"]
        == "Q2"
    )
    assert report["cohort"]["transform_representation"]["records"] == 1
    assert report["grain"] == "reviewed_source_product_family_not_sellable_sku"
    assert run_cohort(spec, records, authorities) == report


@pytest.mark.parametrize(
    "mutation",
    [
        "same-source",
        "same-input",
        "unknown-selection",
        "shared-producer",
        "unknown-producer",
        "cross-group",
    ],
)
def test_overlaps_unknown_or_leaking_partition_are_rejected_in_spec(tmp_path, mutation):
    spec, _, _ = inputs(tmp_path)
    data = spec.model_dump()
    if mutation == "same-source":
        data["snapshot_bindings"][1]["selected_ids"] = ["Q2", "Q3"]
    elif mutation == "same-input":
        data["snapshot_bindings"][1]["input_sha256"] = data["snapshot_bindings"][0]["input_sha256"]
    elif mutation == "unknown-selection":
        data["snapshot_bindings"][1]["selected_ids"] = ["Q999"]
    elif mutation == "shared-producer":
        data["expected_facts"]["Q3"]["producer_ids"] = ["Q20"]
    elif mutation == "unknown-producer":
        data["expected_facts"]["Q3"]["producer_ids"] = []
    else:
        data["family_groups"]["Q3"] = "family-a"
        data["transform_groups"] = ["family-a"]
    with pytest.raises(ValidationError):
        CohortExperiment.model_validate(data)


@pytest.mark.parametrize("snapshot_index", [0, 1])
@pytest.mark.parametrize("field", ["input_sha256", "receipt_sha256", "review_sha256"])
def test_each_authority_hash_is_checked_before_combining(tmp_path, snapshot_index, field):
    spec, manifest, paths = inputs(tmp_path)
    data = spec.model_dump()
    data["snapshot_bindings"][snapshot_index][field] = "f" * 64
    with pytest.raises(AuditError, match="authority_hash_mismatch"):
        load_cohort(CohortExperiment.model_validate(data), manifest, paths)


@pytest.mark.parametrize("mutation", ["failed-receipt", "revision", "brand"])
def test_matching_file_hashes_cannot_override_receipt_revision_or_family_review(tmp_path, mutation):
    spec, manifest, paths = inputs(tmp_path)
    data = spec.model_dump()
    source, receipt, review = paths["holdout"]
    path = review if mutation == "brand" else receipt
    value = json.loads(path.read_text())
    if mutation == "failed-receipt":
        value["accepted"] = False
    elif mutation == "revision":
        value["revisions"]["Q3"] = 9
    else:
        value["records"]["Q3"]["kind"] = "brand"
    path.write_text(json.dumps(value))
    field = "review_sha256" if mutation == "brand" else "receipt_sha256"
    data["snapshot_bindings"][1][field] = sha(path)
    with pytest.raises(AuditError):
        load_cohort(CohortExperiment.model_validate(data), manifest, paths)


@pytest.mark.parametrize(
    "mutation",
    [
        "rank",
        "qualifiers",
        "empty-invalid-qualifiers",
        "type",
        "numeric-id",
        "property",
        "datatype",
    ],
)
def test_producer_holdout_requires_explicit_consistent_source_relations(mutation):
    row = relation("Q20")
    if mutation == "rank":
        row["rank"] = "unsupported"
    elif mutation == "qualifiers":
        row["qualifiers"] = {"P1": []}
    elif mutation == "empty-invalid-qualifiers":
        row["qualifiers"] = []
    elif mutation == "type":
        row["mainsnak"]["datavalue"]["type"] = "string"
    elif mutation == "property":
        row["mainsnak"]["property"] = "P31"
    elif mutation == "datatype":
        row["mainsnak"]["datatype"] = "string"
    else:
        row["mainsnak"]["datavalue"]["value"]["numeric-id"] = True
    with pytest.raises(AuditError, match="relation_requires_review"):
        checked_relation_ids({"claims": {"P176": [row]}}, "P176")


@pytest.mark.parametrize("prop", ["P31", "P176"])
@pytest.mark.parametrize("field,bad_value", [("property", "P999"), ("datatype", "string")])
def test_rehashed_receipts_cannot_approve_contradictory_relation_metadata(
    tmp_path, prop, field, bad_value
):
    spec, manifest, paths = inputs(tmp_path)
    data = spec.model_dump()
    source, _, review = paths["holdout"]
    payload = json.loads(source.read_text())
    payload["entities"]["Q3"]["claims"][prop][0]["mainsnak"][field] = bad_value
    source.write_text(json.dumps(payload))
    # The collector's format acceptance and matching bytes still do not approve relation facts.
    output = tmp_path / ".pubburi" / "modified-replay"
    receipt = collect(manifest, ["Q3"], output, source)
    assert receipt["accepted"] is True
    checked = json.loads(review.read_text())
    checked["input_sha256"] = sha(source)
    review.write_text(json.dumps(checked))
    receipt_path = output / "receipt.json"
    paths["holdout"] = (source, receipt_path, review)
    data["snapshot_bindings"][1].update(
        input_sha256=sha(source), receipt_sha256=sha(receipt_path), review_sha256=sha(review)
    )
    with pytest.raises(AuditError, match="relation_requires_review"):
        load_cohort(CohortExperiment.model_validate(data), manifest, paths)


def test_heldout_facts_do_not_change_fit_parameters_and_existing_output_precedes_reads(
    tmp_path, monkeypatch
):
    spec, manifest, paths = inputs(tmp_path)
    records, auth = load_cohort(spec, manifest, paths)
    first = run_cohort(spec, records, auth)
    changed = spec.model_dump()
    changed["expected_facts"]["Q3"]["abv_percent"] = 100
    records = copy.deepcopy(records)
    records[-1]["abv_percent"] = 100
    second = run_cohort(CohortExperiment.model_validate(changed), records, auth)
    assert first["fit_fingerprint"] == second["fit_fingerprint"]
    assert first["fitted_parameters"] == second["fitted_parameters"]
    output = tmp_path / ".pubburi" / "existing.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text("preserve")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cohort",
            "--manifest",
            "unused",
            "--spec",
            "unused",
            "--output",
            str(output),
            "--snapshot",
            "a",
            "unused",
            "unused",
            "unused",
        ],
    )
    with patch.object(source_family_cohort, "read_json") as read:
        assert source_family_cohort.main() == 2
        read.assert_not_called()
    assert output.read_text() == "preserve"
