"""Compare a frozen train-only SVD candidate with an unchanged reviewed-family baseline."""

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import numpy as np
import sklearn
from pydantic import Field, model_validator
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from pubburi_recommendation.baseline import ContractModel
from pubburi_recommendation.catalog_audit import AuditError, SourceManifest, read_json
from pubburi_recommendation.content_model import atomic_tokens, digest
from pubburi_recommendation.package_identity_audit import Hash
from pubburi_recommendation.source_family_cohort import CohortExperiment, load_cohort, run_cohort
from pubburi_recommendation.source_family_evaluation import aggregate_retrieval, inspect_retrieval
from pubburi_recommendation.source_family_experiment import tokens, write_report

ALGORITHM = "source-family-tfidf-svd-comparison-v1"
MAX_FIT_CELLS = 1_000_000
MEASUREMENTS = [
    "training_reconstruction_relative_frobenius_error",
    "training_retained_frobenius_energy_ratio",
    "training_explained_variance_ratio",
    "transform_zero_nonzero_latent_and_OOV_coverage",
    "same_frozen_fact_retrieval_complete_signed_cosine_rankings_and_positive_query_denominators",
]


class ComparisonSpec(ContractModel):
    schema_version: Literal[1]
    algorithm: Literal["source-family-tfidf-svd-comparison-v1"]
    frozen_at_utc: str = Field(min_length=20, max_length=40)
    base_spec_sha256: Hash
    baseline_report_sha256: Hash
    baseline_fingerprint: Hash
    evidence_kind: Literal["reviewed_public_source", "authored_regression_fixture"]
    sklearn_version: str = Field(min_length=1, max_length=40)
    n_components: int = Field(ge=1, le=100)
    random_state: int = Field(ge=0, le=2_147_483_647)
    svd_algorithm: Literal["randomized"]
    n_iter: int = Field(ge=1, le=20)
    n_oversamples: int = Field(ge=1, le=100)
    power_iteration_normalizer: Literal["QR"]
    normalization: Literal["l2_tfidf_then_l2_latent"]
    retrieval_case_ids: list[str] = Field(min_length=1, max_length=1000)
    predeclared_measurements: list[str] = Field(min_length=5, max_length=5)
    decision_scope: Literal["representation_adequacy_only_not_service_adoption_or_quality"]
    no_parameter_sweep_or_heldout_tuning: Literal[True]

    @model_validator(mode="after")
    def frozen_protocol(self):
        frozen = datetime.fromisoformat(self.frozen_at_utc)
        if frozen.tzinfo is None or frozen.utcoffset() != UTC.utcoffset(frozen):
            raise ValueError("comparison_freeze_requires_explicit_utc")
        if len(self.retrieval_case_ids) != len(set(self.retrieval_case_ids)):
            raise ValueError("comparison_retrieval_case_ids_must_be_unique")
        if self.predeclared_measurements != MEASUREMENTS:
            raise ValueError("comparison_requires_exact_predeclared_measurements")
        return self


