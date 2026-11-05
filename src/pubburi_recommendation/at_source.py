"""Fact-only aT CSV input; source rows are never business IDs or verified SKUs."""

import csv
import hashlib
import io
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, StringConstraints, model_validator

from pubburi_recommendation.baseline import ContractModel
from pubburi_recommendation.catalog_audit import MAX_INPUT_BYTES, AuditError, read_json

ALGORITHM = "at-reviewed-source-facts-v1"
HEADERS = (
    "제품명",
    "제품소개",
    "알콜도수1",
    "알콜도수2",
    "알콜도수3",
    "용량1",
    "용량2",
    "용량3",
    "성분1",
    "성분2",
    "특이사항",
    "특징",
    "양조장",
    "양조장주소",
    "홈페이지주소",
    "수상내역",
)
Hash = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
FactText = Annotated[str, StringConstraints(min_length=1, max_length=1000)]


class AtReceipt(ContractModel):
    schema_version: Literal[1]
    evidence_kind: Literal["operator_public_download_receipt", "authored_regression_fixture"]
    dataset_id: Literal["15048755"]
    source_version: str = Field(pattern=r"^\d{8}$")
    observed_at_utc: str
    source_sha256: Hash
    source_bytes: int = Field(ge=1, le=MAX_INPUT_BYTES)
    http_status: Literal[200]
    normal_public_rate_guard_passed: Literal[True]
    images_fetched: Literal[False]

    @model_validator(mode="after")
    def utc_capture(self):
        captured = datetime.fromisoformat(self.observed_at_utc)
        if captured.tzinfo is None or captured.utcoffset() != UTC.utcoffset(captured):
            raise ValueError("at_capture_requires_utc")
        datetime.strptime(self.source_version, "%Y%m%d")
        return self


class AtRowReview(ContractModel):
    row_number: int = Field(ge=1, le=10_000)
    expected_label: FactText
    expected_producer: FactText | None
    category: str | None = Field(default=None, min_length=1, max_length=64)
    abv_percent: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    abv_unit: Literal["%"] | None = None
    evidence_url: str = Field(max_length=2000)
    evidence_sha256: Hash
    review_note: FactText

    @model_validator(mode="after")
    def explicit_provider_facts(self):
        url = urlsplit(self.evidence_url)
        if (
            url.scheme != "https"
            or url.hostname != "thesool.com"
            or url.username is not None
            or url.password is not None
            or url.port is not None
            or url.path != "/front/publication/M000000066/view.do"
        ):
            raise ValueError("at_review_requires_same_provider_publication")
        if (self.abv_percent is None) != (self.abv_unit is None):
            raise ValueError("at_reviewed_abv_requires_explicit_percent_unit")
        if self.category is None and self.abv_percent is None:
            raise ValueError("at_review_requires_an_explicit_feature_fact")
        return self


class AtReview(ContractModel):
    schema_version: Literal[1]
    algorithm: Literal["at-reviewed-source-facts-v1"]
    input_sha256: Hash
    receipt_sha256: Hash
    manifest_sha256: Hash
    source_version: str = Field(pattern=r"^\d{8}$")
    records: list[AtRowReview] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_rows(self):
        if len({row.row_number for row in self.records}) != len(self.records):
            raise ValueError("at_review_rows_must_be_unique")
        return self


def bounded_bytes(path: Path) -> bytes:
    with path.open("rb") as source:
        content = source.read(MAX_INPUT_BYTES + 1)
    if len(content) > MAX_INPUT_BYTES:
        raise AuditError("input_exceeds_10_mib")
    return content


