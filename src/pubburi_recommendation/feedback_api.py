"""Explicit positive/not-interested feedback over existing request-local B1 facts."""

from typing import Literal, Self

from pydantic import Field, model_validator

from pubburi_recommendation.baseline import ContractModel, ProductId
from pubburi_recommendation.content_api import (
    ContentRecommendationRequest,
    ContentRecommendationResponse,
)
from pubburi_recommendation.content_contracts import GroupId, profile_tokens


class ExplicitFeedback(ContractModel):
    positive_product_ids: list[ProductId] = Field(default_factory=list, max_length=20)
    not_interested_product_ids: list[ProductId] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def unique_feedback(self) -> Self:
        for ids in (self.positive_product_ids, self.not_interested_product_ids):
            if len(ids) != len(set(ids)):
                raise ValueError("feedback_product_ids_must_be_unique")
        return self


class FeedbackRecommendationRequest(ContentRecommendationRequest):
    feedback: ExplicitFeedback = Field(default_factory=ExplicitFeedback)


class FeedbackProduct(ContractModel):
    product_id: ProductId
    sku_group: GroupId | None
    state: Literal["missing", "unavailable", "blocked", "available"]


class PositiveFeedback(FeedbackProduct):
    # Missing/unavailable/negative-blocked references have not been scored.
    supported_profile_tokens: int | None = None
    unknown_profile_tokens: int | None = None
    active_numeric_preferences: list[str] | None = None
    fallback_reason: (
        Literal["no_eligible_products", "no_supported_preferences", "no_matching_features"] | None
    ) = None


class FeedbackMatch(ContractModel):
    product_id: ProductId
    source: Literal["profile", "positive_feedback", "baseline"]
    positive_product_id: ProductId | None = None


class FeedbackRecommendationResponse(ContentRecommendationResponse):
    feedback_algorithm: Literal["r05-max-explicit-feedback-v1"] = "r05-max-explicit-feedback-v1"
    feedback_group_policy: Literal["exclude_all_known_feedback_groups"] = (
        "exclude_all_known_feedback_groups"
    )
    ranking_mode: Literal["positive_feedback", "profile_fallback"]
    positive_references: list[PositiveFeedback]
    not_interested_references: list[FeedbackProduct]
    evaluated_positive_count: int = Field(ge=0, le=20)
    informative_positive_count: int = Field(ge=0, le=20)
    excluded_not_interested_count: int = Field(ge=0, le=1000)
    excluded_positive_group_count: int = Field(ge=0, le=1000)
    matches: list[FeedbackMatch]


def recommend_feedback(request: FeedbackRecommendationRequest) -> FeedbackRecommendationResponse:
    by_id = {product.product_id: product for product in request.catalog}
    negative_ids = set(request.feedback.not_interested_product_ids)
    negative_groups = {by_id[pid].sku_group for pid in negative_ids if pid in by_id}
    positive_groups = {
        by_id[pid].sku_group for pid in request.feedback.positive_product_ids if pid in by_id
    }
    negatives = [
        FeedbackProduct(
            product_id=pid,
            sku_group=by_id[pid].sku_group if pid in by_id else None,
            state="missing"
            if pid not in by_id
            else "available"
            if by_id[pid].available
            else "unavailable",
        )
        for pid in sorted(negative_ids)
    ]
    positives = []
    usable = []
    for pid in sorted(request.feedback.positive_product_ids):
        product = by_id.get(pid)
        reference = PositiveFeedback(
            product_id=pid,
            sku_group=None if product is None else product.sku_group,
            state="missing"
            if product is None
            else "blocked"
            if pid in negative_ids or product.sku_group in negative_groups
            else "unavailable"
            if not product.available
            else "available",
        )
        positives.append(reference)
        if reference.state == "available":
            usable.append((product, reference))
    nonnegative = [
        product
        for product in request.catalog
        if product.product_id not in negative_ids and product.sku_group not in negative_groups
    ]
    candidates = [product for product in nonnegative if product.sku_group not in positive_groups]
    metadata = {
        "positive_references": positives,
        "not_interested_references": negatives,
        "excluded_not_interested_count": len(request.catalog) - len(nonnegative),
        "excluded_positive_group_count": len(nonnegative) - len(candidates),
    }
    if not request.catalog:
        return FeedbackRecommendationResponse(
            **metadata,
            ranking_mode="profile_fallback",
            representation_fitted=False,
            items=[],
            matches=[],
            eligible_count=0,
            evaluated_positive_count=0,
            informative_positive_count=0,
            supported_profile_tokens=0,
            unknown_profile_tokens=len(profile_tokens(request.profile)),
            active_numeric_preferences=[],
            fallback_reason="no_eligible_products",
        )

    from pubburi_recommendation.content_model import FittedContentModel

    # Fit the explicit catalog once, just as content does; feedback never trains user state.
    model = FittedContentModel.fit(request.catalog)
    explicit = model.rank(
        candidates,
        request.profile,
        request.constraints,
        limit=request.limit,
        include_explanations=request.include_explanations,
    )
    best = {
        item.product_id: (item, FeedbackMatch(product_id=item.product_id, source="profile"))
        for item in explicit.items
        if item.score > 0
    }
    informative_count = 0
    for product, reference in usable:
        result = model.similar(
            product,
            candidates,
            request.constraints,
            limit=request.limit,
            include_explanations=request.include_explanations,
        )
        reference.supported_profile_tokens = result.supported_profile_tokens
        reference.unknown_profile_tokens = result.unknown_profile_tokens
        reference.active_numeric_preferences = result.active_numeric_preferences
        reference.fallback_reason = result.fallback_reason
        informative_count += bool(
            result.supported_profile_tokens or result.active_numeric_preferences
        )
        for item in result.items:
            previous = best.get(item.product_id)
            # Explicit profile wins exact ties, then sorted positive IDs keep the smaller ID.
            if item.score > 0 and (previous is None or item.score > previous[0].score):
                best[item.product_id] = (
                    item,
                    FeedbackMatch(
                        product_id=item.product_id,
                        source="positive_feedback",
                        positive_product_id=product.product_id,
                    ),
                )
    # For max aggregation every global top-K item is in some source's top K under the
    # same score/ID order. No need to truncate the candidate set or refit per source.
    selected = sorted(best.values(), key=lambda pair: (-pair[0].score, pair[0].product_id))[
        : request.limit
    ]
    values = explicit.model_dump()
    if informative_count:
        # Positive-evidence mode never pads a shortage with unrelated zero-score rows.
        values["items"] = [item for item, _ in selected]
        values["fallback_reason"] = (
            "no_eligible_products"
            if not explicit.eligible_count
            else None
            if selected
            else "no_matching_features"
        )
        matches = [match for _, match in selected]
    else:
        # Preserve the original profile/B0 fallback, without relabeling it positive evidence.
        matches = [
            FeedbackMatch(
                product_id=item.product_id,
                source="profile" if item.score > 0 else "baseline",
            )
            for item in explicit.items
        ]
    fitted = model.vectorizer is not None or bool(model.scalers)
    if not fitted:
        values["model_fingerprint"] = None
    return FeedbackRecommendationResponse(
        **values,
        **metadata,
        representation_fitted=fitted,
        ranking_mode="positive_feedback" if informative_count else "profile_fallback",
        evaluated_positive_count=len(usable),
        informative_positive_count=informative_count,
        matches=matches,
    )
