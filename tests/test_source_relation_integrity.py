"""Authored relation faults prove normalization/fit/curation boundaries, not source error rates."""

import copy
import json
import math
import subprocess
import sys

import pytest
from test_source_catalog import HASHES, curation_fixture, source_fixture, source_rows
from test_source_family_cohort import relation
from test_source_family_experiment import (
    raw_fixture,
    records_fixture,
    review_fixture,
    spec_fixture,
)

from pubburi_recommendation.catalog_audit import (
    AuditError,
    SourceManifest,
    audit,
    item_ids,
    item_relations,
    read_json,
)
from pubburi_recommendation.package_identity_audit import audit_packages
from pubburi_recommendation.source_catalog import CatalogCuration, curate_catalog
from pubburi_recommendation.source_family_experiment import FamilyExperiment, fit_representation
from pubburi_recommendation.wikidata_collect import check_payload, collect

FAULTS = ("property", "datatype", "value-type", "entity-type", "numeric-id", "snaktype")


def explicit_relation(qid, prop):
    statement = relation(qid)
    statement["mainsnak"].update(property=prop, datatype="wikibase-item")
    return statement


def corrupt(statement, fault, prop):
    snak = statement["mainsnak"]
    if fault == "property":
        snak["property"] = "P176" if prop == "P31" else "P31"
    elif fault == "datatype":
        snak["datatype"] = "string"
    elif fault == "value-type":
        snak["datavalue"]["type"] = "string"
    elif fault == "entity-type":
        snak["datavalue"]["value"]["entity-type"] = "property"
    elif fault == "numeric-id":
        snak["datavalue"]["value"]["numeric-id"] = 999
    else:
        snak["snaktype"] = "novalue"


def fault_payload(prop, fault):
    raw = raw_fixture()
    qid = "Q10" if prop == "P31" else "Q20"
    raw["entities"]["Q1"]["claims"][prop] = [explicit_relation(qid, prop)]
    corrupt(raw["entities"]["Q1"]["claims"][prop][0], fault, prop)
    return raw


@pytest.mark.parametrize(
    "prop,field,prefix",
    [("P31", "instance_of_ids", "instance_of"), ("P176", "producer_ids", "producer")],
)
@pytest.mark.parametrize("fault", FAULTS)
def test_explicit_relation_contradictions_never_become_fact_ids_or_fit_inputs(
    prop, field, prefix, fault, monkeypatch
):
    raw = fault_payload(prop, fault)
    records = records_fixture(raw)
    assert records[0][field] == []
    assert records[0]["issues"] == [f"{prefix}:relation_statement_requires_review"]
    report, _, _ = audit(raw, "a" * 64)
    assert report["relation_issues"] == {f"{prefix}:relation_statement_requires_review": 1}
    assert report["quantity_issues"] == {} and records[0]["abv_percent"] == 5
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import MinMaxScaler

    def forbidden(*_args, **_kwargs):
        pytest.fail("Contradictory categorical facts must fail before any fit")

    with monkeypatch.context() as context:
        context.setattr(TfidfVectorizer, "fit_transform", forbidden)
        context.setattr(MinMaxScaler, "fit", forbidden)
        with pytest.raises(AuditError, match="manual_facts_conflict_with_reviewed_source"):
            fit_representation(FamilyExperiment.model_validate(spec_fixture()), records, {})
    honest = spec_fixture()
    honest["expected_facts"]["Q1"][field] = []
    fitted = fit_representation(FamilyExperiment.model_validate(honest), records, {})
    parameters = fitted["fitted_parameters"]
    idf = dict(zip(parameters["vocabulary"], parameters["idf"], strict=True))
    if prop == "P31":
        assert "instance_of:Q10" not in idf and "instance_of:Q11" in idf
        assert idf["producer:Q20"] == 1
    else:
        # The valid Q2 producer remains; only its document frequency is now one.
        assert idf["producer:Q20"] == pytest.approx(math.log(3 / 2) + 1)
    assert parameters["numeric_fit"]["abv_percent"]["observed_training_values"] == 2


@pytest.mark.parametrize("prop", ["P31", "P176", "P1716"])
@pytest.mark.parametrize("kind", ["minimal", "explicit", "preferred"])
def test_known_relation_shapes_preserve_legacy_omissions_and_item_id_wrapper(prop, kind):
    statement = explicit_relation("Q10", prop)
    if kind == "minimal":
        statement = {"mainsnak": {"datavalue": {"value": {"id": "Q10"}}}}
    elif kind == "preferred":
        statement["rank"] = "preferred"
    value = {"claims": {prop: [statement, copy.deepcopy(statement)]}}
    assert item_relations(value, prop) == (["Q10"], [])
    assert item_ids(value, prop) == ["Q10"]


