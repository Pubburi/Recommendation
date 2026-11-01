"""Offline representation fit on reviewed source families, never Backend/SKU recommendation."""

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Annotated, Literal, Self

import numpy as np
import sklearn
from pydantic import Field, StringConstraints, model_validator
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import MinMaxScaler

from pubburi_recommendation.baseline import ContractModel
from pubburi_recommendation.catalog_audit import (
    AuditError,
    ReviewManifest,
    SourceManifest,
    audit,
    read_json,
)
from pubburi_recommendation.collection_snapshot import verify_collection_snapshot
from pubburi_recommendation.content_model import atomic_tokens, digest

SourceId = Annotated[str, StringConstraints(pattern=r"^Q[1-9][0-9]{0,30}$")]
Group = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
Hash = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
ALGORITHM = "source-family-tfidf-minmax-v1"
NUMERIC = ("abv_percent", "volume_ml")


class FamilyFacts(ContractModel):
    instance_of_ids: list[SourceId] = Field(max_length=64)
    producer_ids: list[SourceId] = Field(max_length=64)
    abv_percent: float | None = Field(ge=0, le=100, allow_inf_nan=False)
    volume_ml: float | None = Field(gt=0, le=1_000_000, allow_inf_nan=False)

    @model_validator(mode="after")
    def canonical_identifiers(self) -> Self:
        for values in (self.instance_of_ids, self.producer_ids):
            if values != sorted(set(values)):
                raise ValueError("fact_identifiers_must_be_sorted_and_unique")
        return self


class FamilyExperiment(ContractModel):
    schema_version: Literal[1]
    experiment_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,99}$")
    evidence_kind: Literal["reviewed_public_source", "authored_regression_fixture"]
    data_kind: Literal["reviewed_source_product_families"]
    input_sha256: Hash
    review_sha256: Hash
    manifest_sha256: Hash
    receipt_sha256: Hash
    family_groups: dict[SourceId, Group] = Field(min_length=2, max_length=1000)
    fit_groups: list[Group] = Field(min_length=1, max_length=1000)
    transform_groups: list[Group] = Field(min_length=1, max_length=1000)
    expected_facts: dict[SourceId, FamilyFacts] = Field(min_length=2, max_length=1000)

    @model_validator(mode="after")
    def frozen_partition(self) -> Self:
        fit, transform = set(self.fit_groups), set(self.transform_groups)
        if len(fit) != len(self.fit_groups) or len(transform) != len(self.transform_groups):
            raise ValueError("partition_groups_must_be_unique")
        if fit & transform:
            raise ValueError("family_groups_must_not_cross_fit_transform")
        if fit | transform != set(self.family_groups.values()):
            raise ValueError("partition_must_cover_exact_family_groups")
        if set(self.expected_facts) != set(self.family_groups):
            raise ValueError("manual_facts_must_cover_exact_selected_families")
        return self


def verify_receipt(
    receipt: dict, payload: dict, spec: FamilyExperiment, manifest_model_hash: str
) -> None:
    verify_collection_snapshot(receipt, payload, spec.input_sha256, manifest_model_hash)


def tokens(facts: FamilyFacts) -> list[str]:
    return [f"instance_of:{qid}" for qid in facts.instance_of_ids] + [
        f"producer:{qid}" for qid in facts.producer_ids
    ]


