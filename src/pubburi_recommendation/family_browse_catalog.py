"""Reviewed source families for owned offline browse DEMOs, never physical SKU approval."""

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from pubburi_recommendation.baseline import Abv, ContractModel
from pubburi_recommendation.catalog_audit import (
    AuditError,
    ReviewManifest,
    SourceManifest,
    audit,
    read_json,
)
from pubburi_recommendation.collection_snapshot import verify_collection_snapshot
from pubburi_recommendation.package_identity_audit import Hash, SourceId
from pubburi_recommendation.source_catalog import Key, Note
from pubburi_recommendation.wikidata_collect import write_receipt

ALGORITHM = "reviewed-source-family-browse-demo-v1"
AT_ALGORITHM = "reviewed-at-named-browse-demo-v1"
SCOPE = "reviewed_source_family_browse_demo_only"


class FamilyBrowseFacts(ContractModel):
    source_revision: int = Field(ge=1)
    label: str = Field(min_length=1, max_length=1000)
    label_language: Literal["ko", "en", "mul"]
    instance_of_ids: list[SourceId] = Field(min_length=1, max_length=64)
    producer_ids: list[SourceId] = Field(min_length=1, max_length=64)
    abv_percent: Abv
    volume_ml: None

    @model_validator(mode="after")
    def exact_relations(self) -> Self:
        for values in (self.instance_of_ids, self.producer_ids):
            if values != sorted(set(values)):
                raise ValueError("family_browse_relations_must_be_sorted_unique")
        return self


class FamilyBrowseSelection(ContractModel):
    catalog_record_id: Key
    source_variant_group: Key
    identity_scope: Literal["reviewed_source_family_browse_demo_only"]
    checked_facts: FamilyBrowseFacts
    review_note: Note


class FamilyBrowseCuration(ContractModel):
    schema_version: Literal[1]
    algorithm: Literal["reviewed-source-family-browse-demo-v1"]
    evidence_kind: Literal["reviewed_public_source", "authored_regression_fixture"]
    input_sha256: Hash
    receipt_sha256: Hash
    manifest_sha256: Hash
    review_sha256: Hash
    catalog_version: Key
    reviewed_at_utc: str = Field(min_length=20, max_length=40)
    records: dict[SourceId, FamilyBrowseSelection] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def explicit_unique_families(self) -> Self:
        reviewed = datetime.fromisoformat(self.reviewed_at_utc)
        if reviewed.tzinfo is None or reviewed.utcoffset() != UTC.utcoffset(reviewed):
            raise ValueError("family_browse_review_requires_utc")
        for field in ("catalog_record_id", "source_variant_group"):
            values = [getattr(row, field) for row in self.records.values()]
            if len(values) != len(set(values)):
                raise ValueError("family_browse_keys_and_groups_must_be_unique")
        return self


class AtBrowseFacts(ContractModel):
    source_row_number: int = Field(ge=1, le=10_000)
    source_version: str = Field(pattern=r"^\d{8}$")
    label: str = Field(min_length=1, max_length=1000)
    producer_name: str = Field(min_length=1, max_length=1000)
    category: str = Field(min_length=1, max_length=64)
    abv_percent: Abv
    volume_ml: None


class AtBrowseSelection(FamilyBrowseSelection):
    checked_facts: AtBrowseFacts


class AtBrowseCuration(FamilyBrowseCuration):
    algorithm: Literal["reviewed-at-named-browse-demo-v1"]
    records: dict[
        Annotated[
            str, StringConstraints(pattern=r"^at:15048755:[0-9a-f]{64}:row:[1-9][0-9]{0,4}$")
        ],
        AtBrowseSelection,
    ] = Field(min_length=1, max_length=10)
    # Local evidence copies beside the curation, never fetched URLs or arbitrary paths.
    fact_evidence_files: list[
        Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")]
    ] = Field(min_length=1, max_length=10)