def normalize_at_csv(
    content: bytes,
    receipt: AtReceipt,
    *,
    manifest_hash: str,
    receipt_hash: str,
    review: AtReview | None = None,
    evidence_hashes: set[str] = frozenset(),
) -> tuple[dict, list[dict], None]:
    input_hash = hashlib.sha256(content).hexdigest()
    if len(content) > MAX_INPUT_BYTES:
        raise AuditError("input_exceeds_10_mib")
    if receipt.source_sha256 != input_hash or receipt.source_bytes != len(content):
        raise AuditError("at_receipt_source_bytes_mismatch")
    try:
        text = content.decode("cp949", errors="strict")
        if "\x00" in text:
            raise ValueError("nul")
        rows = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except (UnicodeError, ValueError, csv.Error) as error:
        raise AuditError("at_invalid_cp949_csv") from error
    if not rows or tuple(rows[0]) != HEADERS:
        raise AuditError("at_exact_16_column_header_required")
    rows = rows[1:]
    if not 1 <= len(rows) <= 10_000 or any(len(row) != len(HEADERS) for row in rows):
        raise AuditError("at_row_count_or_width_invalid")
    if any(not row[0].strip() for row in rows):
        raise AuditError("at_product_label_required")
    identities = Counter((row[0], row[12]) for row in rows)
    duplicates = Counter(tuple(row) for row in rows)
    selected = {}
    if review is not None:
        if (
            review.input_sha256 != input_hash
            or review.receipt_sha256 != receipt_hash
            or review.manifest_sha256 != manifest_hash
            or review.source_version != receipt.source_version
        ):
            raise AuditError("at_review_snapshot_hash_or_version_mismatch")
        selected = {row.row_number: row for row in review.records}
        if any(number > len(rows) for number in selected):
            raise AuditError("at_review_references_missing_row")
    records = []
    for number, row in enumerate(rows, 1):
        producer = row[12] if row[12].strip() else None
        if len(row[0]) > 1000 or (producer is not None and len(producer) > 1000):
            raise AuditError("at_factual_text_exceeds_limit")
        facts = selected.get(number)
        ambiguous = identities[row[0], row[12]] > 1
        if facts is not None:
            if row[0] != facts.expected_label or producer != facts.expected_producer:
                raise AuditError("at_review_label_or_producer_mismatch")
            if ambiguous:
                raise AuditError("at_duplicate_identity_cannot_be_curated")
            if facts.evidence_sha256 not in evidence_hashes:
                raise AuditError("at_provider_evidence_bytes_mismatch")
            if facts.abv_percent is not None:
                try:
                    # No positional pairing or dataset-wide unit inference. Only this manually
                    # reviewed, single-valued CSV field may agree with a provider's explicit %.
                    value = Decimal(row[2])
                    matches = value.is_finite() and value == Decimal(str(facts.abv_percent))
                except InvalidOperation:
                    matches = False
                if not matches or any(value.strip() for value in row[3:5]):
                    raise AuditError("at_reviewed_abv_requires_matching_single_source_value")
        records.append(
            {
                "source_record_id": f"at:15048755:{input_hash}:row:{number}",
                "source_row_number": number,
                "source_version": receipt.source_version,
                "entity_kind": "unverified_source_product_record",
                "label": row[0],
                "producer_name": producer,
                "category": None if facts is None else facts.category,
                "abv_percent": None if facts is None else facts.abv_percent,
                "volume_ml": None,
                "taste_tags": None,
                "aroma_tags": None,
                "raw_abv_values": row[2:5],
                "raw_volume_values": row[5:8],
                "duplicate_identity": ambiguous,
                "review_evidence": None
                if facts is None
                else {
                    "url": facts.evidence_url,
                    "sha256": facts.evidence_sha256,
                    "note": facts.review_note,
                },
                "backend_product_id": None,
                "sku_group": None,
                "availability": "unknown",
                "price_krw": None,
                "service_feature_fit_eligible": False,
            }
        )
    report = {
        "algorithm": ALGORITHM,
        "source_id": "at-traditional-liquor",
        "grain": "versioned_source_csv_row_not_sku",
        "source_version": receipt.source_version,
        "input_sha256": input_hash,
        "receipt_sha256": receipt_hash,
        "manifest_sha256": manifest_hash,
        "encoding": "cp949-strict",
        "records": len(records),
        "reviewed_rows": len(selected),
        "duplicate_whole_rows": sum(count - 1 for count in duplicates.values()),
        "ambiguous_identity_rows": sum(identities[row[0], row[12]] > 1 for row in rows),
        "known": {
            name: sum(row[name] is not None for row in records)
            for name in ("label", "producer_name", "category", "abv_percent", "volume_ml")
        },
        "multiple_abv_rows": sum(sum(bool(v.strip()) for v in row[2:5]) > 1 for row in rows),
        "multiple_volume_rows": sum(sum(bool(v.strip()) for v in row[5:8]) > 1 for row in rows),
        "b0_demo_exported": 0,
        "b1_wire_exports": 0,
        "raw_or_creative_text_redistribution": False,
    }
    return report, records, None


def audit_at_source(manifest_hash, input_path, receipt_path, review_path, evidence_paths):
    if receipt_path is None:
        raise AuditError("at_public_download_receipt_required")
    receipt_data, receipt_hash = read_json(receipt_path)
    receipt = AtReceipt.model_validate(receipt_data)
    review_data, review_hash = (None, None) if review_path is None else read_json(review_path)
    review = None if review_data is None else AtReview.model_validate(review_data)
    evidence_hashes = {hashlib.sha256(bounded_bytes(path)).hexdigest() for path in evidence_paths}
    report, records, request = normalize_at_csv(
        bounded_bytes(input_path),
        receipt,
        manifest_hash=manifest_hash,
        receipt_hash=receipt_hash,
        review=review,
        evidence_hashes=evidence_hashes,
    )
    report.update(review_sha256=review_hash, fact_evidence_sha256=sorted(evidence_hashes))
    return report, records, request