def fit_representation(spec: FamilyExperiment, records: list[dict], hashes: dict) -> dict:
    by_id = {row["source_record_id"]: row for row in records}
    for qid, facts in spec.expected_facts.items():
        row = by_id.get(qid)
        if row is None or row["entity_kind"] != "product_family" or row["label"] is None:
            raise AuditError("selected_records_require_reviewed_named_product_families")
        if any(row[field] != value for field, value in facts.model_dump().items()):
            raise AuditError("manual_facts_conflict_with_reviewed_source")
    fit_ids = sorted(qid for qid, group in spec.family_groups.items() if group in spec.fit_groups)
    transform_ids = sorted(set(spec.family_groups) - set(fit_ids))
    documents = [tokens(spec.expected_facts[qid]) for qid in fit_ids]
    expected_df = Counter(term for document in documents for term in set(document))
    expected_vocabulary = sorted(expected_df)
    vectorizer = None
    matrix = None
    vocabulary, idf = [], []
    if expected_vocabulary:
        vectorizer = TfidfVectorizer(analyzer=atomic_tokens, norm="l2", smooth_idf=True)
        matrix = vectorizer.fit_transform(documents)
        vocabulary = vectorizer.get_feature_names_out().tolist()
        idf = vectorizer.idf_.tolist()
    # Independently calculate expected fit statistics from frozen facts, never held-out rows.
    expected_idf = [
        math.log((1 + len(documents)) / (1 + expected_df[term])) + 1 for term in expected_vocabulary
    ]
    fit_checks = {
        "training_vocabulary_only": vocabulary == expected_vocabulary,
        "training_document_frequency_only": bool(
            np.allclose(idf, expected_idf, atol=1e-12, rtol=1e-12)
        ),
    }
    numeric, scalers = {}, {}
    for field in NUMERIC:
        observed = [getattr(spec.expected_facts[qid], field) for qid in fit_ids]
        observed = [value for value in observed if value is not None]
        scaler = None
        if observed:
            scaler = MinMaxScaler(clip=False).fit(np.array(observed).reshape(-1, 1))
            fit_checks[f"{field}_training_range_only"] = bool(
                scaler.data_min_[0] == min(observed) and scaler.data_max_[0] == max(observed)
            )
        active = bool(observed and min(observed) != max(observed))
        scalers[field] = scaler if active else None
        numeric[field] = {
            "observed_training_values": len(observed),
            "minimum": min(observed) if observed else None,
            "maximum": max(observed) if observed else None,
            "active": active,
            "inactive_reason": None if active else "constant" if observed else "all_unknown",
        }
    parameters = {"vocabulary": vocabulary, "idf": idf, "numeric_fit": numeric}
    training_facts = {qid: spec.expected_facts[qid].model_dump(mode="json") for qid in fit_ids}
    fingerprint = digest(
        {
            "algorithm": ALGORITHM,
            "sklearn_version": sklearn.__version__,
            "training_facts": training_facts,
            **parameters,
        }
    )
    transformed = []
    vocabulary_set = set(expected_vocabulary)
    for qid in transform_ids:
        facts = spec.expected_facts[qid]
        row_tokens = tokens(facts)
        known = [term for term in row_tokens if term in vocabulary_set]
        vector = None if vectorizer is None else vectorizer.transform([row_tokens])
        numeric_values = {}
        for field in NUMERIC:
            value = getattr(facts, field)
            scaler = scalers[field]
            position = (
                None
                if value is None or scaler is None
                else float(scaler.transform([[value]])[0, 0])
            )
            numeric_values[field] = {
                "observed": value is not None,
                "scaled_value": position,
                "outside_fit_range": position is not None and not 0 <= position <= 1,
            }
        transformed.append(
            {
                "source_record_id": qid,
                "source_revision": by_id[qid]["source_revision"],
                "family_group": spec.family_groups[qid],
                "supported_tokens": len(known),
                "unknown_tokens": sorted(set(row_tokens) - set(known)),
                "text_vector_norm": 0.0
                if vector is None
                else float(np.sqrt(vector.power(2).sum())),
                "numeric": numeric_values,
            }
        )
    shape = [len(fit_ids), len(vocabulary)]
    # Bound dense inspection independently of the sparse fit; do not allocate a large dense matrix.
    rank = (
        None
        if matrix is None or shape[0] * shape[1] > 1_000_000
        else int(np.linalg.matrix_rank(matrix.toarray()))
    )
    return {
        "schema_version": 1,
        "algorithm": ALGORITHM,
        "experiment_id": spec.experiment_id,
        "evidence_kind": spec.evidence_kind,
        "grain": "reviewed_source_product_family_not_sellable_sku",
        "hashes": hashes,
        "sklearn_version": sklearn.__version__,
        "fit_fingerprint": fingerprint,
        "fit_records": len(fit_ids),
        "fit_groups": len(spec.fit_groups),
        "transform_records": len(transform_ids),
        "transform_groups": len(spec.transform_groups),
        "fitted_parameters": parameters,
        "fit_text_matrix": {
            "fit_performed": vectorizer is not None,
            "shape": shape,
            "rank": rank,
            "rank_upper_bound": min(shape),
        },
        "fit_checks": fit_checks,
        "passed_contract": all(fit_checks.values()),
        "transformed": transformed,
        "ranking_metrics": {"status": "not_calculated", "reason": "no_relevance_judgments"},
        "svd": {"fitted": False, "decision": "not_adopted_without_downstream_evaluation"},
        "limitations": [
            "not_service_sku_or_backend_id_mapping",
            "representation_fit_not_recommendation_or_user_preference_quality",
            "exact_class_ids_do_not_learn_taxonomy_or_taste",
            "source_family_split_not_final_product_generalization_evaluation",
        ],
    }


def write_report(path: Path, report: dict) -> None:
    """Publish complete private parameters without overwriting a racing/existing report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".family-fit-", delete=False
        ) as output:
            temporary = Path(output.name)
            json.dump(report, output, ensure_ascii=False, indent=2)
            output.write("\n")
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "input", "receipt", "review", "spec", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    try:
        if ".pubburi" not in args.output.resolve().parts:
            raise AuditError("model_report_requires_private_pubburi_directory")
        if args.output.exists():
            raise AuditError("existing_model_report_must_be_preserved")
        manifest_data, manifest_hash = read_json(args.manifest)
        manifest = SourceManifest.model_validate(manifest_data)
        if (
            manifest.source_id != "wikidata-structured"
            or manifest.license_label != "CC0-1.0"
            or not manifest.local_structured_normalization
            or not manifest.structured_feature_fit
        ):
            raise AuditError("source_structured_feature_fit_not_approved")
        spec_data, spec_hash = read_json(args.spec)
        spec = FamilyExperiment.model_validate(spec_data)
        payload, input_hash = read_json(args.input)
        review_data, review_hash = read_json(args.review)
        receipt, receipt_hash = read_json(args.receipt)
        hashes = {
            "manifest_sha256": manifest_hash,
            "input_sha256": input_hash,
            "review_sha256": review_hash,
            "receipt_sha256": receipt_hash,
        }
        if any(getattr(spec, key) != value for key, value in hashes.items()):
            raise AuditError("experiment_input_hash_mismatch")
        review = ReviewManifest.model_validate(review_data)
        _, records, _ = audit(payload, input_hash, review)
        # Collector receipts bind the validated manifest model, not the file's whitespace/bytes.
        manifest_model_hash = hashlib.sha256(manifest.model_dump_json().encode()).hexdigest()
        verify_receipt(receipt, payload, spec, manifest_model_hash)
        report = fit_representation(
            spec,
            records,
            {
                **hashes,
                "spec_sha256": spec_hash,
                "collection_manifest_model_sha256": manifest_model_hash,
            },
        )
        write_report(args.output, report)
        print(
            json.dumps(
                {
                    key: report[key]
                    for key in ("fit_records", "transform_records", "passed_contract")
                }
            )
        )
        return 0 if report["passed_contract"] else 1
    except (OSError, ValueError, TypeError, KeyError) as error:
        reason = str(error) if isinstance(error, AuditError) else type(error).__name__
        print(f"Source family experiment failed: {reason}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
