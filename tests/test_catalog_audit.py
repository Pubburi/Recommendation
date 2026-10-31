"""Directly authored entities test parsing; no real source records are vendored."""

import hashlib
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from pubburi_recommendation.catalog_audit import (
    ABV_UNITS,
    AuditError,
    ReviewManifest,
    audit,
    normalize_entities,
    read_json,
    scalar_quantity,
)

HASH = "a" * 64


def quantity(amount="+5", unit="Q2080811", **attributes):
    return {
        "rank": "normal",
        "mainsnak": {
            "snaktype": "value",
            "datavalue": {
                "value": {
                    "amount": amount,
                    "unit": "http://www.wikidata.org/entity/" + unit,
                    **attributes,
                },
            },
        },
    }


def entity(qid="Q1", claims=None, labels=None):
    return {
        "id": qid,
        "type": "item",
        "lastrevid": 1,
        "labels": {"en": {"value": "Fictional fixture"}} if labels is None else labels,
        "claims": {} if claims is None else claims,
    }


def payload(*entities):
    return {"entities": {item["id"]: item for item in entities}}


def reviews(records, input_hash=HASH):
    return ReviewManifest(input_sha256=input_hash, catalog_mode="demo", records=records)


def sku(**changes):
    return {
        "kind": "sellable_sku",
        "evidence_url": "https://example.org/fixture",
        "backend_product_id": 11,
        "demo_available": False,
        "reviewed_sku_group": "fixture-family-a",
        **changes,
    }


def test_missing_data_and_entity_ids_are_never_inferred_as_sku_or_price():
    report, records, request = audit(payload(entity()), HASH)
    assert records[0]["source_record_id"] == "Q1"
    assert records[0]["entity_kind"] == "unknown"
    assert records[0]["sku_group"] is None
    assert records[0]["availability"] == "unknown"
    assert records[0]["price_krw"] is None
    assert records[0]["price_kind"] == "unknown"
    assert records[0]["abv_percent"] is None
    assert records[0]["volume_ml"] is None
    assert request is None
    assert report["b0_demo_exported"] == 0


def test_unit_conversion_preserves_known_zero_abv_and_missing_label():
    report, records, _ = audit(
        payload(
            entity(
                claims={
                    "P2665": [quantity("+0")],
                    "P2234": [
                        quantity("+0.75", "Q11582"),
                        quantity("+750", "Q2332346"),
                        quantity("+75", "Q1815100"),
                    ],
                },
                labels={},
            )
        ),
        HASH,
    )
    assert records[0]["abv_percent"] == 0
    assert records[0]["volume_ml"] == 750
    assert records[0]["label"] is None
    assert records[0]["issues"] == []
    assert report["missing"]["abv_percent"] == 0
    assert report["missing"]["label"] == 1


@pytest.mark.parametrize(
    "statement, issue",
    [
        (quantity("+101"), "invalid_quantity"),
        (quantity("-1"), "invalid_quantity"),
        (quantity("NaN"), "invalid_quantity"),
        (quantity("Infinity"), "invalid_quantity"),
        (quantity(True), "invalid_quantity"),
        (quantity("1e9999999999"), "invalid_quantity"),
        (quantity("1e-999999999"), "invalid_quantity"),
        (quantity("+5", "Q999"), "unsupported_unit"),
        (quantity("+5", lowerBound="+4", upperBound="+6"), "range_requires_review"),
        ({**quantity(), "qualifiers": {"P585": [{}]}}, "context_requires_review"),
        ({"rank": "normal", "mainsnak": {"snaktype": "somevalue"}}, "unknown_statement"),
    ],
)
def test_unconfirmed_ambiguous_or_invalid_values_remain_unknown(statement, issue):
    value, issues = scalar_quantity(
        entity(claims={"P2665": [statement]}), "P2665", ABV_UNITS, Decimal(100)
    )
    assert value is None
    assert issues == [issue]


