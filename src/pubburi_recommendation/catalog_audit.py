"""Offline structured-source audit. No network, inferred SKU, price, or taste data."""

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter
from decimal import Decimal, DecimalException, InvalidOperation
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from pubburi_recommendation.baseline import CatalogProduct, RecommendationRequest

QID = re.compile(r"Q[1-9][0-9]*\Z")
MAX_INPUT_BYTES = 10 * 1024 * 1024
ABV_UNITS = {"Q2080811": Decimal(1)}
VOLUME_UNITS = {"Q2332346": Decimal(1), "Q11582": Decimal(1000), "Q1815100": Decimal(10)}


class AuditError(ValueError):
    """A safe diagnostic that contains no source record contents."""


class SourceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal[1]
    source_id: str = Field(min_length=1, max_length=100)
    provider: str = Field(min_length=1, max_length=200)
    source_url: str = Field(min_length=1, max_length=1000)
    reviewed_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    license_label: str = Field(min_length=1, max_length=100)
    evidence_urls: list[str] = Field(min_length=1, max_length=10)
    local_structured_normalization: bool
    structured_feature_fit: bool
    raw_redistribution_in_git: Literal[False]
    linked_media_included: Literal[False]
    free_text_included: Literal[False]
    additional_conditions: list[str] = Field(max_length=20)
    decision_notes: list[str] = Field(min_length=1, max_length=20)


