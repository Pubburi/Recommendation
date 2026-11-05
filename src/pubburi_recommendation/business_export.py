"""Export reviewed source-to-business mappings for offline demo requests, never live sales."""

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from pubburi_recommendation.baseline import (
    Abv,
    Category,
    ContractModel,
    Price,
    ProductId,
    RecommendationRequest,
)
from pubburi_recommendation.catalog_audit import AuditError, read_json
from pubburi_recommendation.catalog_authority import load_export_catalog
from pubburi_recommendation.content_api import ContentRecommendationRequest
from pubburi_recommendation.content_contracts import ContentProduct
from pubburi_recommendation.package_identity_audit import Hash
from pubburi_recommendation.source_catalog import Key, Note
from pubburi_recommendation.wikidata_collect import write_receipt

ALGORITHM = "reviewed-business-demo-export-v1"
FAMILY_SCOPE = "reviewed_source_family_browse_demo_only"
MAX_AGE_SECONDS = 300
MAX_CAPTURE_SECONDS = 60
Tag = Annotated[str, StringConstraints(min_length=1, max_length=40)]


def utc_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError("explicit_utc_timestamp_required")
    return parsed


def content_hash(value: object) -> str:
    """Whole parsed response content, not original HTTP bytes or a server revision."""
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    ).hexdigest()


class BusinessProduct(ContractModel):
    id: ProductId
    name: str = Field(min_length=1, max_length=1000)
    type: Category
    price: Price
    img: str | None = Field(max_length=1000)
    abv: Abv
    orderCount: int = Field(ge=0, le=2_147_483_647)


class BusinessFeatures(ContractModel):
    productId: ProductId
    volumeMl: int | None = Field(ge=1, le=1_000_000)
    description: str | None = Field(max_length=2000)
    tasteTags: list[Tag] | None = Field(max_length=20)
    aromaTags: list[Tag] | None = Field(max_length=20)
    sourceName: str | None = Field(max_length=200)
    sourceUrl: str | None = Field(max_length=1000)
    sourceNote: str | None = Field(max_length=1000)

    @model_validator(mode="after")
    def known_features_have_source_metadata(self):
        if any(
            value is not None
            for value in (self.volumeMl, self.description, self.tasteTags, self.aromaTags)
        ) and not (self.sourceName and self.sourceName.strip()):
            raise ValueError("known_business_features_require_source_name_not_rights_approval")
        return self


class SuccessfulResponse[T](ContractModel):
    data: T
    message: str = Field(max_length=1000)
    error: None


class SnapshotRecord(ContractModel):
    product: SuccessfulResponse[BusinessProduct]
    features: SuccessfulResponse[BusinessFeatures]


class BusinessSnapshot(ContractModel):
    schema_version: Literal[1]
    snapshot_origin: Literal[
        "demo_fixture", "owned_demo_fixture", "existing_local_catalog", "owned_family_browse_demo"
    ]
    capture_method: Literal["authored", "http_read"]
    capture_started_at_utc: str = Field(min_length=20, max_length=40)
    capture_finished_at_utc: str = Field(min_length=20, max_length=40)
    records: list[SnapshotRecord] = Field(max_length=1000)

    @model_validator(mode="after")
    def coherent_records(self):
        if (self.snapshot_origin == "demo_fixture") != (self.capture_method == "authored"):
            raise ValueError("snapshot_origin_capture_method_mismatch")
        start, finish = (
            utc_time(self.capture_started_at_utc),
            utc_time(self.capture_finished_at_utc),
        )
        if not 0 <= (finish - start).total_seconds() <= MAX_CAPTURE_SECONDS:
            raise ValueError("snapshot_capture_span_requires_0_to_60_seconds")
        ids = [row.product.data.id for row in self.records]
        if len(ids) != len(set(ids)):
            raise ValueError("snapshot_product_ids_must_be_unique")
        if any(row.product.data.id != row.features.data.productId for row in self.records):
            raise ValueError("product_and_features_ids_must_match")
        return self


class MappingRecord(ContractModel):
    catalog_record_id: Key
    backend_product_id: ProductId
    product_response_sha256: Hash
    features_response_sha256: Hash
    source_variant_group: Key
    eligibility_scope: Literal[
        "public_browse_row_exists", "reviewed_source_family_browse_demo_only"
    ]
    demo_browse_eligible: bool
    price_kind: Literal["demo_snapshot_krw"]
    identity_review_note: Note


class ReviewedMapping(ContractModel):
    schema_version: Literal[1]
    algorithm: Literal["reviewed-business-demo-export-v1"]
    source_catalog_sha256: Hash
    business_snapshot_sha256: Hash
    reviewed_at_utc: str = Field(min_length=20, max_length=40)
    records: list[MappingRecord] = Field(max_length=1000)

    @model_validator(mode="after")
    def unique_mappings(self):
        utc_time(self.reviewed_at_utc)
        for name in ("catalog_record_id", "backend_product_id"):
            ids = [getattr(row, name) for row in self.records]
            if len(ids) != len(set(ids)):
                raise ValueError("mapping_source_and_business_ids_must_be_unique")
        return self


