"""Train an offline neural representation on already reviewed source families."""

import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import sklearn
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import normalize

from pubburi_recommendation.catalog_audit import AuditError, SourceManifest, read_json
from pubburi_recommendation.content_model import atomic_tokens, digest
from pubburi_recommendation.source_family_cohort import CohortExperiment, load_cohort
from pubburi_recommendation.source_family_evaluation import aggregate_retrieval, inspect_retrieval
from pubburi_recommendation.source_family_experiment import tokens, write_report

ALGORITHM = "source-family-tfidf-tanh-autoencoder-v1"
MODEL_SETTINGS = {
    "hidden_layer_sizes": (8, 2, 8),
    "activation": "tanh",
    "solver": "lbfgs",
    "early_stopping": False,
    "random_state": 0,
    "max_iter": 1000,
    "tol": 1e-6,
    "alpha": 0.001,
}


def encode(model, matrix):
    # Biases must not turn an entirely unsupported item into evidence.
    supported = np.any(matrix != 0, axis=1)
    vectors = np.zeros((len(matrix), MODEL_SETTINGS["hidden_layer_sizes"][1]))
    values = matrix[supported]
    for weights, bias in zip(model.coefs_[:2], model.intercepts_[:2], strict=True):
        values = np.tanh(values @ weights + bias)
    vectors[supported] = values
    return normalize(vectors)


def evaluate_cases(spec, fit_ids, query_ids, train, queries):
    train_positions = {qid: i for i, qid in enumerate(fit_ids)}
    query_positions = {qid: i for i, qid in enumerate(query_ids)}
    observations = []
    for case in spec.retrieval_cases:
        query = queries[query_positions[case.query_id]]
        rows = [
            {
                "source_record_id": qid,
                "score": float(np.clip(train[train_positions[qid]] @ query, 0, 1)),
            }
            for qid in case.candidate_ids
        ]
        rows.sort(key=lambda row: (-row["score"], row["source_record_id"]))
        observations.append(inspect_retrieval(case, rows))
    return aggregate_retrieval(observations)


def evaluate(spec, hashes):
    fit_ids = sorted(qid for qid, group in spec.family_groups.items() if group in spec.fit_groups)
    query_ids = sorted(set(spec.family_groups) - set(fit_ids))
    fit_tokens = [tokens(spec.expected_facts[qid]) for qid in fit_ids]
    if not any(fit_tokens):
        raise AuditError("neural_candidate_requires_observed_training_tokens")
    vectorizer = TfidfVectorizer(analyzer=atomic_tokens, norm="l2", smooth_idf=True)
    sparse_train = vectorizer.fit_transform(fit_tokens)
    features = sparse_train.shape[1]
    if features > 256 or (len(fit_ids) + len(query_ids)) * features > 1_000_000:
        raise AuditError("neural_candidate_dense_input_limit")

    train = sparse_train.toarray()
    supported_train = np.any(train != 0, axis=1)
    if supported_train.sum() < 2:
        raise AuditError("neural_candidate_requires_two_supported_training_families")
    training_rows = train[supported_train]
    training_targets = training_rows.ravel() if features == 1 else training_rows
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always", ConvergenceWarning)
        model = MLPRegressor(**MODEL_SETTINGS).fit(training_rows, training_targets)
    converged = not any(issubclass(item.category, ConvergenceWarning) for item in emitted)

    # Transform held-out families only after fitting the vectorizer and network.
    query = vectorizer.transform([tokens(spec.expected_facts[qid]) for qid in query_ids]).toarray()
    supported_query = np.any(query != 0, axis=1)
    latent_train, latent_query = encode(model, train), encode(model, query)
    fingerprint = digest(
        {
            "algorithm": ALGORITHM,
            "settings": MODEL_SETTINGS,
            "sklearn_version": sklearn.__version__,
            "vocabulary": vectorizer.get_feature_names_out().tolist(),
            "idf": vectorizer.idf_.tolist(),
            "weights": [layer.tolist() for layer in model.coefs_],
            "biases": [layer.tolist() for layer in model.intercepts_],
        }
    )

    def reconstruction_rmse(matrix):
        reconstructed = model.predict(matrix).reshape(matrix.shape)
        return float(np.sqrt(np.mean((reconstructed - matrix) ** 2)))

    return {
        "schema_version": 1,
        "algorithm": ALGORITHM,
        "experiment_id": spec.experiment_id,
        "evidence_kind": spec.evidence_kind,
        "hashes": hashes,
        "model_settings": MODEL_SETTINGS,
        "fit_fingerprint": fingerprint,
        "fit_shape": list(train.shape),
        "latent_shape": list(latent_train.shape),
        "fit_groups": len(spec.fit_groups),
        "heldout_groups": len(spec.transform_groups),
        "iterations": int(model.n_iter_),
        "converged": converged,
        "reconstruction": {
            "training_rmse": reconstruction_rmse(training_rows),
            "heldout_supported_rows": int(supported_query.sum()),
            "heldout_supported_rmse": (
                reconstruction_rmse(query[supported_query]) if supported_query.any() else None
            ),
        },
        "heldout": {
            "total_rows": len(query),
            "zero_tfidf_rows": int((~supported_query).sum()),
            "zero_neural_rows": int((~np.any(latent_query != 0, axis=1)).sum()),
        },
        "tfidf_retrieval": evaluate_cases(spec, fit_ids, query_ids, train, query),
        "neural_retrieval": evaluate_cases(spec, fit_ids, query_ids, latent_train, latent_query),
        "scope": "offline_source_family_fact_retrieval",
    }


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
            raise AuditError("neural_report_requires_new_private_output")
        data, manifest_hash = read_json(args.manifest)
        manifest = SourceManifest.model_validate(data)
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
        snapshots = {
            name: (Path(raw), Path(receipt), Path(review))
            for name, raw, receipt, review in args.snapshot
        }
        if len(snapshots) != len(args.snapshot):
            raise AuditError("cohort_snapshot_argument_names_must_be_unique")
        # This verifies the accepted snapshots and the exact P31/P176 facts used by both models.
        _, authorities = load_cohort(spec, manifest, snapshots)
        report = evaluate(
            spec, {"spec_sha256": spec_hash, "manifest_sha256": manifest_hash, **authorities}
        )
        write_report(args.output, report)
        print(json.dumps({"fit_shape": report["fit_shape"], "converged": report["converged"]}))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        code = str(error) if isinstance(error, AuditError) else type(error).__name__
        print("Neural cohort experiment failed: " + code, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
