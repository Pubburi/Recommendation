"""Audit source barcode/package evidence without registering Backend SKUs or fitting models."""

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from pubburi_recommendation.baseline import ContractModel
from pubburi_recommendation.catalog_audit import (
    ABV_UNITS,
    VOLUME_UNITS,
    AuditError,
    SourceManifest,
    item_ids,
    read_json,
    statements,
)
from pubburi_recommendation.collection_snapshot import verify_collection_snapshot
from pubburi_recommendation.wikidata_collect import write_receipt

SourceId = Annotated[str, StringConstraints(pattern=r"^Q[1-9][0-9]{0,30}$")]
Hash = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
# This inspected class is an explicit container signal, never inferred from a name/image filename.
CONTAINER_CLASSES = {"Q1121690"}  # beverage can
BRAND_CLASS = "Q15075508"


class PackageDecision(ContractModel):
    decision: Literal["hold", "candidate_for_manual_mapping"]
    evidence_url: str = Field(min_length=1, max_length=1000)
    rationale: str = Field(min_length=1, max_length=2000)


class PackageReview(ContractModel):
    input_sha256: Hash
    receipt_sha256: Hash
    records: dict[SourceId, PackageDecision] = Field(max_length=10)


def inspect_gtin(value: object) -> dict:
    syntax = (
        isinstance(value, str)
        and len(value) in (8, 12, 13, 14)
        and value.isascii()
        and value.isdecimal()
    )
    checksum = None
    if syntax:
        weighted_sum = sum(
            int(digit) * (3 if index % 2 == 0 else 1)
            for index, digit in enumerate(reversed(value[:-1]))
        )
        checksum = int(value[-1]) == (-weighted_sum) % 10
    nonzero = bool(syntax and any(digit != "0" for digit in value))
    usable = bool(syntax and checksum and nonzero)
    return {
        "value": value if isinstance(value, str) and len(value) <= 64 else None,
        "syntax_valid": syntax,
        "check_digit_valid": checksum,
        "nonzero_identifier": nonzero,
        "structurally_usable": usable,
        # Comparison representation only; preserve the source string/type and its leading zeros.
        "comparison_key_14": value.zfill(14) if usable else None,
        "assignment_or_product_authenticity_verified": False,
    }


def reference_count(statement: dict) -> int:
    references = statement.get("references", [])
    if not isinstance(references, list) or any(not isinstance(row, dict) for row in references):
        raise AuditError("statement_references_array_required")
    return len(references)


def requires_context_review(statement: dict) -> bool:
    qualifiers = statement.get("qualifiers", {})
    return not isinstance(qualifiers, dict) or bool(qualifiers)


def gtin_claims(entity: dict) -> tuple[list[dict], int]:
    source = statements(entity, "P3962")
    if len(source) > 100:
        raise AuditError("gtin_statement_limit_exceeded")
    claims, deprecated = [], 0
    for statement in source:
        if statement.get("rank") == "deprecated":
            deprecated += 1
            continue
        snak = statement["mainsnak"]
        data = snak.get("datavalue")
        value = data.get("value") if isinstance(data, dict) else None
        checks = inspect_gtin(value)
        issue = (
            "unsupported_rank"
            if statement.get("rank") not in ("normal", "preferred")
            else "context_requires_review"
            if requires_context_review(statement)
            else "unknown_or_nonstring_statement"
            if snak.get("snaktype") != "value"
            or not isinstance(data, dict)
            or data.get("type") != "string"
            else "invalid_gtin_syntax"
            if not checks["syntax_valid"]
            else "invalid_gtin_check_digit"
            if not checks["check_digit_valid"]
            else "all_zero_identifier"
            if not checks["nonzero_identifier"]
            else None
        )
        statement_id = statement.get("id")
        claims.append(
            {
                **checks,
                "statement_id": statement_id
                if isinstance(statement_id, str) and len(statement_id) <= 128
                else None,
                "reference_entries": reference_count(statement),
                "issue": issue,
                "usable_without_context": issue is None,
            }
        )
    return claims, deprecated


def container_signals(entity: dict) -> tuple[list[str], list[str]]:
    containers, issues = set(), set()
    for statement in statements(entity, "P31"):
        if statement.get("rank") == "deprecated":
            continue
        ids = set(item_ids({"claims": {"P31": [statement]}}, "P31")) & CONTAINER_CLASSES
        if not ids:
            continue
        snak = statement["mainsnak"]
        data = snak.get("datavalue")
        if requires_context_review(statement):
            issues.add("container_context_requires_review")
        elif (
            statement.get("rank") not in ("normal", "preferred")
            or snak.get("snaktype") != "value"
            or not isinstance(data, dict)
            or data.get("type") != "wikibase-entityid"
        ):
            issues.add("container_statement_requires_review")
        else:
            containers.update(ids)
    return sorted(containers), sorted(issues)


