"""Reuse reviewed snapshots for an unseen-producer family experiment, never merge receipts/SKUs."""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from pubburi_recommendation.baseline import ContractModel
from pubburi_recommendation.catalog_audit import (
    QID,
    AuditError,
    ReviewManifest,
    SourceManifest,
    audit,
    read_json,
    statements,
)
from pubburi_recommendation.collection_snapshot import verify_collection_snapshot
from pubburi_recommendation.source_family_experiment import (
    FamilyPartition,
    Hash,
    SourceId,
    fit_representation,
    write_report,
)


class SnapshotBinding(ContractModel):
    snapshot_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    input_sha256: Hash
    receipt_sha256: Hash
    review_sha256: Hash
    selected_ids: list[SourceId] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def unique_selected(self):
        if self.selected_ids != sorted(set(self.selected_ids)):
            raise ValueError("cohort_selection_must_be_sorted_unique_source_ids")
        return self


class CohortExperiment(FamilyPartition):
    manifest_sha256: Hash
    snapshot_bindings: list[SnapshotBinding] = Field(min_length=2, max_length=4)
    split_policy: Literal["unseen_producer"]

    @model_validator(mode="after")
    def independent_authorities_and_producers(self):
        bindings = self.snapshot_bindings
        if len({row.snapshot_id for row in bindings}) != len(bindings) or len(
            {row.input_sha256 for row in bindings}
        ) != len(bindings):
            raise ValueError("distinct_snapshot_ids_and_inputs_required")
        selected = [qid for row in bindings for qid in row.selected_ids]
        if len(selected) != len(set(selected)):
            raise ValueError("overlapping_source_ids_require_separate_review_not_overwrite")
        if set(selected) != set(self.expected_facts):
            raise ValueError("snapshot_selection_must_cover_exact_frozen_families")
        if any(not facts.producer_ids for facts in self.expected_facts.values()):
            raise ValueError("unseen_producer_split_requires_known_source_producer_relations")
        fit = self.producers(self.fit_groups)
        transformed = self.producers(self.transform_groups)
        if fit & transformed:
            raise ValueError("producer_relations_must_not_cross_fit_transform")
        return self

    def producers(self, groups):
        return {
            producer
            for qid, facts in self.expected_facts.items()
            if self.family_groups[qid] in groups
            for producer in facts.producer_ids
        }


def checked_relation_ids(entity: dict, prop: str) -> list[str]:
    """Only explicit, unqualified entity-valued source relations support this holdout claim."""
    result = set()
    for statement in statements(entity, prop):
        if statement.get("rank") == "deprecated":
            continue
        snak = statement["mainsnak"]
        data = snak.get("datavalue")
        value = data.get("value") if isinstance(data, dict) else None
        qid = value.get("id") if isinstance(value, dict) else None
        qualifiers = statement.get("qualifiers", {})
        if (
            statement.get("rank") not in ("normal", "preferred")
            or not isinstance(qualifiers, dict)
            or qualifiers
            or snak.get("snaktype") != "value"
            # Minimal authored/legacy shapes omit redundant snak metadata. Explicit
            # contradictions must not be treated as a relation merely from its bucket.
            or ("property" in snak and snak["property"] != prop)
            or ("datatype" in snak and snak["datatype"] != "wikibase-item")
            or not isinstance(data, dict)
            or data.get("type") != "wikibase-entityid"
            or not isinstance(qid, str)
            or not QID.fullmatch(qid)
            or ("entity-type" in value and value["entity-type"] != "item")
            or (
                "numeric-id" in value
                and (type(value["numeric-id"]) is not int or value["numeric-id"] != int(qid[1:]))
            )
        ):
            raise AuditError("cohort_source_relation_requires_review")
        result.add(qid)
    return sorted(result)


