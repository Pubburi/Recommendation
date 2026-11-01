"""Preserve reviewed P2234/P518 statement observations, never invent a family volume or SKU."""

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import Counter, defaultdict
from decimal import Decimal, DecimalException
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from pubburi_recommendation.baseline import ContractModel
from pubburi_recommendation.catalog_audit import (
    QID,
    VOLUME_UNITS,
    AuditError,
    ReviewManifest,
    SourceManifest,
    audit,
    read_json,
    statements,
)
from pubburi_recommendation.collection_snapshot import verify_collection_snapshot
from pubburi_recommendation.package_identity_audit import Hash, SourceId, reference_count

Group = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
StatementId = Annotated[str, StringConstraints(pattern=r"^Q[1-9][0-9]*\$[A-Za-z0-9-]{1,90}$")]
Volume = Annotated[str, StringConstraints(pattern=r"^(?:0|[1-9][0-9]{0,6})(?:\.[0-9]{1,20})?$")]


class ContextReview(ContractModel):
    revision: int = Field(ge=1)
    label: str = Field(min_length=1, max_length=1000)
    scope: Literal["volume_context_only"]
    rationale: str = Field(min_length=1, max_length=2000)


class ExpectedObservation(ContractModel):
    source_record_id: SourceId
    context_id: SourceId | None
    volume_ml: Volume | None


class ObservationSpec(ContractModel):
    schema_version: Literal[1]
    evidence_kind: Literal["reviewed_public_source", "authored_regression_fixture"]
    manifest_sha256: Hash
    input_sha256: Hash
    receipt_sha256: Hash
    review_sha256: Hash
    context_input_sha256: Hash
    context_receipt_sha256: Hash
    family_groups: dict[SourceId, Group] = Field(min_length=1, max_length=10)
    source_revisions: dict[SourceId, Annotated[int, Field(ge=1)]]
    contexts: dict[SourceId, ContextReview] = Field(min_length=1, max_length=10)
    expected_observations: dict[StatementId, ExpectedObservation] = Field(max_length=1000)

    @model_validator(mode="after")
    def exact_scope(self):
        if set(self.family_groups) != set(self.source_revisions):
            raise ValueError("exact_family_revision_scope_required")
        for sid, fact in self.expected_observations.items():
            if (
                fact.source_record_id not in self.family_groups
                or not sid.startswith(fact.source_record_id + "$")
                or (fact.context_id is not None and fact.context_id not in self.contexts)
            ):
                raise ValueError("observation_facts_must_reference_reviewed_scope")
        return self


def decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def contextual_quantity(statement: dict, contexts: dict) -> tuple[str | None, str | None, list]:
    """A quantity and exactly one reviewed applies-to-part context share this one statement."""
    issues = []
    snak = statement["mainsnak"]
    data = snak.get("datavalue")
    value = data.get("value") if isinstance(data, dict) else None
    volume = None
    if (
        statement.get("rank") not in ("normal", "preferred")
        or snak.get("property") != "P2234"
        or snak.get("datatype") != "quantity"
        or snak.get("snaktype") != "value"
        or not isinstance(data, dict)
        or data.get("type") != "quantity"
        or not isinstance(value, dict)
    ):
        issues.append("quantity_statement_requires_review")
    else:
        units = {
            f"{scheme}://www.wikidata.org/entity/{qid}": factor
            for qid, factor in VOLUME_UNITS.items()
            for scheme in ("http", "https")
        }
        try:
            amount = value.get("amount")
            if not isinstance(amount, str) or len(amount) > 128:
                raise ValueError
            number = Decimal(amount)
            if not number.is_finite() or value.get("unit") not in units:
                raise ValueError
            for key in ("lowerBound", "upperBound"):
                bound = value.get(key, amount)
                if not isinstance(bound, str) or len(bound) > 128 or Decimal(bound) != number:
                    raise ValueError
            converted = number * units[value["unit"]]
            if not converted.is_finite() or not 0 < converted <= 1_000_000:
                raise ValueError
            # No rounding to invent precision. The normalized contract supports at most 20
            # fractional places; multiplication must also be exact in the Decimal context.
            if converted / units[value["unit"]] != number or converted.as_tuple().exponent < -20:
                raise ValueError
            volume = decimal_text(converted)
        except (ValueError, TypeError, DecimalException):
            issues.append("volume_unit_range_or_precision_requires_review")
    qualifiers = statement.get("qualifiers")
    context_id = None
    if (
        not isinstance(qualifiers, dict)
        or set(qualifiers) != {"P518"}
        or not isinstance(qualifiers["P518"], list)
        or len(qualifiers["P518"]) != 1
        or ("qualifiers-order" in statement and statement["qualifiers-order"] != ["P518"])
    ):
        issues.append("single_applies_to_part_context_required")
    else:
        qualifier = qualifiers["P518"][0]
        data = qualifier.get("datavalue") if isinstance(qualifier, dict) else None
        value = data.get("value") if isinstance(data, dict) else None
        qid = value.get("id") if isinstance(value, dict) else None
        if (
            not isinstance(qualifier, dict)
            or qualifier.get("snaktype") != "value"
            or qualifier.get("property") != "P518"
            or qualifier.get("datatype") != "wikibase-item"
            or not isinstance(data, dict)
            or data.get("type") != "wikibase-entityid"
            or not isinstance(qid, str)
            or len(qid) > 32
            or not QID.fullmatch(qid)
            or value.get("entity-type") != "item"
            or type(value.get("numeric-id")) is not int
            or value["numeric-id"] != int(qid[1:])
            or qid not in contexts
        ):
            issues.append("context_definition_requires_review")
        else:
            context_id = qid
    return context_id, volume, issues


