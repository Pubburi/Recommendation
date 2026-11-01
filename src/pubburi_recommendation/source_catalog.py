"""Curate source container candidates without creating business SKUs or model requests."""

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, StringConstraints, model_validator

from pubburi_recommendation.baseline import ContractModel
from pubburi_recommendation.catalog_audit import AuditError, SourceManifest, read_json
from pubburi_recommendation.collection_snapshot import verify_collection_snapshot
from pubburi_recommendation.package_identity_audit import Hash, SourceId, audit_packages
from pubburi_recommendation.wikidata_collect import write_receipt

ALGORITHM = "source-container-curation-v1"
Key = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9:-]{0,127}$")]
Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class CheckedPackageFacts(ContractModel):
    gtin: str = Field(min_length=8, max_length=14)
    container_class_id: SourceId
    volume_ml: float = Field(gt=0, le=1_000_000, allow_inf_nan=False)
    abv_percent: float = Field(ge=0, le=100, allow_inf_nan=False)


class ContainerSelection(ContractModel):
    catalog_record_id: Key
    source_variant_group: Key
    identity_scope: Literal["single_container_source_candidate"]
    checked_facts: CheckedPackageFacts
    corroboration_url: str = Field(min_length=1, max_length=1000)
    corroboration_publisher: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ]
    review_note: Note
    mixed_type_interpretation: Note | None = None

    @model_validator(mode="after")
    def independent_corroboration_link(self):
        url = urlsplit(self.corroboration_url)
        host = (url.hostname or "").rstrip(".").lower()
        if (
            url.scheme != "https"
            or not host
            or url.username is not None
            or url.password is not None
            or host == "wikidata.org"
            or host.endswith(".wikidata.org")
            or host == "wikimedia.org"
            or host.endswith(".wikimedia.org")
        ):
            raise ValueError("external_https_identity_corroboration_required")
        # This validates a manual review's link shape, not its authority or truth. No fetch.
        return self


class CatalogCuration(ContractModel):
    schema_version: Literal[1]
    algorithm: Literal["source-container-curation-v1"]
    evidence_kind: Literal["reviewed_public_source", "authored_regression_fixture"]
    input_sha256: Hash
    receipt_sha256: Hash
    manifest_sha256: Hash
    catalog_version: Key
    reviewed_at_utc: str = Field(min_length=20, max_length=40)
    records: dict[SourceId, ContainerSelection] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def unique_catalog_keys(self):
        reviewed = datetime.fromisoformat(self.reviewed_at_utc)
        if reviewed.tzinfo is None or reviewed.utcoffset() != UTC.utcoffset(reviewed):
            raise ValueError("curation_review_timestamp_requires_utc")
        keys = [row.catalog_record_id for row in self.records.values()]
        if len(keys) != len(set(keys)):
            raise ValueError("catalog_record_ids_must_be_unique")
        return self


