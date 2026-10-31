"""Inventory legacy demo products/media locally; no SQL execution or training approval."""

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import unicodedata
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import Field

from pubburi_recommendation.baseline import ContractModel
from pubburi_recommendation.catalog_audit import MAX_INPUT_BYTES, AuditError, read_json
from pubburi_recommendation.seed_sql import extract_products

MAX_ASSET_BYTES = 20 * 1024 * 1024
MAX_TOTAL_ASSET_BYTES = 128 * 1024 * 1024


class LegacyManifest(ContractModel):
    schema_version: Literal[1]
    source_id: Literal["pubburi-legacy-demo-seed"]
    reviewed_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    source_refs: list[str] = Field(min_length=1, max_length=10)
    decision: Literal["local_inventory_only_pending_record_and_media_evidence"]
    structured_feature_fit_approved: Literal[False]
    public_redistribution_approved: Literal[False]
    image_reuse_or_training_approved: Literal[False]
    notes: list[str] = Field(min_length=1, max_length=20)


def fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def mapped_asset_name(reference: str | None) -> str | None:
    """Mirror the current basename/pub mapping; reject other namespaces and path traversal."""
    if not isinstance(reference, str) or not reference:
        return None
    if reference.startswith("/images/pub/"):
        reference = reference[len("/images/pub/") :]
    if (
        not reference
        or reference in {".", ".."}
        or any(character in reference for character in "/\\:%?#")
        or any(ord(character) < 32 for character in reference)
    ):
        return None
    return re.sub(r"\.(?:png|jpe?g)$", ".webp", reference, flags=re.I)


def asset_entry(directory_fd: int, name: str, remaining_budget: int) -> tuple[dict, int]:
    entry = {"name": name, "status": "not_regular_file", "sha256": None, "bytes": None}
    bytes_read = 0
    try:
        mode = os.stat(name, dir_fd=directory_fd, follow_symlinks=False).st_mode
        if stat.S_ISLNK(mode):
            entry["status"] = "symlink_blocked"
            return entry, bytes_read
        if not stat.S_ISREG(mode):
            return entry, bytes_read
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
        try:
            # Directory fd + NOFOLLOW keep root/leaf replacement from escaping the inventory.
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode):
                raise AuditError("asset_changed_to_non_regular_file")
            if before.st_size > MAX_ASSET_BYTES:
                entry["status"] = "oversized_blocked"
                return entry, bytes_read
            if before.st_size > remaining_budget:
                raise AuditError("asset_inventory_exceeds_128_mib")
            # Charge actual reads, including rejected/changed files; a stale size cannot bypass cap.
            read_limit = min(MAX_ASSET_BYTES + 1, remaining_budget)
            chunks = []
            while bytes_read < read_limit:
                chunk = os.read(descriptor, min(64 * 1024, read_limit - bytes_read))
                if not chunk:
                    break
                bytes_read += len(chunk)
                chunks.append(chunk)
            after = os.fstat(descriptor)
            if bytes_read > MAX_ASSET_BYTES or after.st_size > MAX_ASSET_BYTES:
                entry["status"] = "oversized_blocked"
                return entry, bytes_read
            if (
                before.st_size != after.st_size
                or before.st_mtime_ns != after.st_mtime_ns
                or before.st_ctime_ns != after.st_ctime_ns
                or bytes_read != after.st_size
            ):
                raise AuditError("asset_changed_while_reading")
            content = b"".join(chunks)
        finally:
            os.close(descriptor)
        extension = Path(name).suffix.lower().lstrip(".")
        signature = (
            "webp"
            if content[:4] == b"RIFF" and content[8:12] == b"WEBP"
            else "png"
            if content.startswith(b"\x89PNG\r\n\x1a\n")
            else "jpeg"
            if content.startswith(b"\xff\xd8\xff")
            else "unknown"
        )
        entry.update(
            status="read",
            sha256=hashlib.sha256(content).hexdigest(),
            bytes=len(content),
            extension=extension,
            signature=signature,
            signature_matches_extension=signature != "unknown"
            and signature == ("jpeg" if extension == "jpg" else extension),
        )
    except OSError:
        entry["status"] = "unreadable_blocked"
    return entry, bytes_read