def observe_family(entity: dict, group: str, contexts: dict) -> list[dict]:
    claims = statements(entity, "P2234")
    if len(claims) > 100:
        raise AuditError("volume_context_statement_limit_exceeded")
    rows, ids, pairs = [], set(), defaultdict(list)
    for statement in claims:
        if statement.get("rank") == "deprecated":
            continue
        sid = statement.get("id")
        if (
            not isinstance(sid, str)
            or len(sid) > 128
            or not re.fullmatch(r"Q[1-9][0-9]*\$[A-Za-z0-9-]{1,90}", sid)
            or not sid.startswith(entity["id"] + "$")
            or sid in ids
        ):
            raise AuditError("unique_source_bound_volume_statement_id_required")
        ids.add(sid)
        context, volume, issues = contextual_quantity(statement, contexts)
        row = {
            "source_record_id": entity["id"],
            "source_revision": entity["lastrevid"],
            "source_url": f"https://www.wikidata.org/wiki/{entity['id']}?oldid={entity['lastrevid']}",
            "family_group": group,
            "statement_id": sid,
            "context_id": context,
            "context_revision": None if context is None else contexts[context].revision,
            "context_label": None if context is None else contexts[context].label,
            "volume_ml": volume,
            "reference_entries": reference_count(statement),
            "hold_reasons": issues,
            "abv_percent": None,
            "gtin": None,
            "backend_product_id": None,
        }
        rows.append(row)
        if context is not None:
            pairs[context].append(row)
    for members in pairs.values():
        if len(members) > 1:
            # Same family/context may disagree or repeat; neither is silently collapsed.
            for row in members:
                row["hold_reasons"].append("repeated_family_context_requires_review")
    return sorted(rows, key=lambda row: row["statement_id"])