def compare_representation(
    comparison: ComparisonSpec, spec: CohortExperiment, baseline: dict
) -> dict:
    if (
        comparison.sklearn_version != sklearn.__version__
        or comparison.baseline_fingerprint != baseline["fit_fingerprint"]
        or comparison.evidence_kind != spec.evidence_kind
        or comparison.retrieval_case_ids != [case.case_id for case in spec.retrieval_cases]
    ):
        raise AuditError("comparison_protocol_conflicts_with_frozen_baseline")
    if datetime.fromisoformat(comparison.frozen_at_utc) > datetime.now(UTC):
        raise AuditError("comparison_freeze_cannot_be_future")
    fit_ids = sorted(qid for qid, group in spec.family_groups.items() if group in spec.fit_groups)
    transform_ids = sorted(set(spec.family_groups) - set(fit_ids))
    shape = baseline["fit_text_matrix"]["shape"]
    rank = baseline["fit_text_matrix"]["rank"]
    if (
        shape[0] * shape[1] > MAX_FIT_CELLS
        or rank is None
        or comparison.n_components >= min(shape)
        or comparison.n_components >= rank
    ):
        raise AuditError("comparison_requires_bounded_nontrivial_rank_reduction")
    # Both candidate TF-IDF and SVD see fit families only; held-out tokens never enter fit.
    vectorizer = TfidfVectorizer(analyzer=atomic_tokens, norm="l2", smooth_idf=True)
    matrix = vectorizer.fit_transform([tokens(spec.expected_facts[qid]) for qid in fit_ids])
    vocabulary = vectorizer.get_feature_names_out().tolist()
    idf = vectorizer.idf_.tolist()
    if (
        vocabulary != baseline["fitted_parameters"]["vocabulary"]
        or idf != baseline["fitted_parameters"]["idf"]
        or list(matrix.shape) != shape
    ):
        raise AuditError("candidate_tfidf_conflicts_with_recomputed_baseline")
    settings = {
        "n_components": comparison.n_components,
        "algorithm": comparison.svd_algorithm,
        "n_iter": comparison.n_iter,
        "n_oversamples": comparison.n_oversamples,
        "power_iteration_normalizer": comparison.power_iteration_normalizer,
        "random_state": comparison.random_state,
    }
    reducer = TruncatedSVD(**settings)
    latent = reducer.fit_transform(matrix)
    reconstructed = reducer.inverse_transform(latent)
    dense = matrix.toarray()  # Bounded by MAX_FIT_CELLS before allocating/fitting.
    energy = float(np.sum(dense**2))
    error = float(np.linalg.norm(dense - reconstructed) / math.sqrt(energy))
    retained = float(np.sum(reconstructed**2) / energy)
    variance = reducer.explained_variance_ratio_.tolist()
    if not all(math.isfinite(value) for value in [error, retained, *variance]):
        raise AuditError("comparison_requires_finite_training_measurements")
    parameters = {
        "settings": settings,
        "normalization": comparison.normalization,
        "vocabulary": vocabulary,
        "idf": idf,
        "components": reducer.components_.tolist(),
        "singular_values": reducer.singular_values_.tolist(),
        "numeric_fit": baseline["fitted_parameters"]["numeric_fit"],
        "numeric_branch": "unchanged_baseline_minmax_not_svd_input",
    }
    fingerprint = digest(
        {
            "algorithm": ALGORITHM,
            "sklearn_version": sklearn.__version__,
            "training_baseline_fingerprint": baseline["fit_fingerprint"],
            **parameters,
        }
    )
    training_vectors = normalize(latent, norm="l2")
    fit_positions = {qid: index for index, qid in enumerate(fit_ids)}
    transformed, query_vectors = [], {}
    previous = {row["source_record_id"]: row for row in baseline["transformed"]}
    for qid in transform_ids:
        document = tokens(spec.expected_facts[qid])
        source_vector = vectorizer.transform([document])
        raw_latent = reducer.transform(source_vector)
        query_vectors[qid] = normalize(raw_latent, norm="l2")[0]
        known = sum(term in vectorizer.vocabulary_ for term in document)
        transformed.append(
            {
                "source_record_id": qid,
                "source_revision": previous[qid]["source_revision"],
                "family_group": spec.family_groups[qid],
                "supported_tokens": known,
                "unknown_tokens": sorted(set(document) - set(vocabulary)),
                "source_text_vector_norm": float(np.sqrt(source_vector.power(2).sum())),
                "latent_vector_norm": float(np.linalg.norm(raw_latent)),
                "normalized_latent_vector": query_vectors[qid].tolist(),
                "numeric": previous[qid]["numeric"],
            }
        )
    retrieved = []
    for case in spec.retrieval_cases:
        scores = training_vectors @ query_vectors[case.query_id]
        if not np.isfinite(scores).all():
            raise AuditError("comparison_requires_finite_retrieval_cosines")
        rows = [
            {
                "source_record_id": qid,
                "score": min(1.0, max(-1.0, float(scores[fit_positions[qid]]))),
            }
            for qid in case.candidate_ids
        ]
        rows.sort(key=lambda row: (-row["score"], row["source_record_id"]))
        # A signed latent cosine must not be clipped to zero, shifted or called a probability.
        retrieved.append(inspect_retrieval(case, rows, signed_cosine=True))
    return {
        "algorithm": ALGORITHM,
        "fitted": True,
        "fit_fingerprint": fingerprint,
        "fit_records": len(fit_ids),
        "transform_records": len(transform_ids),
        "fit_input_shape": shape,
        "latent_dimensions": comparison.n_components,
        "fitted_parameters": parameters,
        "training_measurements": {
            "reconstruction_relative_frobenius_error": error,
            "retained_frobenius_energy_ratio": retained,
            "explained_variance_ratio": variance,
            "explained_variance_ratio_sum": sum(variance),
        },
        "transform_coverage": {
            "records": len(transformed),
            "zero_source_text_vectors": sum(
                row["source_text_vector_norm"] == 0 for row in transformed
            ),
            "zero_latent_vectors": sum(row["latent_vector_norm"] == 0 for row in transformed),
            "nonzero_latent_vectors": sum(row["latent_vector_norm"] > 0 for row in transformed),
            "records_with_oov": sum(bool(row["unknown_tokens"]) for row in transformed),
        },
        "transformed": transformed,
        "ranking_metrics": aggregate_retrieval(retrieved),
        "adoption": "not_adopted_by_offline_comparison",
        "limitations": [
            "small_source_family_representation_audit_not_service_sku_or_user_quality",
            "reconstruction_energy_and_variance_are_training_information_not_relevance",
            "same_class_is_input_and_fact_judgment_not_independent_human_preference",
            "svd_cannot_recover_out_of_vocabulary_facts_or_make_zero_vectors_informative",
            "numeric_unknowns_and_baseline_scalers_are_unchanged_not_latent_inputs",
            "signed_latent_cosine_is_not_a_probability_or_service_score",
            "fixed_candidate_no_parameter_sweep_or_heldout_tuning",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "spec", "comparison-spec", "baseline-report", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--snapshot", nargs=4, action="append", required=True)
    args = parser.parse_args()
    try:
        if ".pubburi" not in args.output.resolve().parts or args.output.exists():
            raise AuditError("comparison_report_requires_new_private_output")
        data, comparison_hash = read_json(args.comparison_spec)
        comparison = ComparisonSpec.model_validate(data)
        expected_baseline, baseline_hash = read_json(args.baseline_report)
        spec_data, spec_hash = read_json(args.spec)
        if (
            comparison.base_spec_sha256 != spec_hash
            or comparison.baseline_report_sha256 != baseline_hash
        ):
            raise AuditError("comparison_frozen_input_hash_mismatch")
        manifest_data, manifest_hash = read_json(args.manifest)
        manifest = SourceManifest.model_validate(manifest_data)
        if (
            manifest.source_id != "wikidata-structured"
            or manifest.license_label != "CC0-1.0"
            or not manifest.local_structured_normalization
            or not manifest.structured_feature_fit
        ):
            raise AuditError("source_structured_feature_fit_not_approved")
        spec = CohortExperiment.model_validate(spec_data)
        if spec.manifest_sha256 != manifest_hash:
            raise AuditError("cohort_manifest_hash_mismatch")
        if len({row[0] for row in args.snapshot}) != len(args.snapshot):
            raise AuditError("cohort_snapshot_argument_names_must_be_unique")
        inputs = {row[0]: tuple(Path(value) for value in row[1:]) for row in args.snapshot}
        records, authorities = load_cohort(spec, manifest, inputs)
        baseline = run_cohort(
            spec,
            records,
            {"spec_sha256": spec_hash, "manifest_sha256": manifest_hash, **authorities},
        )
        if baseline != expected_baseline:
            raise AuditError("comparison_baseline_report_changed")
        candidate = compare_representation(comparison, spec, baseline)
        report = {
            "schema_version": 1,
            "algorithm": ALGORITHM,
            "evidence_kind": spec.evidence_kind,
            "comparison_spec_sha256": comparison_hash,
            "baseline_report_sha256": baseline_hash,
            "baseline": baseline,
            "candidate": candidate,
            "passed_contract": baseline["passed_contract"],
            "network_performed": False,
            "service_mapping_or_adoption_performed": False,
        }
        write_report(args.output, report)
        print(
            json.dumps(
                {
                    "fit_records": candidate["fit_records"],
                    "transform_records": candidate["transform_records"],
                    "latent_dimensions": candidate["latent_dimensions"],
                    "passed_contract": report["passed_contract"],
                }
            )
        )
        return 0 if report["passed_contract"] else 1
    except (OSError, ValueError, TypeError, KeyError) as error:
        code = str(error) if isinstance(error, AuditError) else type(error).__name__
        print("Source representation comparison failed: " + code, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
