"""Opt-in R08 reranking of the existing B1 pool; no learned user preferences or shared state."""

from typing import Annotated, Literal

from pydantic import Field

from pubburi_recommendation.baseline import ContractModel, ProductId
from pubburi_recommendation.content_api import (
    ContentRecommendationRequest,
    ContentRecommendationResponse,
    recommend_content,
)
from pubburi_recommendation.content_contracts import GroupId, Score

POOL_LIMIT = 100


class ExplorationPolicy(ContractModel):
    # Initial explicit rules, not a fitted or user-validated optimum.
    relevance_weight: float = Field(default=0.7, ge=0.5, le=1, allow_inf_nan=False)
    min_relevance_score: Score = 0.0


class ExplorationRequest(ContentRecommendationRequest):
    policy: ExplorationPolicy = Field(default_factory=ExplorationPolicy)


class ExplorationSelection(ContractModel):
    product_id: ProductId
    sku_group: GroupId
    selection_score: Annotated[float, Field(ge=-1, le=1, allow_inf_nan=False)]
    redundancy_penalty_input: Score
    max_observed_text_similarity: Score | None
    basis: Literal["highest_relevance_anchor", "observed_text", "unknown_conservative"]


class ExplorationResponse(ContentRecommendationResponse):
    reranking_algorithm: Literal["r08-text-mmr-group-v1"] = "r08-text-mmr-group-v1"
    policy: ExplorationPolicy
    candidate_pool_limit: Literal[100] = POOL_LIMIT
    candidate_pool_size: int = Field(ge=0, le=POOL_LIMIT)
    pool_truncated: bool
    relevance_pool_size: int = Field(ge=0, le=POOL_LIMIT)
    selected_count: int = Field(ge=0, le=POOL_LIMIT)
    selected_group_count: int = Field(ge=0, le=POOL_LIMIT)
    exploration_reason: Literal["selected", "baseline_fallback", "below_relevance_floor"]
    selections: list[ExplorationSelection]


def recommend_exploration(request: ExplorationRequest) -> ExplorationResponse:
    if not request.catalog:
        base = recommend_content(request)
        return ExplorationResponse(
            **base.model_dump(),
            policy=request.policy,
            candidate_pool_size=0,
            pool_truncated=False,
            relevance_pool_size=0,
            selected_count=0,
            selected_group_count=0,
            exploration_reason="baseline_fallback",
            selections=[],
        )
    # Preserve the lightweight schema/startup path; fit only this explicit request catalog.
    from pubburi_recommendation.content_model import FittedContentModel, product_tokens

    model = FittedContentModel.fit(request.catalog)
    base = model.rank(request.catalog, request.profile, request.constraints, limit=POOL_LIMIT)
    values = base.model_dump()
    values["representation_fitted"] = model.vectorizer is not None or bool(model.scalers)
    if not values["representation_fitted"]:
        values["model_fingerprint"] = None
    pool = (
        [
            item
            for item in base.items
            if item.score > 0 and item.score >= request.policy.min_relevance_score
        ]
        if base.fallback_reason is None
        else []
    )
    by_id = {product.product_id: product for product in request.catalog}
    known = [False] * len(pool)
    similarities = None
    if pool and model.vectorizer is not None:
        vectors = model.vectorizer.transform(
            [product_tokens(by_id[item.product_id]) for item in pool]
        )
        known = [vectors[row].nnz > 0 for row in range(len(pool))]
        # At most 100 x 100, not an unbounded catalog matrix or a second ranking model.
        similarities = (vectors @ vectors.T).toarray()
    remaining = list(range(len(pool)))
    selected, selections, selected_indices, groups = [], [], [], set()
    while remaining and len(selected) < request.limit:
        options = []
        for index in remaining:
            item = pool[index]
            if by_id[item.product_id].sku_group in groups:
                continue
            if not selected_indices:
                redundancy, observed, basis = 0.0, None, "highest_relevance_anchor"
            elif not known[index] or any(not known[other] for other in selected_indices):
                # Unknown/zero vectors supply no novelty evidence. Never reward absence
                # of facts with the zero similarity of an empty sparse representation.
                redundancy, observed, basis = 1.0, None, "unknown_conservative"
            else:
                redundancy = max(
                    max(0.0, min(1.0, float(similarities[index, other])))
                    for other in selected_indices
                )
                observed, basis = redundancy, "observed_text"
            score = (
                request.policy.relevance_weight * item.score
                - (1 - request.policy.relevance_weight) * redundancy
            )
            options.append(
                ((-score, -item.score, item.product_id), index, score, redundancy, observed, basis)
            )
        if not options:
            break
        _, index, score, redundancy, observed, basis = min(options)
        item = pool[index]
        selected.append(item)
        selected_indices.append(index)
        groups.add(by_id[item.product_id].sku_group)
        remaining.remove(index)
        selections.append(
            ExplorationSelection(
                product_id=item.product_id,
                sku_group=by_id[item.product_id].sku_group,
                selection_score=score,
                redundancy_penalty_input=redundancy,
                max_observed_text_similarity=observed,
                basis=basis,
            )
        )
    values["items"] = selected  # Preserve original B1 scores, reasons and contributions verbatim.
    return ExplorationResponse(
        **values,
        policy=request.policy,
        candidate_pool_size=len(base.items),
        pool_truncated=base.eligible_count > POOL_LIMIT,
        relevance_pool_size=len(pool),
        selected_count=len(selected),
        selected_group_count=len(groups),
        selections=selections,
        exploration_reason="baseline_fallback"
        if base.fallback_reason is not None
        else "selected"
        if selected
        else "below_relevance_floor",
    )