def package_quantities(entity: dict, record: dict) -> tuple[dict, list[str]]:
    values, issues = {}, []
    for field, prop in (("abv_percent", "P2665"), ("volume_ml", "P2234")):
        units = ABV_UNITS if prop == "P2665" else VOLUME_UNITS
        allowed_units = {
            f"{scheme}://www.wikidata.org/entity/{unit}"
            for scheme in ("http", "https")
            for unit in units
        }
        malformed = False
        for statement in statements(entity, prop):
            if statement.get("rank") == "deprecated":
                continue
            snak = statement["mainsnak"]
            data = snak.get("datavalue")
            value = data.get("value") if isinstance(data, dict) else None
            if (
                statement.get("rank") not in ("normal", "preferred")
                or snak.get("snaktype") != "value"
                or not isinstance(data, dict)
                or data.get("type") != "quantity"
                or not isinstance(value, dict)
                or not isinstance(value.get("unit"), str)
                or value["unit"] not in allowed_units
                or requires_context_review(statement)
            ):
                malformed = True
        # The existing scalar normalizer handles units, bounds, multiplicity and range. Its
        # older permissive rank/type handling is not sufficient evidence for package identity.
        values[field] = None if malformed else record[field]
        if malformed:
            issues.append(f"{field}_statement_requires_review")
    return values, issues