def load_cohort(
    spec: CohortExperiment, manifest: SourceManifest, snapshots: dict
) -> tuple[list, dict]:
    if set(snapshots) != {row.snapshot_id for row in spec.snapshot_bindings}:
        raise AuditError("cohort_requires_exact_named_snapshot_inputs")
    model_hash = hashlib.sha256(manifest.model_dump_json().encode()).hexdigest()
    selected, provenance = [], []
    for binding in spec.snapshot_bindings:
        raw_path, receipt_path, review_path = snapshots[binding.snapshot_id]
        payload, raw_hash = read_json(raw_path)
        receipt, receipt_hash = read_json(receipt_path)
        review_data, review_hash = read_json(review_path)
        hashes = dict(input_sha256=raw_hash, receipt_sha256=receipt_hash, review_sha256=review_hash)
        if any(getattr(binding, key) != value for key, value in hashes.items()):
            raise AuditError("cohort_snapshot_authority_hash_mismatch")
        verified = verify_collection_snapshot(receipt, payload, raw_hash, model_hash)
        _, records, _ = audit(payload, raw_hash, ReviewManifest.model_validate(review_data))
        by_id = {row["source_record_id"]: row for row in records}
        if not set(binding.selected_ids) <= set(by_id):
            raise AuditError("cohort_selected_family_missing_from_snapshot")
        for qid in binding.selected_ids:
            row, entity = by_id[qid], payload["entities"][qid]
            if row["entity_kind"] != "product_family" or row["label"] is None:
                raise AuditError("cohort_requires_reviewed_named_source_families")
            for prop, field in (("P31", "instance_of_ids"), ("P176", "producer_ids")):
                if checked_relation_ids(entity, prop) != getattr(spec.expected_facts[qid], field):
                    raise AuditError("cohort_source_relation_conflicts_with_frozen_facts")
            selected.append(row)
        provenance.append(
            {
                "snapshot_id": binding.snapshot_id,
                **hashes,
                "collection_mode": receipt["mode"],
                "source_items": len(verified),
                "selected_families": len(binding.selected_ids),
                "selected_revisions": {
                    qid: by_id[qid]["source_revision"] for qid in binding.selected_ids
                },
            }
        )
    return selected, {"source_manifest_model_sha256": model_hash, "snapshots": provenance}


def run_cohort(spec, records, hashes):
    report = fit_representation(spec, records, hashes)
    report["cohort"] = {
        "split_policy": spec.split_policy,
        "snapshot_count": len(spec.snapshot_bindings),
        "selected_families": len(records),
        "selected_producers": len(spec.producers(spec.family_groups.values())),
        "training_producers": len(spec.producers(spec.fit_groups)),
        "transform_producers": len(spec.producers(spec.transform_groups)),
        "producer_overlap": 0,
        "transform_representation": {
            "records": len(report["transformed"]),
            "zero_text_vectors": sum(row["text_vector_norm"] == 0 for row in report["transformed"]),
            "nonzero_text_vectors": sum(
                row["text_vector_norm"] > 0 for row in report["transformed"]
            ),
            "known_numeric_records": {
                name: sum(row["numeric"][name]["observed"] for row in report["transformed"])
                for name in ("abv_percent", "volume_ml")
            },
        },
        "network_performed": False,
        "group_authority": "explicit_curator_family_groups_not_packaging_or_business_skus",
    }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "spec", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument(
        "--snapshot",
        nargs=4,
        action="append",
        required=True,
        metavar=("NAME", "INPUT", "RECEIPT", "REVIEW"),
    )
    args = parser.parse_args()
    try:
        if ".pubburi" not in args.output.resolve().parts or args.output.exists():
            raise AuditError("cohort_report_requires_new_private_output")
        manifest_data, manifest_hash = read_json(args.manifest)
        manifest = SourceManifest.model_validate(manifest_data)
        if (
            manifest.source_id != "wikidata-structured"
            or manifest.license_label != "CC0-1.0"
            or not manifest.local_structured_normalization
            or not manifest.structured_feature_fit
        ):
            raise AuditError("source_structured_feature_fit_not_approved")
        data, spec_hash = read_json(args.spec)
        spec = CohortExperiment.model_validate(data)
        if spec.manifest_sha256 != manifest_hash:
            raise AuditError("cohort_manifest_hash_mismatch")
        if len({row[0] for row in args.snapshot}) != len(args.snapshot):
            raise AuditError("cohort_snapshot_argument_names_must_be_unique")
        inputs = {row[0]: tuple(Path(value) for value in row[1:]) for row in args.snapshot}
        records, authorities = load_cohort(spec, manifest, inputs)
        report = run_cohort(
            spec,
            records,
            {"spec_sha256": spec_hash, "manifest_sha256": manifest_hash, **authorities},
        )
        write_report(args.output, report)
        print(
            json.dumps(
                {
                    "fit_records": report["fit_records"],
                    "transform_records": report["transform_records"],
                    "passed_contract": report["passed_contract"],
                }
            )
        )
        return 0 if report["passed_contract"] else 1
    except (OSError, ValueError, TypeError, KeyError) as error:
        code = str(error) if isinstance(error, AuditError) else type(error).__name__
        print("Source family cohort failed: " + code, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