def require_fresh(snapshot: BusinessSnapshot, now: datetime) -> None:
    start, finish = (
        utc_time(snapshot.capture_started_at_utc),
        utc_time(snapshot.capture_finished_at_utc),
    )
    if start > now or finish > now or (now - finish).total_seconds() > MAX_AGE_SECONDS:
        raise AuditError("snapshot_future_or_stale_for_demo_export")


def build_exports(
    catalog: dict,
    snapshot_data: dict,
    snapshot_hash: str,
    mapping: ReviewedMapping | None,
    now: datetime,
) -> tuple[dict, dict[str, dict]]:
    snapshot = BusinessSnapshot.model_validate(snapshot_data)
    if (
        utc_time(snapshot.capture_started_at_utc) > now
        or utc_time(snapshot.capture_finished_at_utc) > now
    ):
        raise AuditError("snapshot_future_or_stale_for_demo_export")
    rows = [] if mapping is None else mapping.records
    family_browse = catalog.get("data_kind") == FAMILY_SCOPE
    if family_browse:
        if catalog.get("algorithm") != "reviewed-source-family-browse-demo-v1" or any(
            row.get("identity_scope") != FAMILY_SCOPE for row in catalog["records"]
        ):
            raise AuditError("family_browse_authority_must_not_mix_with_containers")
        required_origin = (
            "demo_fixture"
            if catalog["evidence_kind"] == "authored_regression_fixture"
            else "owned_family_browse_demo"
        )
        if snapshot.snapshot_origin != required_origin:
            raise AuditError("family_browse_requires_owned_offline_demo_origin")
        if not rows or {row.catalog_record_id for row in rows} != {
            row["catalog_record_id"] for row in catalog["records"]
        }:
            raise AuditError("family_browse_requires_complete_explicit_mapping")
    elif (
        catalog.get("algorithm") == "reviewed-source-family-browse-demo-v1"
        or snapshot.snapshot_origin == "owned_family_browse_demo"
        or any(row.get("identity_scope") == FAMILY_SCOPE for row in catalog["records"])
    ):
        raise AuditError("family_browse_authority_must_not_mix_with_containers")
    report = {
        "algorithm": ALGORITHM,
        "source_catalog_sha256": content_hash(catalog),
        "business_snapshot_sha256": snapshot_hash,
        "snapshot_origin": snapshot.snapshot_origin,
        "capture_method": snapshot.capture_method,
        "capture_started_at_utc": snapshot.capture_started_at_utc,
        "capture_finished_at_utc": snapshot.capture_finished_at_utc,
        "snapshot_is_atomic_or_server_revision": False,
        "evaluated_at_utc": now.isoformat(),
        "source_candidates": len(catalog["records"]),
        "business_records": len(snapshot.records),
        "exported_products": 0,
        "status": "no_mapping_provided",
        "mode": "offline_demo_snapshot_only",
        "service_training_or_quality_completed": False,
        "limitations": [
            "content_hashes_and_capture_times_are_not_server_revisions_or_atomic_reads",
            "freshness_is_local_snapshot_policy_not_current_sale_stock_or_transaction_guarantee",
            "consumer_must_recheck_current_business_records_prices_and_hard_constraints",
            "manual_mapping_is_not_inferred_from_source_ids_names_or_row_order",
        ],
    }
    if mapping is not None and (
        mapping.source_catalog_sha256 != report["source_catalog_sha256"]
        or mapping.business_snapshot_sha256 != snapshot_hash
    ):
        raise AuditError("mapping_source_or_business_snapshot_hash_mismatch")
    if not rows:
        return report, {}
    require_fresh(snapshot, now)
    reviewed = utc_time(mapping.reviewed_at_utc)
    if reviewed < utc_time(snapshot.capture_finished_at_utc) or reviewed > now:
        raise AuditError("mapping_review_must_follow_capture_and_not_be_future")
    fixture_source = catalog["evidence_kind"] == "authored_regression_fixture"
    fixture_business = snapshot.snapshot_origin not in (
        "existing_local_catalog",
        "owned_family_browse_demo",
    )
    if fixture_source != fixture_business:
        raise AuditError("fixture_and_public_source_business_origins_must_not_mix")
    sources = {row["catalog_record_id"]: row for row in catalog["records"]}
    business = {
        row.product.data.id: (row, raw)
        for row, raw in zip(snapshot.records, snapshot_data["records"], strict=True)
    }
    exported, provenance = [], []
    for selected in rows:
        source = sources.get(selected.catalog_record_id)
        pair = business.get(selected.backend_product_id)
        if source is None or pair is None:
            raise AuditError("mapping_requires_explicit_known_source_and_business_ids")
        record, raw = pair
        if (
            content_hash(raw["product"]) != selected.product_response_sha256
            or content_hash(raw["features"]) != selected.features_response_sha256
        ):
            raise AuditError("mapping_whole_response_content_hash_mismatch")
        facts = source["facts"]
        if family_browse:
            if (
                facts.get("category") is not None
                and raw["product"]["data"]["type"] != facts["category"]
            ):
                raise AuditError("family_browse_source_and_business_category_conflict")
            if (
                selected.eligibility_scope != FAMILY_SCOPE
                or record.product.data.name != facts["label"]
                or facts["volume_ml"] is not None
                or any(
                    value is not None
                    for value in (
                        record.features.data.volumeMl,
                        record.features.data.description,
                        record.features.data.tasteTags,
                        record.features.data.aromaTags,
                    )
                )
            ):
                raise AuditError("family_browse_scope_or_unknown_fields_conflict")
        elif selected.eligibility_scope != "public_browse_row_exists":
            raise AuditError("container_mapping_scope_must_not_change")
        if (
            selected.source_variant_group != source["source_variant_group"]
            or (not family_browse and record.features.data.volumeMl is None)
            or record.features.data.volumeMl != facts["volume_ml"]
            or record.product.data.abv != facts["abv_percent"]
        ):
            raise AuditError("mapping_group_or_explicit_quantity_conflicts")
        product = record.product.data
        exported.append(
            ContentProduct(
                product_id=product.id,
                available=selected.demo_browse_eligible,
                category=product.type,
                price_krw=product.price,
                abv_percent=facts["abv_percent"],
                volume_ml=record.features.data.volumeMl,
                sku_group=selected.source_variant_group,
                taste_tags=None,
                aroma_tags=None,
            )
        )
        provenance.append(
            {
                "catalog_record_id": selected.catalog_record_id,
                "backend_product_id": product.id,
                "source_variant_group": selected.source_variant_group,
                "product_response_sha256": selected.product_response_sha256,
                "features_response_sha256": selected.features_response_sha256,
                "eligibility_scope": selected.eligibility_scope,
                "price_kind": selected.price_kind,
                "identity_review_note": selected.identity_review_note,
                "source_provenance": source["field_provenance"],
                "category_and_price_authority": (
                    "reviewed_source_category_and_captured_business_demo_price"
                    if facts.get("category") is not None
                    else "captured_business_demo_response"
                ),
                "taste_and_aroma": "source_unknown_preserved_business_tags_and_prose_excluded",
            }
        )
    exported.sort(key=lambda row: row.product_id)
    b1 = ContentRecommendationRequest(catalog=exported).model_dump()
    b0 = RecommendationRequest(
        catalog=[
            {
                name: value
                for name, value in product.model_dump().items()
                if name in {"product_id", "available", "category", "price_krw", "abv_percent"}
            }
            for product in exported
        ]
    ).model_dump()
    report.update(
        {
            "exported_products": len(exported),
            "status": "offline_demo_exported",
            "mapping_provenance": provenance,
            "fixture_contract_validation": fixture_source,
        }
    )
    if family_browse:
        report["data_scope"] = FAMILY_SCOPE
        report["physical_sku_or_service_catalog_approved"] = False
    return report, {"b0-demo-request.json": b0, "b1-demo-request.json": b1}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "manifest",
        "input",
        "source-receipt",
        "curation",
        "business-snapshot",
        "output-dir",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--mapping", type=Path)
    parser.add_argument("--family-review", type=Path)
    args = parser.parse_args()
    try:
        if ".pubburi" not in args.output_dir.resolve().parts:
            raise AuditError("business_exports_require_private_pubburi_directory")
        catalog, _ = load_export_catalog(
            args.manifest,
            args.input,
            args.source_receipt,
            args.curation,
            family_review=args.family_review,
        )
        snapshot_data, snapshot_hash = read_json(args.business_snapshot)
        mapping_data, mapping_hash = (
            (None, None) if args.mapping is None else read_json(args.mapping)
        )
        mapping = None if mapping_data is None else ReviewedMapping.model_validate(mapping_data)
        report, exports = build_exports(
            catalog, snapshot_data, snapshot_hash, mapping, datetime.now(UTC)
        )
        report["mapping_sha256"] = mapping_hash
        args.output_dir.mkdir(parents=True, exist_ok=False)
        write_receipt(args.output_dir, {"algorithm": ALGORITHM, "completed": False})
        for name, value in {"export-report.json": report, **exports}.items():
            (args.output_dir / name).write_text(
                json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        if exports:
            require_fresh(BusinessSnapshot.model_validate(snapshot_data), datetime.now(UTC))
        write_receipt(
            args.output_dir,
            {
                "algorithm": ALGORITHM,
                "completed": True,
                "exported_products": report["exported_products"],
                "snapshot_sha256": snapshot_hash,
                "mapping_sha256": mapping_hash,
            },
        )
        print(
            json.dumps(
                {key: report[key] for key in ("status", "exported_products", "snapshot_origin")}
            )
        )
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        reason = str(error) if isinstance(error, AuditError) else type(error).__name__
        print(f"Reviewed business export failed: {reason}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
