"""Compare frozen B1 and a neural reranker on reviewed, unseen aT source products."""

import argparse
import json
import math
import warnings
from pathlib import Path

import numpy as np
from pydantic import Field
from sklearn.exceptions import ConvergenceWarning
from sklearn.neural_network import MLPRegressor

from pubburi_recommendation.at_source import audit_at_source
from pubburi_recommendation.baseline import ContractModel, ProductId
from pubburi_recommendation.catalog_audit import AuditError, SourceManifest, read_json
from pubburi_recommendation.content_model import (
    ContentProduct,
    FittedContentModel,
    digest,
    product_tokens,
)
from pubburi_recommendation.source_family_experiment import write_report
from scripts.evaluate_neural_cohort import MODEL_SETTINGS, encode

AT_K = 3
ALGORITHM = "b1-neural-rerank-at-heldout-v1"


class MaterialJudgment(ContractModel):
    material: str = Field(pattern=r"^[a-z][a-z-]{0,39}$")
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Protocol(ContractModel):
    review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    train_rows: list[ProductId] = Field(min_length=3, max_length=100)
    heldout: dict[str, MaterialJudgment] = Field(min_length=3, max_length=100)


def matrix(b1, products):
    columns = [b1.vectorizer.transform([product_tokens(row) for row in products]).toarray()]
    for field, scaler in sorted(b1.scalers.items()):
        values = [getattr(row, field) for row in products]
        observed = np.array([value is not None for value in values])
        scaled = np.zeros(len(values))
        if observed.any():
            scaled[observed] = np.clip(
                scaler.transform([[value] for value in values if value is not None])[:, 0], 0, 1
            )
        columns.extend([scaled[:, None], observed[:, None]])
    return np.column_stack(columns)


def metrics(order, relevant):
    hits = [position for position, item in enumerate(order[:AT_K]) if item in relevant]
    dcg = sum(1 / math.log2(position + 2) for position in hits)
    ideal = sum(1 / math.log2(position + 2) for position in range(min(AT_K, len(relevant))))
    return {"recall": len(hits) / len(relevant), "ndcg": dcg / ideal}


