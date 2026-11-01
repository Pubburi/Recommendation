"""Authored statement/family facts, not licensed source products or preference labels."""

import copy
import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from pubburi_recommendation import volume_context
from pubburi_recommendation.catalog_audit import AuditError, SourceManifest, read_json
from pubburi_recommendation.volume_context import (
    ContextReview,
    ObservationSpec,
    contextual_quantity,
    observe_family,
    prepare_observations,
    write_private_report,
)
from pubburi_recommendation.wikidata_collect import collect

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "sources/wikidata-structured.json"


def context(qid="Q10"):
    return {
        "property": "P518",
        "datatype": "wikibase-item",
        "snaktype": "value",
        "datavalue": {
            "type": "wikibase-entityid",
            "value": {"id": qid, "numeric-id": int(qid[1:]), "entity-type": "item"},
        },
    }


def claim(sid="Q1$small", qid="Q10", amount="+0.33"):
    return {
        "id": sid,
        "rank": "normal",
        "mainsnak": {
            "property": "P2234",
            "datatype": "quantity",
            "snaktype": "value",
            "datavalue": {
                "type": "quantity",
                "value": {"amount": amount, "unit": "http://www.wikidata.org/entity/Q11582"},
            },
        },
        "qualifiers": {"P518": [context(qid)]},
        "qualifiers-order": ["P518"],
    }


def contexts():
    return {
        qid: ContextReview(
            revision=8,
            label=label,
            scope="volume_context_only",
            rationale="Authored definition, no real SKU.",
        )
        for qid, label in (("Q10", "Authored small"), ("Q11", "Authored large"))
    }


def family():
    return {
        "id": "Q1",
        "type": "item",
        "lastrevid": 7,
        "labels": {"en": {"value": "Authored family"}},
        "claims": {"P2234": [claim(), claim("Q1$large", "Q11", "+20")]},
    }


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs(tmp_path):
    def write(name, value):
        path = tmp_path / (name + ".json")
        path.write_text(json.dumps(value))
        return path

    source = write("families", {"success": 1, "entities": {"Q1": family()}})
    definitions = write(
        "definitions",
        {
            "success": 1,
            "entities": {
                qid: {
                    "id": qid,
                    "type": "item",
                    "lastrevid": 8,
                    "labels": {"en": {"value": row.label}},
                    "claims": {},
                }
                for qid, row in contexts().items()
            },
        },
    )
    manifest = SourceManifest.model_validate(read_json(MANIFEST)[0])
    paths = {"input": source, "context_input": definitions}
    for name, ids in (("input", ["Q1"]), ("context_input", ["Q10", "Q11"])):
        output = tmp_path / ".pubburi" / name
        collect(manifest, ids, output, paths[name])
        paths["receipt" if name == "input" else "context_receipt"] = output / "receipt.json"
    paths["review"] = write(
        "review",
        {
            "input_sha256": sha(source),
            "catalog_mode": "demo",
            "records": {
                "Q1": {"kind": "product_family", "evidence_url": "https://example.invalid/authored"}
            },
        },
    )
    spec = ObservationSpec.model_validate(
        {
            "schema_version": 1,
            "evidence_kind": "authored_regression_fixture",
            "manifest_sha256": sha(MANIFEST),
            **{k + "_sha256": sha(p) for k, p in paths.items()},
            "family_groups": {"Q1": "same-family-for-all-contexts"},
            "source_revisions": {"Q1": 7},
            "contexts": {qid: row.model_dump() for qid, row in contexts().items()},
            "expected_observations": {
                "Q1$small": {"source_record_id": "Q1", "context_id": "Q10", "volume_ml": "330"},
                "Q1$large": {"source_record_id": "Q1", "context_id": "Q11", "volume_ml": "20000"},
            },
        }
    )
    return spec, paths


def test_two_contexts_preserve_separate_quantities_and_one_family_without_sku_inference(tmp_path):
    spec, paths = inputs(tmp_path)
    report = prepare_observations(spec, MANIFEST, paths)
    assert report["active_volume_observations"] == report["preserved_observations"] == 2
    assert report["held_observations"] == 0
    assert report["families"] == [
        {
            "source_record_id": "Q1",
            "family_group": "same-family-for-all-contexts",
            "volume_ml": None,
        }
    ]
    assert {row["volume_ml"] for row in report["observations"]} == {"330", "20000"}
    assert {row["family_group"] for row in report["observations"]} == {
        "same-family-for-all-contexts"
    }
    assert all(
        row["abv_percent"] is row["gtin"] is row["backend_product_id"] is None
        for row in report["observations"]
    )
    assert report == prepare_observations(spec, MANIFEST, paths)
    assert not report["model_fit_performed"] and report["backend_mappings_created"] == 0