@pytest.mark.parametrize("fault", FAULTS)
def test_bad_active_neighbor_quarantines_whole_set_but_deprecated_is_ignored(fault):
    good, bad = explicit_relation("Q10", "P31"), explicit_relation("Q11", "P31")
    corrupt(bad, fault, "P31")
    value = {"claims": {"P31": [good, bad]}}
    assert item_relations(value, "P31") == ([], ["relation_statement_requires_review"])
    value["claims"]["P31"].reverse()
    assert item_relations(value, "P31") == ([], ["relation_statement_requires_review"])
    bad["rank"] = "deprecated"
    assert item_relations(value, "P31") == (["Q10"], [])


@pytest.mark.parametrize("qualifiers", [{"P580": []}, [], None, ""])
def test_qualified_or_ambiguous_relation_is_not_an_unconditional_class_or_producer(qualifiers):
    value = explicit_relation("Q10", "P31")
    value["qualifiers"] = qualifiers
    assert item_relations({"claims": {"P31": [value]}}, "P31") == ([], ["context_requires_review"])


@pytest.mark.parametrize(
    "target,value",
    [
        ("rank", "unsupported"),
        ("id", "Q01"),
        ("id", 10),
        ("id", "Q" + "1" * 33),
        ("numeric-id", True),
        ("numeric-id", "10"),
        pytest.param("numeric-id", 10**5000, id="oversized-python-integer"),
    ],
)
def test_malformed_identity_types_and_bounds_stay_unknown_without_coercion(target, value):
    statement = explicit_relation("Q10", "P31")
    if target == "rank":
        statement[target] = value
    else:
        statement["mainsnak"]["datavalue"]["value"][target] = value
    assert item_relations({"claims": {"P31": [statement]}}, "P31") == (
        [],
        ["relation_statement_requires_review"],
    )


@pytest.mark.parametrize("neighbor", [False, True])
@pytest.mark.parametrize("fault", FAULTS)
def test_malformed_container_or_brand_cannot_be_approved_by_mixed_type_scope(neighbor, fault):
    raw = source_fixture(mixed=neighbor)
    statement = raw["entities"]["Q1"]["claims"]["P31"][int(neighbor)]
    corrupt(statement, fault, "P31")
    rows = source_rows(raw)
    assert rows[0]["instance_of_ids"] == []
    assert "instance_of_relations_require_review" in rows[0]["hold_reasons"]
    assert not rows[0]["package_field_combination_present"]
    # curation_fixture includes a mixed-type interpretation; it cannot override this hold.
    with pytest.raises(AuditError, match="curation_cannot_override_unresolved_source_hold"):
        curate_catalog(CatalogCuration.model_validate(curation_fixture()), rows, HASHES)


@pytest.mark.parametrize("prop", ["P31", "P176"])
@pytest.mark.parametrize("fault", ["property", "value-type"])
def test_real_offline_receipt_cli_rejects_false_facts_but_honest_unknown_can_fit(
    tmp_path, prop, fault
):
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    manifest_path = root / "sources/wikidata-structured.json"
    manifest = SourceManifest.model_validate(read_json(manifest_path)[0])
    raw = tmp_path / "raw.json"
    raw.write_text(json.dumps(fault_payload(prop, fault)))
    output = tmp_path / ".pubburi" / "source"
    receipt = collect(manifest, ["Q1", "Q2", "Q3"], output, raw)
    assert receipt["accepted"] is True
    review = tmp_path / "review.json"
    review.write_text(json.dumps(review_fixture(read_json(raw)[1])))
    spec = spec_fixture(
        input_sha256=read_json(raw)[1],
        receipt_sha256=read_json(output / "receipt.json")[1],
        review_sha256=read_json(review)[1],
        manifest_sha256=read_json(manifest_path)[1],
    )
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec))
    destination = tmp_path / ".pubburi" / "false-fit.json"
    command = [
        sys.executable,
        "-m",
        "pubburi_recommendation.source_family_experiment",
        "--manifest",
        str(manifest_path),
        "--input",
        str(raw),
        "--receipt",
        str(output / "receipt.json"),
        "--review",
        str(review),
        "--spec",
        str(spec_path),
        "--output",
        str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=20)
    assert result.returncode == 2 and not destination.exists()
    assert (
        result.stderr.strip()
        == "Source family experiment failed: manual_facts_conflict_with_reviewed_source"
    )
    field = "instance_of_ids" if prop == "P31" else "producer_ids"
    spec["expected_facts"]["Q1"][field] = []
    spec_path.write_text(json.dumps(spec))
    command[-1] = str(destination.with_name("honest-fit.json"))
    result = subprocess.run(command, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["passed_contract"] is True


def test_package_audit_holds_malformed_class_while_preserving_valid_quantities():
    raw = source_fixture()
    corrupt(raw["entities"]["Q1"]["claims"]["P31"][1], "datatype", "P31")
    report, rows = audit_packages(
        raw, check_payload(raw, ["Q1"]), HASHES, "authored_regression_fixture"
    )
    assert report["package_field_combination_entities"] == 0
    assert rows[0]["volume_ml"] == 500 and rows[0]["abv_percent"] == 5
    assert rows[0]["backend_product_id"] is None and not rows[0]["feature_fit_eligible"]
