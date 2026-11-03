"""Revalidate a completed offline DEMO export before consuming its exact request bytes."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pubburi_recommendation.business_export import (
    ALGORITHM,
    BusinessSnapshot,
    ReviewedMapping,
    build_exports,
    require_fresh,
    utc_time,
)
from pubburi_recommendation.catalog_audit import (
    MAX_INPUT_BYTES,
    AuditError,
    parse_json_bytes,
    read_json,
)
from pubburi_recommendation.catalog_authority import load_export_catalog
from pubburi_recommendation.content_api import ContentRecommendationRequest

EXPORT_FILES = frozenset(
    ("receipt.json", "export-report.json", "b0-demo-request.json", "b1-demo-request.json")
)


def export_bytes(value):
    """The unchanged business_export writer's exact UTF-8 encoding."""
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


@dataclass(frozen=True)
class CheckedExport:
    request: ContentRecommendationRequest
    mapping: ReviewedMapping
    metadata: dict


def load_checked_export(
    export_dir: Path,
    manifest: Path,
    raw: Path,
    source_receipt: Path,
    curation: Path,
    business_snapshot: Path,
    mapping_path: Path,
    *,
    family_review: Path | None = None,
    replay: bool = False,
    now: datetime | None = None,
) -> CheckedExport:
    """Load no model; rederive authority and compare all four immutable export files.

    Normal mode additionally requires a currently fresh business snapshot. Explicit replay
    validates freshness at the recorded export time and labels the result historical only.
    Neither mode approves a service catalog, sale/stock or current business state.
    """
    now = datetime.now(UTC) if now is None else now
    utc_time(now.isoformat())
    if type(replay) is not bool:
        raise AuditError("checked_export_replay_requires_boolean")
    if export_dir.is_symlink() or not export_dir.is_dir():
        raise AuditError("checked_export_directory_required")
    if {path.name for path in export_dir.iterdir()} != EXPORT_FILES:
        raise AuditError("checked_export_requires_exact_completed_file_set")
    values, hashes, contents = {}, {}, {}
    for name in sorted(EXPORT_FILES):
        path = export_dir / name
        if path.is_symlink() or not path.is_file():
            raise AuditError("checked_export_requires_regular_artifact_files")
        with path.open("rb") as source:
            content = source.read(MAX_INPUT_BYTES + 1)
        values[name], hashes[name] = parse_json_bytes(content)
        contents[name] = content
    receipt = values["receipt.json"]
    if receipt.get("completed") is not True or receipt.get("algorithm") != ALGORITHM:
        raise AuditError("checked_export_completed_receipt_required")
    recorded_time = utc_time(values["export-report.json"]["evaluated_at_utc"])
    if recorded_time > now:
        raise AuditError("checked_export_recorded_time_is_future")
    catalog, _ = load_export_catalog(
        manifest, raw, source_receipt, curation, family_review=family_review
    )
    snapshot, snapshot_hash = read_json(business_snapshot)
    mapping_data, mapping_hash = read_json(mapping_path)
    mapping = ReviewedMapping.model_validate(mapping_data)
    # Even replay must have been a valid, fresh and explicitly mapped export at that
    # recorded time. The timestamp never substitutes for hashes, rights or fact checks.
    report, requests = build_exports(catalog, snapshot, snapshot_hash, mapping, recorded_time)
    if not requests:
        raise AuditError("checked_export_requires_nonempty_reviewed_mapping")
    report["mapping_sha256"] = mapping_hash
    expected_receipt = {
        "algorithm": ALGORITHM,
        "completed": True,
        "exported_products": report["exported_products"],
        "snapshot_sha256": snapshot_hash,
        "mapping_sha256": mapping_hash,
    }
    expected = {"receipt.json": expected_receipt, "export-report.json": report, **requests}
    for name, value in expected.items():
        if contents[name] != export_bytes(value):
            raise AuditError("checked_export_artifact_bytes_conflict")
    if not replay:
        require_fresh(BusinessSnapshot.model_validate(snapshot), now)
    return CheckedExport(
        request=ContentRecommendationRequest.model_validate(requests["b1-demo-request.json"]),
        mapping=mapping,
        metadata={
            "algorithm": "checked-reviewed-demo-export-v1",
            "mode": "historical_demo_replay" if replay else "fresh_demo_snapshot",
            "checked_at_utc": now.isoformat(),
            "original_export_at_utc": recorded_time.isoformat(),
            "snapshot_origin": report["snapshot_origin"],
            "data_scope": report.get("data_scope", "reviewed_mapped_business_demo_only"),
            "evidence_kind": catalog["evidence_kind"],
            "source_catalog_sha256": report["source_catalog_sha256"],
            "business_snapshot_sha256": snapshot_hash,
            "mapping_sha256": mapping_hash,
            "artifact_sha256": hashes,
            "service_catalog_approved": False,
            "model_loaded": False,
            "current_business_revalidation_required": True,
        },
    )