@pytest.mark.parametrize(
    "amount,unit,expected",
    [
        ("+0.33", "Q11582", "330"),
        ("+33", "Q1815100", "330"),
        ("+330", "Q2332346", "330"),
        ("1e3", "Q11582", "1000000"),
    ],
)
def test_exact_canonical_units_and_exponents_never_average_or_round(amount, unit, expected):
    row = claim(amount=amount)
    row["mainsnak"]["datavalue"]["value"]["unit"] = "https://www.wikidata.org/entity/" + unit
    assert contextual_quantity(row, contexts()) == ("Q10", expected, [])


@pytest.mark.parametrize(
    "mutation",
    [
        "rank",
        "property",
        "datatype",
        "snaktype",
        "type",
        "bare-unit",
        "wrong-namespace",
        "unknown-unit",
        "zero",
        "negative",
        "too-large",
        "nan",
        "inf",
        "range",
        "bound-type",
        "amount-type",
        "precision",
    ],
)
def test_malformed_or_ambiguous_quantity_is_held_unknown(mutation):
    row = claim()
    snak = row["mainsnak"]
    value = snak["datavalue"]["value"]
    if mutation == "rank":
        row["rank"] = "unsupported"
    elif mutation in ("property", "datatype", "snaktype"):
        snak[mutation] = "wrong"
    elif mutation == "type":
        snak["datavalue"]["type"] = "string"
    elif mutation == "bare-unit":
        value["unit"] = "Q11582"
    elif mutation == "wrong-namespace":
        value["unit"] = "https://example.invalid/Q11582"
    elif mutation == "unknown-unit":
        value["unit"] = "http://www.wikidata.org/entity/Q11229"
    elif mutation == "range":
        value["upperBound"] = "+0.34"
    elif mutation == "bound-type":
        value["upperBound"] = 0.33
    elif mutation == "amount-type":
        value["amount"] = True
    else:
        value["amount"] = {
            "zero": "0",
            "negative": "-1",
            "too-large": "1001",
            "nan": "NaN",
            "inf": "Infinity",
            "precision": "0.12345678901234567890123456789",
        }[mutation]
    context_id, volume, holds = contextual_quantity(row, contexts())
    assert context_id == "Q10" and volume is None and holds


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "extra-property",
        "duplicate",
        "two-contexts",
        "unknown",
        "property",
        "datatype",
        "snaktype",
        "type",
        "numeric-id",
        "bool-numeric-id",
        "entity-type",
        "order",
        "empty",
        "null",
    ],
)
def test_context_qualifier_must_be_one_explicit_reviewed_item_without_other_scope(mutation):
    row = claim()
    qualifier = row["qualifiers"]["P518"][0]
    if mutation == "missing":
        del row["qualifiers"]
    elif mutation == "extra-property":
        row["qualifiers"]["P580"] = []
    elif mutation == "duplicate":
        row["qualifiers"]["P518"].append(copy.deepcopy(qualifier))
    elif mutation == "two-contexts":
        row["qualifiers"]["P518"].append(context("Q11"))
    elif mutation == "unknown":
        row["qualifiers"]["P518"] = [context("Q99")]
    elif mutation in ("property", "datatype", "snaktype"):
        qualifier[mutation] = "wrong"
    elif mutation == "type":
        qualifier["datavalue"]["type"] = "string"
    elif mutation in ("numeric-id", "bool-numeric-id", "entity-type"):
        qualifier["datavalue"]["value"][
            "numeric-id" if mutation == "bool-numeric-id" else mutation
        ] = True if mutation == "bool-numeric-id" else "wrong"
    elif mutation == "order":
        row["qualifiers-order"] = ["P518", "P518"]
    elif mutation == "empty":
        row["qualifiers"]["P518"] = []
    else:
        row["qualifiers"] = None
    context_id, volume, holds = contextual_quantity(row, contexts())
    assert context_id is None and volume == "330" and holds


@pytest.mark.parametrize("amount", ["+0.33", "+0.5"])
def test_same_family_context_repetition_or_conflict_holds_all_instead_of_overwrite(amount):
    entity = family()
    entity["claims"]["P2234"].append(claim("Q1$repeat", amount=amount))
    rows = observe_family(entity, "family", contexts())
    affected = [row for row in rows if row["context_id"] == "Q10"]
    assert len(rows) == 3 and len(affected) == 2
    assert all(
        row["hold_reasons"] == ["repeated_family_context_requires_review"] for row in affected
    )


