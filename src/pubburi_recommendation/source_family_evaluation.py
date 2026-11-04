"""Frozen source-fact retrieval judgments and metrics; no model fit or ranking implementation."""

import math
from typing import Annotated

from pydantic import Field, StringConstraints, model_validator

from pubburi_recommendation.baseline import ContractModel
from pubburi_recommendation.catalog_audit import AuditError

SourceId = Annotated[str, StringConstraints(pattern=r"^Q[1-9][0-9]{0,30}$")]


class FamilyRetrievalCase(ContractModel):
    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,99}$")
    query_id: SourceId
    candidate_ids: list[SourceId] = Field(min_length=1, max_length=1000)
    relevant_ids: list[SourceId] = Field(max_length=1000)
    cutoffs: list[Annotated[int, Field(ge=1, le=1000)]] = Field(min_length=1, max_length=20)
    fact_basis: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def declared_candidate_judgments(self):
        if len(set(self.candidate_ids)) != len(self.candidate_ids):
            raise ValueError("retrieval_candidates_must_be_unique")
        if len(set(self.relevant_ids)) != len(self.relevant_ids) or not set(
            self.relevant_ids
        ) <= set(self.candidate_ids):
            raise ValueError("relevance_must_be_unique_declared_candidates")
        if self.query_id in self.candidate_ids:
            raise ValueError("query_cannot_be_its_own_candidate")
        if self.cutoffs != sorted(set(self.cutoffs)):
            raise ValueError("retrieval_cutoffs_must_be_sorted_and_unique")
        return self


class RetrievedFamily(ContractModel):
    source_record_id: SourceId
    score: float = Field(ge=0, le=1, allow_inf_nan=False)


def inspect_retrieval(case: FamilyRetrievalCase, ranked: list[dict]) -> dict:
    """Inspect complete results and apply manually frozen labels, never derive gold from scores."""
    rows = [RetrievedFamily.model_validate(row) for row in ranked]
    ids = [row.source_record_id for row in rows]
    if len(ids) != len(set(ids)) or set(ids) != set(case.candidate_ids):
        raise AuditError("retrieval_results_must_cover_exact_declared_candidates")
    if rows != sorted(rows, key=lambda row: (-row.score, row.source_record_id)):
        raise AuditError("retrieval_results_must_follow_score_and_source_id_ties")
    gold = set(case.relevant_ids)
    baseline = sorted(case.candidate_ids)

    def metrics(order):
        if not gold:
            return {"status": "not_calculated", "reason": "no_positive_fact_judgments"}
        values = {}
        for cutoff in case.cutoffs:
            prefix = order[:cutoff]
            hits = sum(qid in gold for qid in prefix)
            dcg = sum(1 / math.log2(rank + 2) for rank, qid in enumerate(prefix) if qid in gold)
            ideal = sum(1 / math.log2(rank + 2) for rank in range(min(cutoff, len(gold))))
            values[str(cutoff)] = {"recall": hits / len(gold), "ndcg": dcg / ideal}
        return {"status": "calculated", "at_k": values}

    return {
        "case_id": case.case_id,
        "query_id": case.query_id,
        "candidate_count": len(case.candidate_ids),
        "positive_fact_judgments": len(gold),
        "fact_basis": case.fact_basis,
        "reference_source_id_order": baseline,
        "representation_cosine": ranked,
        "reference_metrics": metrics(baseline),
        "representation_metrics": metrics(ids),
    }


def aggregate_retrieval(cases: list[dict]) -> dict:
    """Macro means include only positive-label queries, with a denominator per cutoff."""
    summary = {}
    for name in ("reference_metrics", "representation_metrics"):
        by_cutoff = {}
        for case in cases:
            for cutoff, values in case[name].get("at_k", {}).items():
                by_cutoff.setdefault(cutoff, []).append(values)
        summary[name] = {
            cutoff: {
                "queries": len(rows),
                "mean_recall": sum(row["recall"] for row in rows) / len(rows),
                "mean_ndcg": sum(row["ndcg"] for row in rows) / len(rows),
            }
            for cutoff, rows in sorted(by_cutoff.items(), key=lambda row: int(row[0]))
        }
    calculated = sum(row["representation_metrics"]["status"] == "calculated" for row in cases)
    return {
        "status": "calculated" if calculated else "not_calculated",
        "grain": "exact_source_class_fact_retrieval_not_user_preference",
        "query_count": len(cases),
        "positive_label_queries": calculated,
        "omitted_no_positive_queries": len(cases) - calculated,
        "macro_means": summary,
        "cases": cases,
        "limitations": [
            "manual_judgments_from_source_facts_not_human_preference_or_behavior",
            "same_class_is_a_feature_and_a_fact_relation_not_independent_semantic_truth",
            "one_query_or_tiny_candidate_pool_cannot_establish_service_quality",
            "source_id_lexical_reference_is_not_the_backend_service_b0_contract",
        ],
    }