def load_at_browse_catalog(
    manifest, manifest_hash, input_path, receipt_path, curation_path, review_path
):
    from pubburi_recommendation.at_source import audit_at_source

    if (
        manifest.license_label != "portal-unrestricted-with-additional-notes"
        or not manifest.local_structured_normalization
        or not manifest.structured_feature_fit
    ):
        raise AuditError("at_browse_source_not_approved")
    data, curation_hash = read_json(curation_path)
    curation = AtBrowseCuration.model_validate(data)
    if datetime.fromisoformat(curation.reviewed_at_utc) > datetime.now(UTC):
        raise AuditError("family_browse_review_must_not_be_future")
    evidence = [curation_path.parent / name for name in curation.fact_evidence_files]
    if any(path.resolve().parent != curation_path.parent.resolve() for path in evidence):
        raise AuditError("at_browse_evidence_requires_local_files")
    audited, normalized, receipt = audit_at_source(
        manifest_hash, input_path, receipt_path, review_path, evidence
    )
    hashes = {
        name: audited[name]
        for name in ("manifest_sha256", "input_sha256", "receipt_sha256", "review_sha256")
    }
    if any(getattr(curation, name) != value for name, value in hashes.items()):
        raise AuditError("family_browse_authority_hash_mismatch")
    # The evidence kind must come from the same receipt bytes as the audited hash.
    kind = (
        "authored_regression_fixture"
        if receipt.evidence_kind == "authored_regression_fixture"
        else "reviewed_public_source"
    )
    if curation.evidence_kind != kind:
        raise AuditError("at_browse_receipt_evidence_kind_mismatch")
    hashes["curation_sha256"] = curation_hash
    by_id = {row["source_record_id"]: row for row in normalized}
    records = []
    for source_key, selected in sorted(curation.records.items()):
        row = by_id.get(source_key)
        if row is None or row["review_evidence"] is None or row["duplicate_identity"]:
            raise AuditError("at_browse_requires_individually_reviewed_source_row")
        facts = selected.checked_facts
        if any(row[name] != value for name, value in facts.model_dump().items()):
            raise AuditError("at_browse_facts_conflict_with_reviewed_source")
        if (
            selected.catalog_record_id
            != f"at-browse-{facts.source_version}-row{facts.source_row_number}"
        ):
            raise AuditError("at_browse_catalog_key_requires_bound_version_and_row")
        provenance = {
            "source_id": manifest.source_id,
            "source_record_id": source_key,
            "source_grain": "named_csv_product_record_not_verified_sku",
            "source_version": facts.source_version,
            "source_row_number": facts.source_row_number,
            "source_url": manifest.source_url,
            "input_sha256": hashes["input_sha256"],
            "license": manifest.license_label,
        }
        reviewed = {**provenance, "provider_evidence": row["review_evidence"]}
        records.append(
            {
                "catalog_record_id": selected.catalog_record_id,
                "source_variant_group": selected.source_variant_group,
                "identity_scope": SCOPE,
                "source": provenance,
                "facts": {
                    name: getattr(facts, name)
                    for name in ("label", "category", "abv_percent", "volume_ml")
                },
                "field_provenance": {
                    "label": {**provenance, "csv_column": "제품명"},
                    "producer_name": {**provenance, "csv_column": "양조장"},
                    "category": {
                        **reviewed,
                        "authority": "explicit_same_provider_manual_fact_review",
                    },
                    "abv_percent": {**reviewed, "csv_column": "알콜도수1", "source_unit": "%"},
                    "volume_ml": {**provenance, "status": "unknown_not_variant_or_unit_approved"},
                },
                "reviewed_source_facts": facts.model_dump(),
                "source_issues": [],
                "review_note": selected.review_note,
                "unknown": dict.fromkeys(
                    (
                        "gtin",
                        "container",
                        "pack_count",
                        "taste_tags",
                        "aroma_tags",
                        "price_krw",
                        "availability",
                    )
                ),
                "physical_sku_or_service_catalog_approved": False,
            }
        )
    catalog = {
        "schema_version": 1,
        "algorithm": ALGORITHM,
        "data_kind": SCOPE,
        "evidence_kind": kind,
        "catalog_version": curation.catalog_version,
        "hashes": hashes,
        "records": records,
    }
    return catalog, {
        "algorithm": AT_ALGORITHM,
        "scope": SCOPE,
        "hashes": hashes,
        "source_grain": "named_csv_product_record_not_verified_sku",
        "source_items": len(normalized),
        "selected_named_records": len(records),
        "physical_sku_or_service_catalog_approved": False,
        "business_mapping": "requires_explicit_owned_family_browse_demo_snapshot_and_mapping",
    }