def test_statement_order_does_not_change_report_and_deprecated_is_not_an_active_observation():
    entity = family()
    baseline = observe_family(entity, "family", contexts())
    entity["claims"]["P2234"].reverse()
    entity["claims"]["P2234"].append({**claim("Q1$old"), "rank": "deprecated"})
    assert observe_family(entity, "family", contexts()) == baseline


@pytest.mark.parametrize("sid", [None, "Q2$other", "Q1$small", "Q1$bad\n"])
def test_missing_foreign_duplicate_or_invalid_statement_ids_fail_closed(sid):
    entity = family()
    entity["claims"]["P2234"][1]["id"] = sid
    with pytest.raises(AuditError, match="statement_id_required"):
        observe_family(entity, "family", contexts())


@pytest.mark.parametrize(
    "field", ["input", "receipt", "review", "context_input", "context_receipt"]
)
def test_each_raw_receipt_and_review_authority_is_hash_bound(tmp_path, field):
    spec, paths = inputs(tmp_path)
    data = spec.model_dump()
    data[field + "_sha256"] = "f" * 64
    with pytest.raises(AuditError, match="authority_hash_mismatch"):
        prepare_observations(ObservationSpec.model_validate(data), MANIFEST, paths)


@pytest.mark.parametrize("field", ["receipt", "context_receipt"])
@pytest.mark.parametrize("mutation", ["failed", "revision"])
def test_rehashed_receipt_still_requires_acceptance_and_matching_revision(
    tmp_path, field, mutation
):
    spec, paths = inputs(tmp_path)
    data = spec.model_dump()
    receipt = json.loads(paths[field].read_text())
    if mutation == "failed":
        receipt["accepted"] = False
    else:
        receipt["revisions"][next(iter(receipt["revisions"]))] += 1
    paths[field].write_text(json.dumps(receipt))
    data[field + "_sha256"] = sha(paths[field])
    with pytest.raises(AuditError, match="accepted_matching_source_receipt_required"):
        prepare_observations(ObservationSpec.model_validate(data), MANIFEST, paths)


@pytest.mark.parametrize(
    "mutation",
    [
        "context-revision",
        "context-label",
        "family-revision",
        "family-kind",
        "frozen-volume",
        "missing-fact",
    ],
)
def test_valid_collection_receipt_does_not_override_manual_scope_or_frozen_facts(
    tmp_path, mutation
):
    spec, paths = inputs(tmp_path)
    data = spec.model_dump()
    if mutation == "context-revision":
        data["contexts"]["Q10"]["revision"] += 1
    elif mutation == "context-label":
        data["contexts"]["Q10"]["label"] = "invented"
    elif mutation == "family-revision":
        data["source_revisions"]["Q1"] += 1
    elif mutation == "family-kind":
        review = json.loads(paths["review"].read_text())
        review["records"]["Q1"]["kind"] = "brand"
        paths["review"].write_text(json.dumps(review))
        data["review_sha256"] = sha(paths["review"])
    elif mutation == "frozen-volume":
        data["expected_observations"]["Q1$small"]["volume_ml"] = "500"
    else:
        del data["expected_observations"]["Q1$small"]
    with pytest.raises(AuditError):
        prepare_observations(ObservationSpec.model_validate(data), MANIFEST, paths)


def test_fact_scope_cannot_point_to_foreign_family_or_unreviewed_context(tmp_path):
    spec, _ = inputs(tmp_path)
    data = spec.model_dump()
    data["expected_observations"]["Q1$small"]["context_id"] = "Q99"
    with pytest.raises(ValidationError):
        ObservationSpec.model_validate(data)


def test_private_report_is_complete_nonoverwriting_and_cli_failure_does_not_reflect_input(
    tmp_path, capsys
):
    path = tmp_path / ".pubburi" / "observations.json"
    write_private_report(path, {"complete": True})
    with pytest.raises(FileExistsError):
        write_private_report(path, {"complete": False})
    assert json.loads(path.read_text()) == {"complete": True}
    assert list(path.parent.iterdir()) == [path]
    with pytest.raises(AuditError):
        write_private_report(tmp_path / "public.json", {})
    spec, paths = inputs(tmp_path)
    data = spec.model_dump()
    data["input_sha256"] = "f" * 64
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(data))
    failed = tmp_path / ".pubburi" / "failed.json"
    command = [
        "volume-context",
        "--manifest",
        str(MANIFEST),
        "--spec",
        str(spec_path),
        "--output",
        str(failed),
    ]
    for name, value in paths.items():
        command.extend(["--" + name.replace("_", "-"), str(value)])
    with patch.object(sys, "argv", command):
        assert volume_context.main() == 2
    assert capsys.readouterr().err == "volume_context_preparation_failed\n"
    assert not failed.exists()