def prepare_observations(spec: ObservationSpec, manifest_path: Path, paths: dict) -> dict:
    manifest_data, manifest_hash = read_json(manifest_path)
    manifest = SourceManifest.model_validate(manifest_data)
    if (
        manifest_hash != spec.manifest_sha256
        or manifest.source_id != "wikidata-structured"
        or manifest.license_label != "CC0-1.0"
        or not manifest.local_structured_normalization
    ):
        raise AuditError("reviewed_cc0_volume_context_source_required")
    loaded = {name: read_json(path) for name, path in paths.items()}
    for name, (_, file_hash) in loaded.items():
        if file_hash != getattr(spec, name + "_sha256"):
            raise AuditError("volume_context_authority_hash_mismatch")
    payload, raw_hash = loaded["input"]
    receipt = loaded["receipt"][0]
    definitions, definition_hash = loaded["context_input"]
    definition_receipt = loaded["context_receipt"][0]
    model_hash = hashlib.sha256(manifest.model_dump_json().encode()).hexdigest()
    verify_collection_snapshot(receipt, payload, raw_hash, model_hash)
    defined = verify_collection_snapshot(
        definition_receipt, definitions, definition_hash, model_hash
    )
    definition_records = {row["source_record_id"]: row for row in defined}
    if set(definition_records) != set(spec.contexts):
        raise AuditError("exact_reviewed_context_definitions_required")
    for qid, context in spec.contexts.items():
        record = definition_records[qid]
        if record["source_revision"] != context.revision or record["label"] != context.label:
            raise AuditError("context_definition_review_conflicts_with_source")
    review = ReviewManifest.model_validate(loaded["review"][0])
    _, records, _ = audit(payload, raw_hash, review)
    by_id = {row["source_record_id"]: row for row in records}
    rows, families = [], []
    for qid, group in sorted(spec.family_groups.items()):
        record = by_id.get(qid)
        if (
            record is None
            or record["entity_kind"] != "product_family"
            or record["source_revision"] != spec.source_revisions[qid]
            or record["volume_ml"] is not None
        ):
            raise AuditError("reviewed_family_with_unknown_scalar_volume_required")
        families.append({"source_record_id": qid, "family_group": group, "volume_ml": None})
        rows.extend(observe_family(payload["entities"][qid], group, spec.contexts))
    actual = {
        row["statement_id"]: {
            key: row[key] for key in ("source_record_id", "context_id", "volume_ml")
        }
        for row in rows
    }
    expected = {sid: fact.model_dump() for sid, fact in spec.expected_observations.items()}
    if actual != expected:
        raise AuditError("volume_context_observations_conflict_with_frozen_facts")
    return {
        "schema_version": 1,
        "algorithm": "reviewed-volume-context-observation-v1",
        "grain": "source_quantity_statement_with_applies_to_part_not_packaging_sku",
        "evidence_kind": spec.evidence_kind,
        "hashes": {
            "manifest_sha256": manifest_hash,
            **{k + "_sha256": v[1] for k, v in loaded.items()},
        },
        "collection_modes": {
            "families": receipt["mode"],
            "definitions": definition_receipt["mode"],
        },
        "selected_families": len(families),
        "context_definitions": len(definition_records),
        "active_volume_observations": len(rows),
        "preserved_observations": sum(not row["hold_reasons"] for row in rows),
        "held_observations": sum(bool(row["hold_reasons"]) for row in rows),
        "hold_reasons": dict(
            sorted(Counter(reason for row in rows for reason in row["hold_reasons"]).items())
        ),
        "families": families,
        "observations": rows,
        "backend_mappings_created": 0,
        "model_fit_performed": False,
        "limitations": [
            "context_definition_not_complete_physical_package_or_sellable_sku",
            "family_scalar_volume_unknown_and_variants_share_family_group",
            "no_gtin_abv_pack_count_taste_price_or_availability_inferred",
            "source_observation_not_business_mapping_or_model_quality_approval",
        ],
    }


def write_private_report(path: Path, report: dict) -> None:
    if ".pubburi" not in path.resolve().parts:
        raise AuditError("volume_context_output_requires_private_pubburi_directory")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
        os.link(
            temporary, path
        )  # Publish complete output once; never overwrite an existing report.
    finally:
        os.unlink(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    names = ("input", "receipt", "review", "context-input", "context-receipt")
    for name in (*names, "manifest", "spec", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    try:
        spec_data, spec_hash = read_json(args.spec)
        spec = ObservationSpec.model_validate(spec_data)
        paths = {name.replace("-", "_"): getattr(args, name.replace("-", "_")) for name in names}
        report = prepare_observations(spec, args.manifest, paths)
        report["spec_sha256"] = spec_hash
        write_private_report(args.output, report)
        print(
            json.dumps(
                {
                    key: report[key]
                    for key in (
                        "selected_families",
                        "active_volume_observations",
                        "preserved_observations",
                        "held_observations",
                        "backend_mappings_created",
                    )
                }
            )
        )
        return 0
    except (AuditError, OSError, ValueError):
        print("volume_context_preparation_failed", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