def load_family_browse_catalog(manifest_path, input_path, receipt_path, curation_path, review_path):
    manifest_data, manifest_hash = read_json(manifest_path)
    manifest = SourceManifest.model_validate(manifest_data)
    if manifest.source_id == "at-traditional-liquor":
        return load_at_browse_catalog(
            manifest, manifest_hash, input_path, receipt_path, curation_path, review_path
        )
    if (
        manifest.source_id != "wikidata-structured"
        or manifest.license_label != "CC0-1.0"
        or not manifest.local_structured_normalization
        or not manifest.structured_feature_fit
    ):
        raise AuditError("family_browse_source_not_approved")
    payload, input_hash = read_json(input_path)
    receipt, receipt_hash = read_json(receipt_path)
    review_data, review_hash = read_json(review_path)
    curation_data, curation_hash = read_json(curation_path)
    curation = FamilyBrowseCuration.model_validate(curation_data)
    hashes = dict(
        manifest_sha256=manifest_hash,
        input_sha256=input_hash,
        receipt_sha256=receipt_hash,
        review_sha256=review_hash,
        curation_sha256=curation_hash,
    )
    if any(
        getattr(curation, name) != value
        for name, value in hashes.items()
        if name != "curation_sha256"
    ):
        raise AuditError("family_browse_authority_hash_mismatch")
    if datetime.fromisoformat(curation.reviewed_at_utc) > datetime.now(UTC):
        raise AuditError("family_browse_review_must_not_be_future")
    verify_collection_snapshot(
        receipt,
        payload,
        input_hash,
        hashlib.sha256(manifest.model_dump_json().encode()).hexdigest(),
    )
    _, normalized, _ = audit(payload, input_hash, ReviewManifest.model_validate(review_data))
    by_id = {row["source_record_id"]: row for row in normalized}
    records = []
    for qid, selected in sorted(curation.records.items()):
        row = by_id.get(qid)
        if row is None or row["entity_kind"] != "product_family":
            raise AuditError("family_browse_requires_reviewed_product_family")
        facts = selected.checked_facts
        if any(row[name] != value for name, value in facts.model_dump().items()):
            raise AuditError("family_browse_facts_conflict_with_reviewed_source")
        # Explicit contradictory/qualified/ambiguous source facts cannot become honest absence.
        if any(issue.startswith(("abv:", "instance_of:", "producer:")) for issue in row["issues"]):
            raise AuditError("family_browse_source_facts_require_review")
        provenance = {
            "source_id": row["source_id"],
            "source_record_id": qid,
            "source_revision": row["source_revision"],
            "source_url": row["source_url"],
            "input_sha256": input_hash,
            "license": "CC0-1.0",
        }
        records.append(
            {
                "catalog_record_id": selected.catalog_record_id,
                "source_variant_group": selected.source_variant_group,
                "identity_scope": SCOPE,
                "source": provenance,
                "facts": {
                    "label": facts.label,
                    "abv_percent": facts.abv_percent,
                    "volume_ml": None,
                },
                "field_provenance": {
                    "label": {**provenance, "property": "labels:" + facts.label_language},
                    "abv_percent": {**provenance, "property": "P2665", "normalized_unit": "vol%"},
                    "instance_of_ids": {**provenance, "property": "P31"},
                    "producer_ids": {**provenance, "property": "P176"},
                    "volume_ml": {**provenance, "property": "P2234", "status": "unknown"},
                },
                "reviewed_source_facts": facts.model_dump(),
                "source_issues": row["issues"],
                "review_note": selected.review_note,
                "unknown": {
                    "gtin": None,
                    "container": None,
                    "pack_count": None,
                    "taste_tags": None,
                    "aroma_tags": None,
                    "price_krw": None,
                    "availability": None,
                },
                "physical_sku_or_service_catalog_approved": False,
            }
        )
    catalog = {
        "schema_version": 1,
        "algorithm": ALGORITHM,
        "data_kind": SCOPE,
        "evidence_kind": curation.evidence_kind,
        "catalog_version": curation.catalog_version,
        "hashes": hashes,
        "records": records,
    }
    report = {
        "algorithm": ALGORITHM,
        "scope": SCOPE,
        "hashes": hashes,
        "source_items": len(normalized),
        "selected_families": len(records),
        "physical_sku_or_service_catalog_approved": False,
        "business_mapping": "requires_explicit_owned_family_browse_demo_snapshot_and_mapping",
    }
    return catalog, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "input", "receipt", "curation", "review", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        if ".pubburi" not in args.output_dir.resolve().parts or args.output_dir.exists():
            raise AuditError("family_browse_requires_new_private_output_directory")
        catalog, report = load_family_browse_catalog(
            args.manifest, args.input, args.receipt, args.curation, args.review
        )
        args.output_dir.mkdir(parents=True, exist_ok=False)
        write_receipt(args.output_dir, {"algorithm": ALGORITHM, "completed": False})
        for name, value in (("source-catalog.json", catalog), ("curation-report.json", report)):
            (args.output_dir / name).write_text(
                json.dumps(value, ensure_ascii=False, indent=2) + "\n"
            )
        write_receipt(
            args.output_dir,
            {"algorithm": ALGORITHM, "completed": True, "hashes": catalog["hashes"]},
        )
        selected_kind = (
            "selected_named_records" if "selected_named_records" in report else "selected_families"
        )
        print(json.dumps({"scope": SCOPE, selected_kind: len(catalog["records"])}))
        return 0
    except (OSError, ValueError, TypeError, KeyError):
        print("family_browse_preparation_failed", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
