"""Lightweight consistency gate for an already collected structured snapshot."""

from pubburi_recommendation.catalog_audit import QID, AuditError
from pubburi_recommendation.wikidata_collect import check_payload


def verify_collection_snapshot(
    receipt: dict, payload: dict, input_hash: str, manifest_model_hash: str
) -> list[dict]:
    requested = receipt.get("requested_ids")
    revisions = receipt.get("revisions")
    mode = receipt.get("mode")
    if (
        type(receipt.get("schema_version")) is not int
        or receipt["schema_version"] != 1
        or receipt.get("accepted") is not True
        or receipt.get("error_code") is not None
        or mode not in ("live_get", "offline_replay")
        or (
            mode == "live_get"
            and (type(receipt.get("http_status")) is not int or receipt["http_status"] != 200)
        )
        or (mode == "offline_replay" and receipt.get("http_status") is not None)
        or receipt.get("structured_data_license") != "CC0-1.0"
        or receipt.get("response_sha256") != input_hash
        or receipt.get("manifest_sha256") != manifest_model_hash
        or not isinstance(requested, list)
        or not 1 <= len(requested) <= 10
        or any(
            not isinstance(qid, str) or len(qid) > 32 or not QID.fullmatch(qid) for qid in requested
        )
        or len(set(requested)) != len(requested)
        or not isinstance(revisions, dict)
        or any(type(value) is not int or value < 1 for value in revisions.values())
    ):
        raise AuditError("accepted_matching_source_receipt_required")
    records = check_payload(payload, requested)
    expected = {row["source_record_id"]: row["source_revision"] for row in records}
    if revisions != expected:
        raise AuditError("accepted_matching_source_receipt_required")
    return records