def audit_packages(
    payload: dict,
    records: list[dict],
    hashes: dict,
    evidence_kind: str,
    review: PackageReview | None = None,
) -> tuple[dict, list[dict]]:
    if review is not None and (
        review.input_sha256 != hashes["input_sha256"]
        or review.receipt_sha256 != hashes["receipt_sha256"]
    ):
        raise AuditError("package_review_snapshot_hash_mismatch")
    rows, identifiers = [], defaultdict(set)
    for record in records:
        qid = record["source_record_id"]
        entity = payload["entities"][qid]
        claims, deprecated = gtin_claims(entity)
        usable = [claim for claim in claims if claim["usable_without_context"]]
        unique = {claim["comparison_key_14"] for claim in usable}
        containers, holds = container_signals(entity)
        quantities, quantity_issues = package_quantities(entity, record)
        holds.extend(quantity_issues)
        if record["label"] is None:
            holds.append("label_unknown")
        if len(unique) != 1 or any(not claim["usable_without_context"] for claim in claims):
            holds.append("single_unambiguous_gtin_required")
        if quantities["volume_ml"] is None:
            holds.append("volume_unknown")
        if quantities["abv_percent"] is None:
            holds.append("abv_unknown")
        if not containers:
            holds.append("explicit_container_type_unknown")
        if containers and BRAND_CLASS in record["instance_of_ids"]:
            holds.append("mixed_brand_and_container_types")
        warnings = []
        if any(claim["reference_entries"] == 0 for claim in usable):
            warnings.append("unreferenced_gtin_statement")
        row = {
            **record,
            **quantities,
            "brand_ids": item_ids(entity, "P1716"),
            "gtin_claims": claims,
            "deprecated_gtin_statements": deprecated,
            "explicit_container_class_ids": containers,
            "package_field_combination_present": bool(
                len(unique) == 1
                and all(claim["usable_without_context"] for claim in claims)
                and containers
                and record["label"] is not None
                and quantities["volume_ml"] is not None
                and quantities["abv_percent"] is not None
            ),
            "package_count": None,
            "considered_quantity_reference_entries": {
                field: sum(
                    reference_count(statement)
                    for statement in statements(entity, prop)
                    if statement.get("rank") != "deprecated"
                )
                for field, prop in (("abv_percent", "P2665"), ("volume_ml", "P2234"))
            },
            "hold_reasons": holds,
            "warnings": warnings,
            "manual_review": "not_performed",
            "backend_product_id": None,
            "backend_mapping_approved": False,
            "feature_fit_eligible": False,
        }
        for key in unique:
            identifiers[key].add(qid)
        rows.append(row)
    if review is not None and set(review.records) - {row["source_record_id"] for row in rows}:
        raise AuditError("package_review_references_unknown_entity")
    for row in rows:
        if any(
            len(identifiers[claim["comparison_key_14"]]) > 1
            for claim in row["gtin_claims"]
            if claim["usable_without_context"]
        ):
            row["hold_reasons"].append("identifier_shared_across_source_items")
        decision = None if review is None else review.records.get(row["source_record_id"])
        if decision is not None:
            if decision.evidence_url != row["source_url"]:
                raise AuditError("package_review_requires_exact_source_revision_url")
            if decision.decision == "candidate_for_manual_mapping" and row["hold_reasons"]:
                raise AuditError("manual_candidate_conflicts_with_source_hold")
            row["manual_review"] = decision.decision
            row["review_rationale"] = decision.rationale
    report = {
        "schema_version": 1,
        "algorithm": "package-identity-audit-v1",
        "audit_kind": "source_package_identity_not_sku_approval",
        "evidence_kind": evidence_kind,
        "hashes": hashes,
        "entities": len(rows),
        "active_gtin_claims": sum(len(row["gtin_claims"]) for row in rows),
        "checksum_valid_claims": sum(
            claim["check_digit_valid"] is True for row in rows for claim in row["gtin_claims"]
        ),
        "unambiguous_identifier_entities": sum(
            len(
                {
                    claim["comparison_key_14"]
                    for claim in row["gtin_claims"]
                    if claim["usable_without_context"]
                }
            )
            == 1
            and not any(claim["issue"] for claim in row["gtin_claims"])
            for row in rows
        ),
        "package_field_combination_entities": sum(
            row["package_field_combination_present"] for row in rows
        ),
        "hold_reasons": dict(
            sorted(Counter(reason for row in rows for reason in row["hold_reasons"]).items())
        ),
        "manual_decisions": dict(sorted(Counter(row["manual_review"] for row in rows).items())),
        "shared_identifier_groups": sum(len(ids) > 1 for ids in identifiers.values()),
        "backend_mappings_approved": 0,
        "feature_fit_promotions": 0,
        "limitations": [
            "discovery_success_and_checksum_not_gs1_assignment_or_authenticity_verification",
            "same_item_fields_do_not_establish_pack_count_variant_or_legal_sale_eligibility",
            "manufacturer_pack_count_and_missing_fields_not_inferred",
            "no_backend_id_registration_catalog_fit_or_recommendation_quality_claim",
        ],
    }
    return report, rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "input", "receipt", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--review", type=Path)
    parser.add_argument(
        "--evidence-kind",
        choices=["reviewed_public_source", "authored_regression_fixture"],
        required=True,
    )
    args = parser.parse_args()
    try:
        if ".pubburi" not in args.output_dir.resolve().parts:
            raise AuditError("package_outputs_require_private_pubburi_directory")
        manifest_data, manifest_hash = read_json(args.manifest)
        manifest = SourceManifest.model_validate(manifest_data)
        if (
            manifest.source_id != "wikidata-structured"
            or manifest.license_label != "CC0-1.0"
            or not manifest.local_structured_normalization
        ):
            raise AuditError("source_package_normalization_not_approved")
        payload, input_hash = read_json(args.input)
        receipt, receipt_hash = read_json(args.receipt)
        manifest_model_hash = hashlib.sha256(manifest.model_dump_json().encode()).hexdigest()
        records = verify_collection_snapshot(receipt, payload, input_hash, manifest_model_hash)
        review_data, review_hash = (None, None) if args.review is None else read_json(args.review)
        review = None if review_data is None else PackageReview.model_validate(review_data)
        hashes = {
            "manifest_sha256": manifest_hash,
            "input_sha256": input_hash,
            "receipt_sha256": receipt_hash,
            "review_sha256": review_hash,
        }
        report, rows = audit_packages(payload, records, hashes, args.evidence_kind, review)
        args.output_dir.mkdir(parents=True, exist_ok=False)
        write_receipt(
            args.output_dir, {"mode": "offline_package_identity_audit", "completed": False}
        )
        (args.output_dir / "package-records.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (args.output_dir / "audit-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        write_receipt(
            args.output_dir,
            {
                "mode": "offline_package_identity_audit",
                "completed": True,
                "hashes": hashes,
                "backend_mappings_approved": False,
                "feature_fit_promotions": False,
            },
        )
        print(
            json.dumps(
                {
                    key: report[key]
                    for key in (
                        "entities",
                        "checksum_valid_claims",
                        "package_field_combination_entities",
                        "backend_mappings_approved",
                        "feature_fit_promotions",
                    )
                }
            )
        )
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        reason = str(error) if isinstance(error, AuditError) else type(error).__name__
        print(f"Package identity audit failed: {reason}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