def test_conflicting_variants_are_not_flattened_or_cartesian_expanded():
    records = normalize_entities(
        payload(
            entity(
                claims={
                    "P2665": [quantity("+5"), quantity("+7")],
                    "P2234": [quantity("+500", "Q2332346"), quantity("+750", "Q2332346")],
                }
            )
        )
    )
    assert len(records) == 1
    assert records[0]["abv_percent"] is None
    assert records[0]["volume_ml"] is None
    assert records[0]["issues"] == [
        "abv:multiple_values_require_review",
        "volume:multiple_values_require_review",
    ]


def test_deprecated_values_do_not_override_current_statements():
    records = normalize_entities(
        payload(
            entity(
                claims={
                    "P2665": [{**quantity("+15"), "rank": "deprecated"}, quantity("+5")],
                }
            )
        )
    )
    assert records[0]["abv_percent"] == 5
    assert records[0]["issues"] == []


@pytest.mark.parametrize("kind", ["category", "brand", "producer", "product_family", "unknown"])
def test_non_sku_entity_cannot_be_exported_even_with_a_backend_id(kind):
    report, records, request = audit(payload(entity()), HASH, reviews({"Q1": sku(kind=kind)}))
    assert request["catalog"] == []
    assert records[0]["sku_group"] is None
    assert report["entity_kinds"] == {kind: 1}


def test_explicit_sku_mapping_keeps_demo_price_and_availability_separate_from_source_facts():
    report, records, request = audit(
        payload(entity(claims={"P2665": [quantity("+5")]})),
        HASH,
        reviews({"Q1": sku(demo_price_krw=1000, reviewed_category="fixture")}),
    )
    assert request["catalog"] == [
        {
            "product_id": 11,
            "available": False,
            "category": "fixture",
            "price_krw": 1000,
            "abv_percent": 5.0,
        }
    ]
    assert records[0]["price_krw"] is None
    assert records[0]["availability"] == "unknown"
    assert records[0]["sku_group"] == "fixture-family-a"
    assert report["catalog_mode"] == "demo"


@pytest.mark.parametrize(
    "changes",
    [
        {"backend_product_id": None},
        {"demo_available": None},
        {"reviewed_sku_group": None},
        {"reviewed_sku_group": " "},
    ],
)
def test_sku_mapping_requires_independent_id_availability_and_group_review(changes):
    with pytest.raises(AuditError):
        audit(payload(entity()), HASH, reviews({"Q1": sku(**changes)}))


def test_missing_label_and_duplicate_backend_ids_prevent_export():
    with pytest.raises(AuditError, match="sku_requires_reviewed_label"):
        audit(payload(entity(labels={})), HASH, reviews({"Q1": sku()}))
    with pytest.raises(ValidationError):
        audit(payload(entity("Q1"), entity("Q2")), HASH, reviews({"Q1": sku(), "Q2": sku()}))


def test_review_is_bound_to_snapshot_and_known_entities():
    with pytest.raises(AuditError, match="review_snapshot_hash_mismatch"):
        audit(payload(entity()), HASH, reviews({}, input_hash="b" * 64))
    with pytest.raises(AuditError, match="review_references_unknown_entity"):
        audit(payload(entity()), HASH, reviews({"Q2": sku()}))


@pytest.mark.parametrize(
    "source",
    [
        {},
        {"entities": []},
        {"entities": {"Q1": entity("Q2")}},
        payload({**entity(), "claims": []}),
        payload({**entity(), "lastrevid": True}),
        payload(entity(claims={"P2665": {}})),
    ],
)
def test_schema_drift_is_rejected(source):
    with pytest.raises(AuditError):
        audit(source, HASH)


def test_audit_output_is_reproducible_and_input_order_independent():
    assert audit(payload(entity("Q2"), entity("Q1")), HASH) == audit(
        payload(entity("Q1"), entity("Q2")), HASH
    )


def command(*args):
    return [sys.executable, "-m", "pubburi_recommendation.catalog_audit", *map(str, args)]


