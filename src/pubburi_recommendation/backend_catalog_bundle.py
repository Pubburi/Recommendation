"""Publish a fresh checked DEMO catalog for an explicitly pinned Backend consumer."""

import argparse
import contextlib
import hashlib
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, model_validator

from pubburi_recommendation.baseline import ContractModel, ProductId
from pubburi_recommendation.business_export import (
    FAMILY_SCOPE,
    MAX_AGE_SECONDS,
    BusinessFeatures,
    BusinessProduct,
    BusinessSnapshot,
    SuccessfulResponse,
    utc_time,
)
from pubburi_recommendation.catalog_audit import MAX_INPUT_BYTES, AuditError, read_json
from pubburi_recommendation.checked_export import EXPORT_FILES, export_bytes, load_checked_export
from pubburi_recommendation.content_contracts import ContentProduct, GroupId, validate_catalog
from pubburi_recommendation.package_identity_audit import Hash
from pubburi_recommendation.source_catalog import Key
from pubburi_recommendation.wikidata_collect import write_receipt

ALGORITHM = "checked-backend-demo-bundle-v1"


class DemoFlags(ContractModel):
    service_catalog_approved: bool
    model_loaded: bool
    current_business_revalidation_required: bool

    @model_validator(mode="after")
    def demo_only(self):
        if (
            self.service_catalog_approved
            or self.model_loaded
            or not self.current_business_revalidation_required
        ):
            raise ValueError("bundle_requires_unpromoted_demo_and_current_revalidation")
        return self


class CheckedMetadata(DemoFlags):
    algorithm: Literal["checked-reviewed-demo-export-v1"]
    mode: Literal["fresh_demo_snapshot"]
    checked_at_utc: str = Field(min_length=20, max_length=40)
    original_export_at_utc: str = Field(min_length=20, max_length=40)
    snapshot_origin: Literal[
        "demo_fixture", "owned_demo_fixture", "existing_local_catalog", "owned_family_browse_demo"
    ]
    data_scope: Literal[
        "reviewed_mapped_business_demo_only", "reviewed_source_family_browse_demo_only"
    ]
    evidence_kind: Literal["authored_regression_fixture", "reviewed_public_source"]
    source_catalog_sha256: Hash
    business_snapshot_sha256: Hash
    mapping_sha256: Hash
    artifact_sha256: dict[str, Hash]

    @model_validator(mode="after")
    def completed_artifact_binding(self):
        if set(self.artifact_sha256) != EXPORT_FILES:
            raise ValueError("bundle_requires_all_four_checked_artifact_hashes")
        if utc_time(self.original_export_at_utc) > utc_time(self.checked_at_utc):
            raise ValueError("bundle_export_must_not_follow_check")
        return self


class BundleRecord(ContractModel):
    catalog_record_id: Key
    backend_product_id: ProductId
    sku_group: GroupId
    price_kind: Literal["demo_snapshot_krw"]
    eligibility_scope: Literal[
        "public_browse_row_exists", "reviewed_source_family_browse_demo_only"
    ]
    product: SuccessfulResponse[BusinessProduct]
    features: SuccessfulResponse[BusinessFeatures]


class BackendCatalogBundle(DemoFlags):
    schema_version: Literal[1]
    algorithm: Literal["checked-backend-demo-bundle-v1"]
    catalog: list[ContentProduct] = Field(min_length=1, max_length=1000)
    records: list[BundleRecord] = Field(min_length=1, max_length=1000)
    checked_export: CheckedMetadata
    valid_until_utc: str = Field(min_length=20, max_length=40)

    @model_validator(mode="after")
    def exact_catalog_binding(self):
        validate_catalog(self.catalog)
        if [p.product_id for p in self.catalog] != [r.backend_product_id for r in self.records]:
            raise ValueError("bundle_records_must_follow_exact_catalog_ids_and_order")
        if len({r.catalog_record_id for r in self.records}) != len(self.records):
            raise ValueError("bundle_source_keys_must_be_unique")
        family = self.checked_export.data_scope == FAMILY_SCOPE
        for product, row in zip(self.catalog, self.records, strict=True):
            source, features = row.product.data, row.features.data
            if (
                source.id != row.backend_product_id
                or features.productId != row.backend_product_id
                or product.sku_group != row.sku_group
                or product.category != source.type
                or product.price_krw != source.price
                or product.abv_percent != source.abv
                or product.volume_ml != features.volumeMl
                or product.taste_tags is not None
                or product.aroma_tags is not None
                or row.eligibility_scope != (FAMILY_SCOPE if family else "public_browse_row_exists")
            ):
                raise ValueError("bundle_catalog_and_reviewed_business_record_conflict")
        seconds = (
            utc_time(self.valid_until_utc) - utc_time(self.checked_export.checked_at_utc)
        ).total_seconds()
        if not 0 < seconds <= MAX_AGE_SECONDS:
            raise ValueError("bundle_validity_requires_remaining_original_snapshot_budget")
        return self


