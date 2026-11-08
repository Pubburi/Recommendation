"""Compile reviewed aT facts for a pinned local catalog, without business state or network."""

import argparse
import contextlib
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, StringConstraints, ValidationError, field_validator, model_validator

from pubburi_recommendation.at_source import Hash, audit_at_source
from pubburi_recommendation.baseline import ContractModel
from pubburi_recommendation.catalog_audit import AuditError, SourceManifest, read_json

ALGORITHM = "at-reviewed-local-catalog-v1"
SOURCE_URL = "https://www.data.go.kr/data/15048755/fileData.do?recommendDataYn=Y"
LOCAL_POLICY = (
    "Project policy permits reviewed structured facts for noncommercial local display and fit "
    "through at-reviewed-local-catalog-v1; explicit Backend identity mapping and current state "
    "remain separate. This records project scope, not newly granted publisher rights."
)
CATEGORIES = {"약주": "약 · 청주", "탁주": "탁주", "과실주": "과실주", "증류주": "증류주"}
Key = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9._:-]{0,127}$")]
Text = Annotated[str, StringConstraints(min_length=1, max_length=1000)]


def utc_time(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError("at_catalog_requires_utc")
    return parsed


class SelectedRow(ContractModel):
    catalog_record_id: Key
    source_row_number: int = Field(ge=1, le=10_000)
    source_variant_group: Key


def unique_records(records):
    for key in ("catalog_record_id", "source_row_number"):
        values = [getattr(row, key) for row in records]
        if len(set(values)) != len(values):
            raise ValueError("at_catalog_requires_unique_record_ids_and_rows")


class VersionedContract(ContractModel):
    schema_version: Literal[1]

    @field_validator("schema_version", mode="before")
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int:
            raise ValueError("at_catalog_version_requires_integer")
        return value


class CatalogSelection(VersionedContract):
    algorithm: Literal["at-local-catalog-selection-v1"]
    catalog_version: Key
    reviewed_at_utc: str
    input_sha256: Hash
    receipt_sha256: Hash
    manifest_sha256: Hash
    review_sha256: Hash
    records: list[SelectedRow] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def reviewed_selection(self):
        utc_time(self.reviewed_at_utc)
        unique_records(self.records)
        return self


class CatalogSource(ContractModel):
    source_id: Literal["at-traditional-liquor"]
    dataset_id: Literal["15048755"]
    source_version: str = Field(pattern=r"^\d{8}$")
    evidence_kind: Literal["operator_public_download_receipt", "authored_regression_fixture"]
    captured_at_utc: str
    input_sha256: Hash
    receipt_sha256: Hash
    manifest_sha256: Hash
    review_sha256: Hash
    selection_sha256: Hash


class CatalogLicense(ContractModel):
    label: Literal["portal-unrestricted-with-additional-notes"]
    purpose: Literal["noncommercial_local_structured_display_and_fit"]
    attribution: Literal["한국농수산식품유통공사(aT) 전통주정보"]
    source_url: Literal[SOURCE_URL]
    raw_redistribution: Literal[False]
    source_media_included: Literal[False]
    free_text_included: Literal[False]

    @field_validator(
        "raw_redistribution", "source_media_included", "free_text_included", mode="before"
    )
    @classmethod
    def boolean_flag(cls, value):
        if type(value) is not bool:
            raise ValueError("at_catalog_license_flag_requires_boolean")
        return value


class CatalogFacts(ContractModel):
    label: Text
    producer_name: Text
    source_category: Literal["약주", "탁주", "과실주", "증류주"]
    category: Literal["약 · 청주", "탁주", "과실주", "증류주"]
    abv_percent: float = Field(ge=0, le=100, allow_inf_nan=False)
    volume_ml: int = Field(ge=1, le=1_000_000)
    gtin: None
    taste_tags: None
    aroma_tags: None
    image_url: None
    description: None

    @model_validator(mode="after")
    def explicit_category_map(self):
        if CATEGORIES[self.source_category] != self.category:
            raise ValueError("at_catalog_category_mapping_mismatch")
        if not self.label.strip() or not self.producer_name.strip():
            raise ValueError("at_catalog_requires_named_product_and_producer")
        return self


class CatalogEvidence(ContractModel):
    url: str = Field(min_length=1, max_length=2000)
    sha256: Hash

    @model_validator(mode="after")
    def same_provider(self):
        url = urlsplit(self.url)
        if (
            url.scheme != "https"
            or url.hostname != "thesool.com"
            or url.username is not None
            or url.password is not None
            or url.port is not None
            or url.path != "/front/publication/M000000066/view.do"
        ):
            raise ValueError("at_catalog_requires_same_provider_evidence")
        return self


class CatalogRecord(SelectedRow):
    source_record_id: str
    facts: CatalogFacts
    evidence: CatalogEvidence


class AtLocalCatalog(VersionedContract):
    algorithm: Literal["at-reviewed-local-catalog-v1"]
    scope: Literal["REVIEWED_LOCAL_CATALOG"]
    catalog_version: Key
    reviewed_at_utc: str
    source: CatalogSource
    license: CatalogLicense
    records: list[CatalogRecord] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def exact_authority(self):
        unique_records(self.records)
        if utc_time(self.source.captured_at_utc) > utc_time(self.reviewed_at_utc):
            raise ValueError("at_catalog_review_precedes_capture")
        datetime.strptime(self.source.source_version, "%Y%m%d")
        for row in self.records:
            expected = f"at:15048755:{self.source.input_sha256}:row:{row.source_row_number}"
            if row.source_record_id != expected:
                raise ValueError("at_catalog_source_identity_mismatch")
        return self


def compile_catalog(manifest_path, input_path, receipt_path, review_path, selection_path, evidence):
    """Recheck original bytes and explicit rows; never infer IDs, stock or sensory facts."""
    manifest_data, manifest_hash = read_json(manifest_path)
    manifest = SourceManifest.model_validate(manifest_data)
    if (
        manifest.source_id != "at-traditional-liquor"
        or manifest.provider != "한국농수산식품유통공사"
        or manifest.source_url != SOURCE_URL
        or manifest.license_label != "portal-unrestricted-with-additional-notes"
        or not manifest.local_structured_normalization
        or not manifest.structured_feature_fit
        or LOCAL_POLICY not in manifest.additional_conditions
    ):
        raise AuditError("at_local_catalog_project_scope_not_reviewed")
    selected_data, selection_hash = read_json(selection_path)
    selection = CatalogSelection.model_validate(selected_data)
    report, rows, receipt = audit_at_source(
        manifest_hash, input_path, receipt_path, review_path, evidence
    )
    for key in ("input_sha256", "receipt_sha256", "manifest_sha256", "review_sha256"):
        if getattr(selection, key) != report[key]:
            raise AuditError("at_catalog_selection_authority_mismatch")
    reviewed = {row["source_row_number"] for row in rows if row["review_evidence"] is not None}
    if reviewed != {row.source_row_number for row in selection.records}:
        raise AuditError("at_catalog_selection_requires_exact_reviewed_rows")
    by_row = {row["source_row_number"]: row for row in rows}
    records = []
    for chosen in selection.records:
        row = by_row[chosen.source_row_number]
        if any(
            row[key] is None for key in ("producer_name", "category", "abv_percent", "volume_ml")
        ):
            raise AuditError("at_catalog_requires_reviewed_single_container_facts")
        if row["category"] not in CATEGORIES:
            raise AuditError("at_catalog_category_not_supported")
        facts = {key: row[key] for key in ("label", "producer_name", "abv_percent", "volume_ml")}
        facts.update(
            source_category=row["category"],
            category=CATEGORIES[row["category"]],
            gtin=None,
            taste_tags=None,
            aroma_tags=None,
            image_url=None,
            description=None,
        )
        records.append(
            {
                **chosen.model_dump(),
                "source_record_id": row["source_record_id"],
                "facts": facts,
                "evidence": {key: row["review_evidence"][key] for key in ("url", "sha256")},
            }
        )
    return AtLocalCatalog.model_validate(
        {
            "schema_version": 1,
            "algorithm": ALGORITHM,
            "scope": "REVIEWED_LOCAL_CATALOG",
            "catalog_version": selection.catalog_version,
            "reviewed_at_utc": selection.reviewed_at_utc,
            "source": {
                "source_id": manifest.source_id,
                "dataset_id": receipt.dataset_id,
                "source_version": receipt.source_version,
                "evidence_kind": receipt.evidence_kind,
                "captured_at_utc": receipt.observed_at_utc,
                **{
                    key: report[key]
                    for key in (
                        "input_sha256",
                        "receipt_sha256",
                        "manifest_sha256",
                        "review_sha256",
                    )
                },
                "selection_sha256": selection_hash,
            },
            "license": {
                "label": manifest.license_label,
                "purpose": "noncommercial_local_structured_display_and_fit",
                "attribution": "한국농수산식품유통공사(aT) 전통주정보",
                "source_url": SOURCE_URL,
                "raw_redistribution": False,
                "source_media_included": False,
                "free_text_included": False,
            },
            "records": records,
        }
    )


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def publish_catalog(args):
    output = args.output_dir
    if ".pubburi" not in output.resolve().parts or output.exists() or output.is_symlink():
        raise AuditError("at_catalog_requires_new_private_output")

    def load():
        result = compile_catalog(
            args.manifest, args.input, args.receipt, args.review, args.selection, args.fact_evidence
        )
        if utc_time(result.reviewed_at_utc) > datetime.now(UTC):
            raise AuditError("at_catalog_review_is_in_future")
        return result.model_dump(mode="json")

    first = load()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    target, pending = output / "catalog-authority.json", output / "catalog-authority.json.pending"

    def receipt(value):
        path = output / "receipt.json"
        path.write_bytes(encoded(value))
        os.chmod(path, 0o600)

    receipt({"algorithm": ALGORITHM, "completed": False})
    try:
        data = encoded(first)
        with pending.open("xb") as stream:
            os.chmod(pending, 0o600)
            stream.write(data)
        if load() != first:
            raise AuditError("at_catalog_inputs_changed_during_publication")
        os.link(pending, target)
        pending.unlink()
        result = {
            "algorithm": ALGORITHM,
            "completed": True,
            "authority_sha256": hashlib.sha256(data).hexdigest(),
            "records": len(first["records"]),
        }
        receipt(result)
        return result
    except (AuditError, ValidationError, OSError, ValueError, KeyError):
        with contextlib.suppress(OSError):
            target.unlink(missing_ok=True)
            receipt({"algorithm": ALGORITHM, "completed": False})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "input", "receipt", "review", "selection", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--fact-evidence", type=Path, action="append", default=[])
    args = parser.parse_args()
    try:
        result = publish_catalog(args)
    except (AuditError, ValidationError, OSError, ValueError, KeyError) as error:
        message = (
            str(error) if isinstance(error, AuditError) else "invalid_at_catalog_input_or_write"
        )
        print("aT local catalog failed: " + message, file=sys.stderr)
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