def evaluate(protocol, source_records, review_hash):
    if protocol.review_sha256 != review_hash:
        raise AuditError("heldout_review_hash_mismatch")
    train_ids = set(protocol.train_rows)
    judgments = {int(key): value for key, value in protocol.heldout.items()}
    if (
        len(train_ids) != len(protocol.train_rows)
        or {str(key) for key in judgments} != set(protocol.heldout)
        or train_ids & judgments.keys()
    ):
        raise AuditError("heldout_rows_must_be_canonical_unique_and_disjoint")
    reviewed = {row["source_row_number"]: row for row in source_records if row["review_evidence"]}
    if set(reviewed) != train_ids | judgments.keys():
        raise AuditError("heldout_partition_must_cover_exact_reviewed_rows")
    producers = {
        key: "".join(row["producer_name"].casefold().split()) if row["producer_name"] else ""
        for key, row in reviewed.items()
    }
    train_producers = {producers[key] for key in train_ids}
    heldout_producers = {producers[key] for key in judgments}
    if "" in producers.values() or train_producers & heldout_producers:
        raise AuditError("heldout_producer_groups_must_be_known_and_disjoint")
    if any(
        value.evidence_sha256 != reviewed[key]["review_evidence"]["sha256"]
        for key, value in judgments.items()
    ):
        raise AuditError("heldout_judgment_evidence_hash_mismatch")

    products = {
        key: ContentProduct(
            product_id=key,
            sku_group=f"offline-producer:{producers[key]}",
            available=True,  # Membership in the offline candidate pool only.
            category=row["category"],
            abv_percent=row["abv_percent"],
        )
        for key, row in reviewed.items()
    }
    training = [products[key] for key in sorted(train_ids)]
    b1 = FittedContentModel.fit(training)
    if b1.vectorizer is None:
        raise AuditError("heldout_requires_training_category_vocabulary")
    train = matrix(b1, training)
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always", ConvergenceWarning)
        d1 = MLPRegressor(**MODEL_SETTINGS).fit(
            train, train if train.shape[1] > 1 else train.ravel()
        )
    heldout_ids = sorted(judgments)
    latent = dict(
        zip(heldout_ids, encode(d1, matrix(b1, [products[k] for k in heldout_ids])), strict=True)
    )
    cases = []
    for key in heldout_ids:
        candidates = [
            products[other] for other in heldout_ids if producers[other] != producers[key]
        ]
        relevant = {
            row.product_id
            for row in candidates
            if judgments[row.product_id].material == judgments[key].material
        }
        base = b1.similar(products[key], candidates, limit=max(1, len(candidates)))
        positive = [item for item in base.items if item.score > 0]
        reranked = sorted(
            positive,
            key=lambda item: (
                -(item.score + max(0.0, float(latent[key] @ latent[item.product_id]))),
                item.product_id,
            ),
        )
        orders = {
            "b1": [row.product_id for row in positive],
            "d1": [row.product_id for row in reranked],
        }
        cases.append(
            {
                "query": key,
                "candidates": len(candidates),
                "positives": len(relevant),
                "orders": orders,
                "metrics": {name: metrics(order, relevant) for name, order in orders.items()}
                if relevant
                else None,
            }
        )
    labeled = [case["metrics"] for case in cases if case["metrics"] is not None]
    return {
        "algorithm": ALGORITHM,
        "scope": "offline_source_material_retrieval_not_service_acceptance",
        "cutoff": AT_K,
        "training": {
            "rows": len(training),
            "producers": len(train_producers),
            "features": train.shape[1],
        },
        "heldout": {
            "rows": len(heldout_ids),
            "producers": len(heldout_producers),
            "labeled_queries": len(labeled),
            "empty_rankings": sum(not case["orders"]["b1"] for case in cases),
        },
        "macro": {
            name: {
                metric: float(np.mean([row[name][metric] for row in labeled]))
                for metric in ("recall", "ndcg")
            }
            for name in ("b1", "d1")
        }
        if labeled
        else None,
        "b1_fit": b1.fingerprint,
        "d1_fit": digest(
            {
                "b1": b1.fingerprint,
                "settings": MODEL_SETTINGS,
                "weights": [x.tolist() for x in d1.coefs_],
                "biases": [x.tolist() for x in d1.intercepts_],
            }
        ),
        "converged": not any(issubclass(item.category, ConvergenceWarning) for item in emitted),
        "iterations": int(d1.n_iter_),
        "cases": cases,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "input", "receipt", "review", "protocol", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--evidence", type=Path, action="append", required=True)
    args = parser.parse_args()
    try:
        if ".pubburi" not in args.output.resolve().parts or args.output.exists():
            raise AuditError("heldout_requires_new_private_output")
        data, manifest_hash = read_json(args.manifest)
        manifest = SourceManifest.model_validate(data)
        if manifest.source_id != "at-traditional-liquor" or not (
            manifest.local_structured_normalization and manifest.structured_feature_fit
        ):
            raise AuditError("heldout_source_fit_not_approved")
        raw_protocol, protocol_hash = read_json(args.protocol)
        protocol = Protocol.model_validate(raw_protocol)
        source, records, _ = audit_at_source(
            manifest_hash, args.input, args.receipt, args.review, args.evidence
        )
        report = evaluate(protocol, records, source["review_sha256"])
        report["protocol_sha256"] = protocol_hash
        report["source_sha256"] = source["input_sha256"]
        write_report(args.output, report)
        print(
            json.dumps({key: report[key] for key in ("training", "heldout", "macro", "converged")})
        )
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        code = str(error) if isinstance(error, AuditError) else type(error).__name__
        parser.exit(2, f"Heldout comparison failed: {code}\n")


if __name__ == "__main__":
    raise SystemExit(main())