def build_bundle(checked, snapshot_path: Path):
    snapshot_data, snapshot_hash = read_json(snapshot_path)
    if snapshot_hash != checked.metadata["business_snapshot_sha256"]:
        raise AuditError("bundle_business_snapshot_changed_after_check")
    snapshot = BusinessSnapshot.model_validate(snapshot_data)
    business = {row["product"]["data"]["id"]: row for row in snapshot_data["records"]}
    mapping = {row.backend_product_id: row for row in checked.mapping.records}
    records = []
    for product in checked.request.catalog:
        row = mapping[product.product_id]
        raw = business[product.product_id]
        records.append(
            dict(
                catalog_record_id=row.catalog_record_id,
                backend_product_id=row.backend_product_id,
                sku_group=row.source_variant_group,
                price_kind=row.price_kind,
                eligibility_scope=row.eligibility_scope,
                product=raw["product"],
                features=raw["features"],
            )
        )
    value = dict(
        schema_version=1,
        algorithm=ALGORITHM,
        catalog=checked.request.model_dump()["catalog"],
        records=records,
        checked_export=checked.metadata,
        service_catalog_approved=False,
        model_loaded=False,
        current_business_revalidation_required=True,
        valid_until_utc=(
            utc_time(snapshot.capture_finished_at_utc) + timedelta(seconds=MAX_AGE_SECONDS)
        ).isoformat(),
    )
    BackendCatalogBundle.model_validate(value)
    # Return original parsed response objects: DTO validation must not rewrite
    # numeric spellings, null/[] or source strings used in the original hashes.
    if len(export_bytes(value)) > MAX_INPUT_BYTES:
        raise AuditError("backend_bundle_exceeds_ten_mib")
    return value


def utc_now():
    return datetime.now(UTC)


def publish_bundle(args):
    output = args.output_dir
    if ".pubburi" not in output.resolve().parts or output.exists() or output.is_symlink():
        raise AuditError("backend_bundle_requires_new_private_output")

    def load():
        return load_checked_export(
            args.export_dir,
            args.manifest,
            args.input,
            args.source_receipt,
            args.curation,
            args.business_snapshot,
            args.mapping,
            family_review=args.family_review,
            now=utc_now(),
        )

    first = load()
    initial = build_bundle(first, args.business_snapshot)
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    pending, target = output / "catalog-bundle.json.pending", output / "catalog-bundle.json"
    published = False
    try:
        write_receipt(output, {"algorithm": ALGORITHM, "completed": False})
        os.chmod(output / "receipt.json", 0o600)
        with pending.open("xb") as stream:
            os.chmod(pending, 0o600)
            stream.write(export_bytes(initial))
        final = load()
        for key in (
            "artifact_sha256",
            "source_catalog_sha256",
            "business_snapshot_sha256",
            "mapping_sha256",
        ):
            if first.metadata[key] != final.metadata[key]:
                raise AuditError("backend_bundle_inputs_changed_during_publication")
        bundle = build_bundle(final, args.business_snapshot)
        data = export_bytes(bundle)
        pending.write_bytes(data)
        if utc_now() >= utc_time(bundle["valid_until_utc"]):
            raise AuditError("backend_bundle_expired_before_completion")
        # No replacement of an unexpected target, even inside our new private directory.
        os.link(pending, target)
        published = True
        pending.unlink()
        receipt = {
            "algorithm": ALGORITHM,
            "completed": True,
            "bundle_sha256": hashlib.sha256(data).hexdigest(),
            "records": len(bundle["records"]),
            "valid_until_utc": bundle["valid_until_utc"],
        }
        if utc_now() >= utc_time(bundle["valid_until_utc"]):
            raise AuditError("backend_bundle_expired_before_completion")
        write_receipt(output, receipt)
        return receipt
    except (AuditError, ValidationError, OSError, ValueError, KeyError):
        if published:
            with contextlib.suppress(OSError):
                target.unlink(missing_ok=True)
        with contextlib.suppress(OSError):
            write_receipt(output, {"algorithm": ALGORITHM, "completed": False})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "export-dir",
        "manifest",
        "input",
        "source-receipt",
        "curation",
        "business-snapshot",
        "mapping",
        "output-dir",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--family-review", type=Path)
    args = parser.parse_args()
    try:
        receipt = publish_bundle(args)
    except (AuditError, ValidationError, OSError, ValueError, KeyError) as error:
        message = (
            str(error) if isinstance(error, AuditError) else "invalid_backend_bundle_input_or_write"
        )
        print("Backend catalog bundle failed: " + message, file=sys.stderr)
        return 2
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