def file_inventory(directory: Path) -> tuple[list[dict], str]:
    try:
        directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as error:
        raise AuditError("asset_root_must_be_real_directory") from error
    try:
        names = sorted(os.listdir(directory_fd))
        if len(names) > 2000:
            raise AuditError("asset_inventory_exceeds_2000_entries")
        inventory = []
        total_bytes = 0
        for name in names:
            entry, bytes_read = asset_entry(directory_fd, name, MAX_TOTAL_ASSET_BYTES - total_bytes)
            total_bytes += bytes_read
            if total_bytes > MAX_TOTAL_ASSET_BYTES:
                raise AuditError("asset_inventory_exceeds_128_mib")
            inventory.append(entry)
        return inventory, fingerprint(inventory)
    finally:
        os.close(directory_fd)


def string_value(value, maximum: int) -> str | None:
    return value.strip() if isinstance(value, str) and 0 < len(value.strip()) <= maximum else None


def numeric_value(value, maximum: int, *, integer: bool) -> int | float | None:
    if not isinstance(value, Decimal) or not value.is_finite() or not 0 <= value <= maximum:
        return None
    if integer:
        return int(value) if value == value.to_integral_value() else None
    converted = float(value)
    return None if value != 0 and converted == 0 else converted


def duplicate_summary(values: list[str]) -> dict:
    counts = Counter(values)
    repeated = [count for count in counts.values() if count > 1]
    return {
        "duplicate_groups": len(repeated),
        "affected_rows": sum(repeated),
        "extra_rows": sum(count - 1 for count in repeated),
    }


def canonical_decimal(value: Decimal) -> str:
    # Decimal.normalize() can round through the caller's precision context; do not use it here.
    if value == 0:
        return "0"
    formatted = format(value, "f")
    return formatted.rstrip("0").rstrip(".") if "." in formatted else formatted