def test_cli_writes_private_reports_and_never_overwrites_prior_run(tmp_path):
    source = tmp_path / "input.json"
    source.write_text(json.dumps(payload(entity())))
    output = tmp_path / ".pubburi" / "run"
    args = [
        "--manifest",
        Path("sources/wikidata-structured.json"),
        "--input",
        source,
        "--output-dir",
        output,
    ]
    result = subprocess.run(command(*args), text=True, capture_output=True)
    assert result.returncode == 0
    assert json.loads((output / "audit-report.json").read_text())["entities"] == 1
    assert (output / "normalized-records.json").is_file()
    assert not (output / "b0-demo-request.json").exists()
    again = subprocess.run(command(*args), text=True, capture_output=True)
    assert again.returncode == 2
    assert "FileExistsError" in again.stderr


def test_cli_checks_permission_before_opening_source_and_keeps_errors_private(tmp_path):
    result = subprocess.run(
        command(
            "--manifest",
            "sources/at-traditional-liquor.json",
            "--input",
            tmp_path / "nonexistent-private-input",
            "--output-dir",
            tmp_path / ".pubburi" / "run",
        ),
        text=True,
        capture_output=True,
    )
    assert result.returncode == 2
    assert "source_normalization_not_approved" in result.stderr
    assert "nonexistent-private-input" not in result.stderr
    assert not (tmp_path / ".pubburi").exists()


def test_cli_rejects_public_output_and_nonfinite_json(tmp_path):
    source = tmp_path / "input.json"
    source.write_text('{"unexpected": NaN}')
    with pytest.raises(AuditError, match="nonfinite_json_number"):
        read_json(source)
    result = subprocess.run(
        command(
            "--manifest",
            "sources/wikidata-structured.json",
            "--input",
            source,
            "--output-dir",
            tmp_path / "public",
        ),
        text=True,
        capture_output=True,
    )
    assert result.returncode == 2
    assert "outputs_must_be_inside_private_pubburi_directory" in result.stderr
    source.write_text("[]")
    with pytest.raises(AuditError, match="json_object_required"):
        read_json(source)


def test_cli_mapping_export_uses_exact_file_hash(tmp_path):
    source = tmp_path / "input.json"
    source.write_text(json.dumps(payload(entity())))
    review = tmp_path / "review.json"
    review.write_text(
        reviews({"Q1": sku()}, hashlib.sha256(source.read_bytes()).hexdigest()).model_dump_json()
    )
    output = tmp_path / ".pubburi" / "run"
    result = subprocess.run(
        command(
            "--manifest",
            "sources/wikidata-structured.json",
            "--input",
            source,
            "--review",
            review,
            "--output-dir",
            output,
        ),
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0
    request = json.loads((output / "b0-demo-request.json").read_text())
    assert request["catalog"][0]["product_id"] == 11
    assert request["catalog"][0]["price_krw"] is None


@pytest.mark.parametrize(
    "text, reason",
    [
        ('{"entities":{}, "entities":{}}', "duplicate_json_object_key"),
        ('{"value":1e9999}', "nonfinite_json_number"),
    ],
)
def test_json_parser_rejects_duplicate_keys_and_numeric_overflow(tmp_path, text, reason):
    source = tmp_path / "source.json"
    source.write_text(text)
    with pytest.raises(AuditError, match=reason):
        read_json(source)


def test_json_parser_and_cli_hide_recursion_details(tmp_path):
    source = tmp_path / "private-source.json"
    source.write_text('{"private-source-marker":' + "[" * 20000 + "0" + "]" * 20000 + "}")
    with pytest.raises(AuditError, match="json_nesting_exceeds_parser_limit"):
        read_json(source)
    result = subprocess.run(
        command(
            "--manifest",
            "sources/wikidata-structured.json",
            "--input",
            source,
            "--output-dir",
            tmp_path / ".pubburi" / "deep",
        ),
        text=True,
        capture_output=True,
    )
    assert result.returncode == 2
    assert "json_nesting_exceeds_parser_limit" in result.stderr
    assert "Traceback" not in result.stderr and "private-source-marker" not in result.stderr