def curate_catalog(
    curation: CatalogCuration, source_records: list[dict], hashes: dict
) -> tuple[dict, dict]:
    for name in ("input_sha256", "receipt_sha256", "manifest_sha256"):
        if getattr(curation, name) != hashes[name]:
            raise AuditError("curation_source_snapshot_hash_mismatch")
    by_id = {row["source_record_id"]: row for row in source_records}
    if set(curation.records) - set(by_id):
        raise AuditError("curation_references_unknown_source_item")
    candidates = []
    for qid, selection in sorted(curation.records.items()):
        source = by_id[qid]
        holds = set(source["hold_reasons"])
        if holds - {"mixed_brand_and_container_types"}:
            raise AuditError("curation_cannot_override_unresolved_source_hold")
        if not source["package_field_combination_present"]:
            raise AuditError("explicit_source_package_fields_required")
        if "mixed_brand_and_container_types" in holds and (
            selection.mixed_type_interpretation is None
            or not selection.mixed_type_interpretation.strip()
        ):
            raise AuditError("mixed_source_types_require_explicit_scoped_interpretation")
        facts = selection.checked_facts
        usable = [claim for claim in source["gtin_claims"] if claim["usable_without_context"]]
        if (
            facts.gtin not in {claim["value"] for claim in usable}
            or facts.container_class_id not in source["explicit_container_class_ids"]
            or facts.volume_ml != source["volume_ml"]
            or facts.abv_percent != source["abv_percent"]
        ):
            raise AuditError("manual_corroboration_conflicts_with_allowed_source_facts")
        provenance = {
            "source_id": source["source_id"],
            "source_record_id": qid,
            "source_revision": source["source_revision"],
            "source_url": source["source_url"],
            "input_sha256": hashes["input_sha256"],
            "license": "CC0-1.0",
        }
        values = {
            "label": (source["label"], "labels:" + source["label_language"]),
            "gtin": (facts.gtin, "P3962"),
            "container_class_id": (facts.container_class_id, "P31"),
            "volume_ml": (source["volume_ml"], "P2234"),
            "abv_percent": (source["abv_percent"], "P2665"),
        }
        candidates.append(
            {
                "catalog_record_id": selection.catalog_record_id,
                "source_variant_group": selection.source_variant_group,
                "identity_scope": selection.identity_scope,
                "source": provenance,
                "facts": {name: value for name, (value, _) in values.items()},
                "field_provenance": {
                    name: {
                        **provenance,
                        "property": prop,
                        "normalized_unit": {"volume_ml": "mL", "abv_percent": "vol%"}.get(name),
                    }
                    for name, (_, prop) in values.items()
                },
                "original_instance_of_ids": source["instance_of_ids"],
                "original_source_holds": source["hold_reasons"],
                "unreviewed_source_producer_ids": source["producer_ids"],
                "scoped_interpretation": selection.mixed_type_interpretation,
                "identity_review": {
                    "corroboration_url": selection.corroboration_url,
                    "publisher": selection.corroboration_publisher,
                    "review_note": selection.review_note,
                    "reviewed_at_utc": curation.reviewed_at_utc,
                    "purpose": "identity_cross_check_only_not_feature_or_license_source",
                },
                "unreviewed_or_unknown": {
                    "manufacturer": None,
                    "pack_count": None,
                    "category": None,
                    "taste_tags": None,
                    "aroma_tags": None,
                    "price_krw": None,
                    "availability": None,
                },
                "backend_product_id": None,
                "backend_mapping_approved": False,
                "service_feature_fit_eligible": False,
            }
        )
    catalog = {
        "schema_version": 1,
        "algorithm": ALGORITHM,
        "data_kind": "reviewed_source_container_candidates",
        "evidence_kind": curation.evidence_kind,
        "catalog_version": curation.catalog_version,
        "hashes": hashes,
        "records": candidates,
    }
    report = {
        "schema_version": 1,
        "algorithm": ALGORITHM,
        "evidence_kind": curation.evidence_kind,
        "hashes": hashes,
        "source_items": len(source_records),
        "selected_source_candidates": len(candidates),
        "unselected_source_items": len(source_records) - len(candidates),
        "source_variant_groups": len(
            {row.source_variant_group for row in curation.records.values()}
        ),
        "mixed_type_scoped_interpretations": sum(
            bool(row["original_source_holds"]) for row in candidates
        ),
        "backend_mappings_approved": 0,
        "b0_wire_exports": 0,
        "b1_wire_exports": 0,
        "service_feature_fit_promotions": 0,
        "mapping_status": "requires_actual_backend_snapshot_and_explicit_mapping",
        "limitations": [
            "source_candidate_string_keys_and_groups_are_not_business_skus_or_backend_ids",
            "manual_link_and_fact_match_do_not_automatically_prove_identity_or_external_rights",
            "original_source_types_and_holds_preserved_not_silently_repaired",
            "no_external_text_image_taste_price_dataset_or_user_relevance_evaluation",
        ],
    }
    return catalog, report


def load_source_catalog(
    manifest_path: Path, input_path: Path, receipt_path: Path, curation_path: Path
) -> tuple[dict, dict]:
    """Recompute the catalog from its authorities; never trust an edited projection alone."""
    manifest_data, manifest_hash = read_json(manifest_path)
    manifest = SourceManifest.model_validate(manifest_data)
    if (
        manifest.source_id != "wikidata-structured"
        or manifest.license_label != "CC0-1.0"
        or not manifest.local_structured_normalization
    ):
        raise AuditError("source_catalog_normalization_not_approved")
    payload, input_hash = read_json(input_path)
    receipt, receipt_hash = read_json(receipt_path)
    model_hash = hashlib.sha256(manifest.model_dump_json().encode()).hexdigest()
    records = verify_collection_snapshot(receipt, payload, input_hash, model_hash)
    curation_data, curation_hash = read_json(curation_path)
    curation = CatalogCuration.model_validate(curation_data)
    hashes = {
        "input_sha256": input_hash,
        "receipt_sha256": receipt_hash,
        "manifest_sha256": manifest_hash,
        "curation_sha256": curation_hash,
    }
    _, source_rows = audit_packages(payload, records, hashes, curation.evidence_kind)
    return curate_catalog(curation, source_rows, hashes)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "input", "receipt", "curation", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        if ".pubburi" not in args.output_dir.resolve().parts:
            raise AuditError("source_catalog_outputs_require_private_pubburi_directory")
        catalog, report = load_source_catalog(
            args.manifest, args.input, args.receipt, args.curation
        )
        args.output_dir.mkdir(parents=True, exist_ok=False)
        write_receipt(args.output_dir, {"algorithm": ALGORITHM, "completed": False})
        for name, value in (("source-catalog.json", catalog), ("curation-report.json", report)):
            (args.output_dir / name).write_text(
                json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        write_receipt(
            args.output_dir,
            {
                "algorithm": ALGORITHM,
                "completed": True,
                "hashes": catalog["hashes"],
                "wire_exports": 0,
            },
        )
        print(
            json.dumps(
                {
                    key: report[key]
                    for key in ("selected_source_candidates", "b0_wire_exports", "b1_wire_exports")
                }
            )
        )
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        reason = str(error) if isinstance(error, AuditError) else type(error).__name__
        print(f"Source catalog curation failed: {reason}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