def audit_seed(sql: str, sql_sha256: str, inventory: list[dict], inventory_sha256: str) -> tuple:
    products, inserts = extract_products(sql)
    assets = {entry["name"]: entry for entry in inventory}
    records = []
    for position, product in enumerate(products, 1):
        seed_values = {
            key: {"sql_literal_type": "decimal", "value": str(value)}
            if isinstance(value, Decimal)
            else value
            for key, value in product.items()
        }
        row_fingerprint = fingerprint(
            {
                key: {"sql_literal_type": "decimal", "value": canonical_decimal(value)}
                if isinstance(value, Decimal)
                else value
                for key, value in product.items()
            }
        )
        fields = {
            "name": string_value(product["name"], 100),
            "category": string_value(product["type"], 20),
            "demo_price_krw": numeric_value(product["price"], 2_147_483_647, integer=True),
            "unverified_abv_percent": numeric_value(product["abv"], 100, integer=False),
            "demo_order_count": numeric_value(product["order_count"], 2_147_483_647, integer=True),
        }
        issues = [f"missing_or_invalid:{field}" for field, value in fields.items() if value is None]
        source_name = string_value(product["img"], 100)
        mapped_name = mapped_asset_name(source_name)
        if mapped_name is None:
            issues.append("image_reference_missing_or_unsupported_path")
        mapped_asset = assets.get(mapped_name)
        source_basename = (
            source_name.removeprefix("/images/pub/") if mapped_name is not None else None
        )
        source_asset = assets.get(source_basename)
        if mapped_name is not None and (mapped_asset is None or mapped_asset["status"] != "read"):
            issues.append("mapped_image_missing_or_blocked")
        if (
            mapped_asset is not None
            and mapped_asset["status"] == "read"
            and not mapped_asset["signature_matches_extension"]
        ):
            issues.append("mapped_image_signature_mismatch")
        records.append(
            {
                "seed_row_ordinal": position,  # Not an existing database ID or a verified SKU ID.
                "seed_row_fingerprint": row_fingerprint,
                "seed_values": seed_values,
                **fields,
                "image_reference": source_name,
                "mapped_asset_name": mapped_name,
                "mapped_asset_status": None if mapped_asset is None else mapped_asset["status"],
                "mapped_asset_sha256": None if mapped_asset is None else mapped_asset["sha256"],
                "source_asset_sha256": None if source_asset is None else source_asset["sha256"],
                "backend_product_id": None,
                "verified_sku_group": None,
                "verified_volume_ml": None,
                "verified_category": None,
                "verified_abv_percent": None,
                "taste_tags": None,
                "aroma_tags": None,
                "actual_price_krw": None,
                "observed_popularity": None,
                "identity_review": "unreviewed_legacy_demo_entry",
                "structured_field_evidence": "not_supplied_by_supported_legacy_literal_contract",
                "image_rights_evidence": "not_supplied_by_supported_legacy_literal_contract",
                "feature_fit_eligible": False,
                "quarantine_reasons": [
                    "record_identity_and_field_evidence_unverified",
                    "image_usage_rights_unverified",
                ],
                "issues": issues,
            }
        )
    used_assets = {record["mapped_asset_name"] for record in records if record["mapped_asset_name"]}
    hashes = defaultdict(list)
    for asset in inventory:
        if asset["sha256"] is not None:
            hashes[asset["sha256"]].append(asset["name"])
    report = {
        "schema_version": 1,
        "source_id": "pubburi-legacy-demo-seed",
        "sql_sha256": sql_sha256,
        "asset_inventory_sha256": inventory_sha256,
        "grain": "active_literal_insert_row_not_verified_sku_or_existing_database_id",
        "active_product_insert_statements": inserts,
        "product_rows": len(records),
        "valid_seed_literal_values": {
            field: sum(record[field] is not None for record in records)
            for field in (
                "name",
                "category",
                "demo_price_krw",
                "unverified_abv_percent",
                "demo_order_count",
            )
        },
        "category_rows": dict(
            sorted(Counter(record["category"] or "unknown" for record in records).items())
        ),
        "exact_duplicate_rows": duplicate_summary(
            [record["seed_row_fingerprint"] for record in records]
        ),
        "normalized_name_duplicates": duplicate_summary(
            [
                " ".join(unicodedata.normalize("NFKC", record["name"]).casefold().split())
                for record in records
                if record["name"] is not None
            ]
        ),
        "shared_mapped_asset_references": duplicate_summary(
            [record["mapped_asset_name"] for record in records if record["mapped_asset_name"]]
        ),
        "asset_files_read": sum(asset["status"] == "read" for asset in inventory),
        "asset_status_counts": dict(
            sorted(Counter(asset["status"] for asset in inventory).items())
        ),
        "unused_read_assets": sum(
            asset["status"] == "read" and asset["name"] not in used_assets for asset in inventory
        ),
        "byte_identical_asset_groups": sum(len(names) > 1 for names in hashes.values()),
        "mapped_images_readable": sum(
            record["mapped_asset_status"] == "read" for record in records
        ),
        "source_reference_files_readable": sum(
            record["source_asset_sha256"] is not None for record in records
        ),
        "row_issue_counts": dict(
            sorted(Counter(issue for record in records for issue in record["issues"]).items())
        ),
        "unverified": {
            field: sum(record[field] is None for record in records)
            for field in (
                "backend_product_id",
                "verified_sku_group",
                "verified_volume_ml",
                "verified_category",
                "verified_abv_percent",
                "taste_tags",
                "aroma_tags",
                "actual_price_krw",
                "observed_popularity",
            )
        },
        "record_identity_or_field_evidence_unverified": len(records),
        "referenced_image_rights_unverified": len(used_assets),
        "feature_fit_eligible_rows": 0,
        "limitations": [
            "repository_provenance_not_per_record_or_media_permission",
            "seed_literals_not_observed_product_truth_or_popularity",
            "name_volume_or_abv_text_not_parsed_into_verified_features",
            "asset_hash_or_signature_not_visual_identity_or_license_validation",
            "no_database_access_export_training_or_publication",
        ],
    }
    return report, records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--sql", type=Path, required=True)
    parser.add_argument("--assets-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = LegacyManifest.model_validate(read_json(args.manifest)[0])
        if ".pubburi" not in args.output_dir.resolve().parts:
            raise AuditError("outputs_must_be_inside_private_pubburi_directory")
        if args.output_dir.exists():
            raise AuditError("existing_audit_must_be_preserved")
        with args.sql.open("rb") as source:
            content = source.read(MAX_INPUT_BYTES + 1)
        if len(content) > MAX_INPUT_BYTES:
            raise AuditError("seed_exceeds_10_mib")
        sql_hash = hashlib.sha256(content).hexdigest()
        inventory, inventory_hash = file_inventory(args.assets_dir)
        report, records = audit_seed(content.decode("utf-8"), sql_hash, inventory, inventory_hash)
        report["manifest_sha256"] = fingerprint(manifest.model_dump(mode="json"))
        args.output_dir.mkdir(parents=True, exist_ok=False)
        for name, value in {
            "audit-report.json": report,
            "quarantined-products.json": records,
            "asset-inventory.json": inventory,
        }.items():
            (args.output_dir / name).write_text(
                json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        print(json.dumps(report, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        reason = str(error) if isinstance(error, AuditError) else type(error).__name__
        print(f"Legacy seed audit failed: {reason}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