class EntityReview(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["category", "brand", "producer", "product_family", "sellable_sku", "unknown"]
    evidence_url: str = Field(min_length=1, max_length=1000)
    backend_product_id: int | None = Field(default=None, ge=1, le=2_147_483_647)
    demo_available: bool | None = None
    demo_price_krw: int | None = Field(default=None, ge=0, le=2_147_483_647)
    reviewed_category: str | None = Field(default=None, min_length=1, max_length=64)
    reviewed_sku_group: str | None = Field(default=None, min_length=1, max_length=128)


class ReviewManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    catalog_mode: Literal["demo"]
    records: dict[str, EntityReview]


def read_json(path: Path) -> tuple[dict, str]:
    with path.open("rb") as source:
        content = source.read(MAX_INPUT_BYTES + 1)
    return parse_json_bytes(content)


def parse_json_bytes(content: bytes) -> tuple[dict, str]:
    """Apply the same bounded/duplicate-key/finite JSON boundary to files and HTTP bodies."""
    if len(content) > MAX_INPUT_BYTES:
        raise AuditError("input_exceeds_10_mib")

    def invalid_number(_value):
        raise AuditError("nonfinite_json_number")

    def finite_float(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise AuditError("nonfinite_json_number")
        return parsed

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise AuditError("duplicate_json_object_key")
            result[key] = value
        return result

    try:
        payload = json.loads(
            content,
            parse_constant=invalid_number,
            parse_float=finite_float,
            object_pairs_hook=unique_object,
        )
    except AuditError:
        raise
    except RecursionError as error:
        raise AuditError("json_nesting_exceeds_parser_limit") from error
    except (UnicodeError, ValueError) as error:
        raise AuditError("invalid_json") from error
    if not isinstance(payload, dict):
        raise AuditError("json_object_required")
    return payload, hashlib.sha256(content).hexdigest()


def statements(entity: dict, prop: str) -> list[dict]:
    values = entity.get("claims", {}).get(prop, [])
    if not isinstance(values, list) or any(not isinstance(value, dict) for value in values):
        raise AuditError("statement_array_required")
    if any(not isinstance(value.get("mainsnak"), dict) for value in values):
        raise AuditError("statement_mainsnak_object_required")
    return values


def item_relations(entity: dict, prop: str) -> tuple[list[str], list[str]]:
    """Preserve unknown relation sets; a QID-shaped value cannot repair explicit contradictions."""
    ids, issues = set(), set()
    for statement in statements(entity, prop):
        if statement.get("rank") == "deprecated":
            continue
        snak = statement["mainsnak"]
        data = snak.get("datavalue")
        value = data.get("value") if isinstance(data, dict) else None
        qid = value.get("id") if isinstance(value, dict) else None
        qualifiers = statement.get("qualifiers", {})
        if not isinstance(qualifiers, dict) or qualifiers:
            issues.add("context_requires_review")
            continue
        # Omitted redundant legacy metadata remains compatible. If supplied, every
        # part must describe this unqualified item relation, including its identity.
        if (
            ("rank" in statement and statement["rank"] not in ("normal", "preferred"))
            or ("snaktype" in snak and snak["snaktype"] != "value")
            or ("property" in snak and snak["property"] != prop)
            or ("datatype" in snak and snak["datatype"] != "wikibase-item")
            or not isinstance(data, dict)
            or ("type" in data and data["type"] != "wikibase-entityid")
            or not isinstance(qid, str)
            or len(qid) > 32
            or not QID.fullmatch(qid)
            or ("entity-type" in value and value["entity-type"] != "item")
            or (
                "numeric-id" in value
                and (type(value["numeric-id"]) is not int or value["numeric-id"] != int(qid[1:]))
            )
        ):
            issues.add("relation_statement_requires_review")
            continue
        ids.add(qid)
    # Do not turn a partly unknown set into a complete positive fact declaration.
    return ([] if issues else sorted(ids)), sorted(issues)


def item_ids(entity: dict, prop: str) -> list[str]:
    return item_relations(entity, prop)[0]


def wikidata_unit_factors(units: dict[str, Decimal]) -> dict[str, Decimal]:
    """Only the supported Wikidata entity URIs name these conversion factors."""
    return {
        f"{scheme}://www.wikidata.org/entity/{qid}": factor
        for qid, factor in units.items()
        for scheme in ("http", "https")
    }


def scalar_quantity(entity: dict, prop: str, units: dict, maximum: Decimal):
    values = set()
    issues = set()
    unit_factors = wikidata_unit_factors(units)
    for statement in statements(entity, prop):
        if statement.get("rank") == "deprecated":
            continue
        if statement.get("qualifiers"):
            issues.add("context_requires_review")
            continue
        snak = statement.get("mainsnak", {})
        data = snak.get("datavalue")
        value = data.get("value") if isinstance(data, dict) else None
        if snak.get("snaktype") != "value" or not isinstance(value, dict):
            issues.add("unknown_statement")
            continue
        # Minimal legacy/authored inputs omit redundant metadata. An explicit conflict
        # cannot be repaired from its claims bucket or from a quantity-shaped value.
        if (
            ("property" in snak and snak["property"] != prop)
            or ("datatype" in snak and snak["datatype"] != "quantity")
            or ("type" in data and data["type"] != "quantity")
        ):
            issues.add("quantity_statement_requires_review")
            continue
        unit = value.get("unit")
        if not isinstance(unit, str) or unit not in unit_factors:
            issues.add("unsupported_unit")
            continue
        try:
            if not isinstance(value.get("amount"), str) or len(value["amount"]) > 128:
                raise InvalidOperation
            amount = Decimal(value["amount"])
            bounds = [
                Decimal(value.get(key, value["amount"])) for key in ("lowerBound", "upperBound")
            ]
            if not amount.is_finite() or any(not bound.is_finite() for bound in bounds):
                raise InvalidOperation
            if any(bound != amount for bound in bounds):
                issues.add("range_requires_review")
                continue
            converted = amount * unit_factors[unit]
            if converted < 0 or converted > maximum:
                raise InvalidOperation
            if amount != 0 and (converted == 0 or float(converted) == 0):
                raise InvalidOperation
            if prop == "P2234" and converted == 0:
                raise InvalidOperation
            values.add(converted)
        except (KeyError, TypeError, ValueError, DecimalException):
            issues.add("invalid_quantity")
    if len(values) > 1:
        issues.add("multiple_values_require_review")
    value = float(next(iter(values))) if len(values) == 1 and not issues else None
    return value, sorted(issues)


def normalize_entities(payload: dict) -> list[dict]:
    entities = payload.get("entities")
    if not isinstance(entities, dict) or len(entities) > 2000:
        raise AuditError("entities_object_required_max_2000")
    records = []
    for qid, entity in sorted(entities.items()):
        if not QID.fullmatch(qid) or not isinstance(entity, dict) or entity.get("id") != qid:
            raise AuditError("invalid_entity_identity")
        if entity.get("type") != "item" or "missing" in entity:
            raise AuditError("item_entity_required")
        if not isinstance(entity.get("claims", {}), dict):
            raise AuditError("claims_object_required")
        revision = entity.get("lastrevid")
        if type(revision) is not int or revision < 1:
            raise AuditError("positive_source_revision_required")
        name = None
        name_language = None
        if not isinstance(entity.get("labels", {}), dict):
            raise AuditError("labels_object_required")
        # Keep existing localized choices; mul is Wikidata's default-for-all source label.
        for language in ("ko", "en", "mul"):
            label_data = entity.get("labels", {}).get(language, {})
            label = label_data.get("value") if isinstance(label_data, dict) else None
            if isinstance(label, str) and label.strip():
                if len(label) > 1000:
                    raise AuditError("label_exceeds_1000_characters")
                name = label.strip()
                name_language = language
                break
        abv, abv_issues = scalar_quantity(entity, "P2665", ABV_UNITS, Decimal(100))
        volume, volume_issues = scalar_quantity(entity, "P2234", VOLUME_UNITS, Decimal(1_000_000))
        classes, class_issues = item_relations(entity, "P31")
        producers, producer_issues = item_relations(entity, "P176")
        records.append(
            {
                "source_id": "wikidata-structured",
                "source_record_id": qid,
                "source_revision": revision,
                "source_url": f"https://www.wikidata.org/wiki/{qid}?oldid={revision}",
                "label": name,
                "label_language": name_language,
                "instance_of_ids": classes,
                "producer_ids": producers,
                "abv_percent": abv,
                "volume_ml": volume,
                "price_krw": None,
                "price_kind": "unknown",
                "availability": "unknown",
                "sku_group": None,
                "entity_kind": "unknown",
                "issues": [
                    *(f"abv:{issue}" for issue in abv_issues),
                    *(f"volume:{issue}" for issue in volume_issues),
                    *(f"instance_of:{issue}" for issue in class_issues),
                    *(f"producer:{issue}" for issue in producer_issues),
                ],
            }
        )
    return records


def audit(
    payload: dict, input_hash: str, reviews: ReviewManifest | None = None
) -> tuple[dict, list, dict | None]:
    records = normalize_entities(payload)
    review_rows = {} if reviews is None else reviews.records
    if reviews is not None and reviews.input_sha256 != input_hash:
        raise AuditError("review_snapshot_hash_mismatch")
    record_ids = {record["source_record_id"] for record in records}
    if set(review_rows) - record_ids:
        raise AuditError("review_references_unknown_entity")
    catalog = []
    kinds = Counter()
    for record in records:
        review = review_rows.get(record["source_record_id"])
        if review is not None:
            record["entity_kind"] = review.kind
            record["review_evidence_url"] = review.evidence_url
        kinds[record["entity_kind"]] += 1
        if review is None or review.kind != "sellable_sku":
            continue
        if review.backend_product_id is None or review.demo_available is None:
            raise AuditError("sku_requires_backend_id_and_explicit_demo_availability")
        if review.reviewed_sku_group is None or not review.reviewed_sku_group.strip():
            raise AuditError("sku_requires_explicit_reviewed_group")
        if record["label"] is None:
            raise AuditError("sku_requires_reviewed_label")
        # Entity/brand IDs never become backend IDs or SKU groups automatically.
        record["sku_group"] = review.reviewed_sku_group
        catalog.append(
            CatalogProduct(
                product_id=review.backend_product_id,
                available=review.demo_available,
                category=review.reviewed_category,
                price_krw=review.demo_price_krw,
                abv_percent=record["abv_percent"],
            )
        )
    request = None if reviews is None else RecommendationRequest(catalog=catalog).model_dump()
    report = {
        "schema_version": 1,
        "input_sha256": input_hash,
        "source_id": "wikidata-structured",
        "entities": len(records),
        "entity_kinds": dict(sorted(kinds.items())),
        "label_languages": dict(
            sorted(Counter(record["label_language"] or "unknown" for record in records).items())
        ),
        "missing": {
            field: sum(record[field] is None for record in records)
            for field in ("label", "abv_percent", "volume_ml", "price_krw", "sku_group")
        },
        "quantity_issues": dict(
            sorted(
                Counter(
                    issue
                    for record in records
                    for issue in record["issues"]
                    if issue.startswith(("abv:", "volume:"))
                ).items()
            )
        ),
        "relation_issues": dict(
            sorted(
                Counter(
                    issue
                    for record in records
                    for issue in record["issues"]
                    if issue.startswith(("instance_of:", "producer:"))
                ).items()
            )
        ),
        "b0_demo_exported": len(catalog),
        "catalog_mode": "demo" if reviews else None,
        "limitations": [
            "purposeful_small_sample_not_population_estimate",
            "no_taste_or_price_inference",
            "brands_and_categories_are_not_skus",
            "not_model_training_or_user_preference_evaluation",
        ],
    }
    return report, records, request


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--fact-evidence", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest_data, manifest_hash = read_json(args.manifest)
        manifest = SourceManifest.model_validate(manifest_data)
        if not manifest.local_structured_normalization:
            raise AuditError("source_normalization_not_approved")
        if ".pubburi" not in args.output_dir.resolve().parts:
            raise AuditError("outputs_must_be_inside_private_pubburi_directory")
        if (
            manifest.source_id == "at-traditional-liquor"
            and manifest.license_label == "portal-unrestricted-with-additional-notes"
        ):
            from pubburi_recommendation.at_source import AuditError as AtAuditError
            from pubburi_recommendation.at_source import audit_at_source

            try:
                report, records, request = audit_at_source(
                    manifest_hash, args.input, args.receipt, args.review, args.fact_evidence
                )
            except AtAuditError as error:
                # `python -m` has a distinct __main__ module/class identity.
                raise AuditError(str(error)) from error
        elif manifest.source_id == "wikidata-structured" and manifest.license_label == "CC0-1.0":
            if args.receipt is not None or args.fact_evidence:
                raise AuditError("at_evidence_options_require_at_source")
            payload, input_hash = read_json(args.input)
            review = (
                None
                if args.review is None
                else ReviewManifest.model_validate(read_json(args.review)[0])
            )
            report, records, request = audit(payload, input_hash, review)
        else:
            raise AuditError("unsupported_source_or_license")
        # New directories prevent overwriting an earlier source/review snapshot.
        args.output_dir.mkdir(parents=True, exist_ok=False)
        outputs = {"audit-report.json": report, "normalized-records.json": records}
        if request is not None:
            outputs["b0-demo-request.json"] = request
        for name, content in outputs.items():
            (args.output_dir / name).write_text(
                json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        print(json.dumps(report, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        # ValidationError includes input values; never echo source contents or local paths.
        reason = str(error) if isinstance(error, AuditError) else type(error).__name__
        print(f"Catalog audit failed: {reason}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
