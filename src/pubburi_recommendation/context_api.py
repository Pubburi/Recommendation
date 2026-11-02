"""Explicit cart/demo-order context using existing reference facts, never co-purchase data."""

from typing import Literal, Self

from pydantic import Field, model_validator

from pubburi_recommendation.baseline import Constraints, ContractModel, ProductId
from pubburi_recommendation.content_contracts import (
    ALGORITHM,
    ContentItem,
    ContentProduct,
    GroupId,
    Score,
    validate_catalog,
)


class ContextRecommendationRequest(ContractModel):
    catalog: list[ContentProduct] = Field(max_length=1000)
    reference_product_ids: list[ProductId] = Field(min_length=1, max_length=20)
    constraints: Constraints = Field(default_factory=Constraints)
    min_relevance_score: Score = 0.0
    limit: int = Field(default=12, ge=1, le=100)

    @model_validator(mode="after")
    def unique_catalog_and_references(self) -> Self:
        validate_catalog(self.catalog, allow_empty=True)
        if len(self.reference_product_ids) != len(set(self.reference_product_ids)):
            raise ValueError("context_reference_product_ids_must_be_unique")
        return self


class ContextReference(ContractModel):
    product_id: ProductId
    sku_group: GroupId | None
    state: Literal["missing", "unavailable", "available"]
    # None means not evaluated; unavailable/missing facts never become an empty profile.
    supported_profile_tokens: int | None = None
    unknown_profile_tokens: int | None = None
    active_numeric_preferences: list[str] | None = None
    fallback_reason: (
        Literal["no_eligible_products", "no_supported_preferences", "no_matching_features"] | None
    ) = None


class ContextMatch(ContractModel):
    product_id: ProductId
    reference_product_id: ProductId


class ContextRecommendationResponse(ContractModel):
    algorithm: Literal["b1-tfidf-minmax-v1"] = ALGORITHM
    aggregation_algorithm: Literal["r07-max-reference-v1"] = "r07-max-reference-v1"
    fit_scope: Literal["request_catalog"] = "request_catalog"
    profile_source: Literal["explicit_context_product_facts"] = "explicit_context_product_facts"
    reference_group_policy: Literal["exclude_all_known_reference_groups"] = (
        "exclude_all_known_reference_groups"
    )
    representation_fitted: bool
    model_fingerprint: str | None = None
    min_relevance_score: Score
    references: list[ContextReference]
    evaluated_reference_count: int = Field(ge=0, le=20)
    eligible_count: int | None = Field(default=None, ge=0, le=1000)
    excluded_reference_group_count: int | None = Field(default=None, ge=0, le=1000)
    items: list[ContentItem]
    matches: list[ContextMatch]
    fallback_reason: (
        Literal[
            "no_usable_references",
            "no_eligible_products",
            "no_supported_preferences",
            "no_matching_features",
            "below_relevance_floor",
        ]
        | None
    ) = None


def recommend_context(request: ContextRecommendationRequest) -> ContextRecommendationResponse:
    by_id = {product.product_id: product for product in request.catalog}
    references = []
    usable = []
    groups = set()
    for pid in sorted(request.reference_product_ids):
        product = by_id.get(pid)
        if product is not None:
            # Even an unavailable context product's known variants cannot be recommended.
            groups.add(product.sku_group)
        reference = ContextReference(
            product_id=pid,
            sku_group=None if product is None else product.sku_group,
            state="missing"
            if product is None
            else "available"
            if product.available
            else "unavailable",
        )
        references.append(reference)
        if product is not None and product.available:
            usable.append((product, reference))
    metadata = {
        "references": references,
        "evaluated_reference_count": len(usable),
        "min_relevance_score": request.min_relevance_score,
    }
    if not usable:
        # Keep startup, health/B0 and a context without usable references model-independent.
        return ContextRecommendationResponse(
            **metadata,
            representation_fitted=False,
            items=[],
            matches=[],
            fallback_reason="no_usable_references",
        )

    from pubburi_recommendation.content_model import FittedContentModel

    model = FittedContentModel.fit(request.catalog)
    candidates = [product for product in request.catalog if product.sku_group not in groups]
    best = {}
    eligible_count = 0
    positive_match = False
    supported_reference = False
    for product, reference in usable:
        result = model.similar(product, candidates, request.constraints, limit=request.limit)
        eligible_count = result.eligible_count
        reference.supported_profile_tokens = result.supported_profile_tokens
        reference.unknown_profile_tokens = result.unknown_profile_tokens
        reference.active_numeric_preferences = result.active_numeric_preferences
        reference.fallback_reason = result.fallback_reason
        supported_reference |= result.fallback_reason != "no_supported_preferences"
        for item in result.items:
            if item.score <= 0:
                continue
            positive_match = True
            if item.score < request.min_relevance_score:
                continue
            previous = best.get(item.product_id)
            # References are sorted, so equal scores keep the smaller reference ID.
            if previous is None or item.score > previous[0].score:
                best[item.product_id] = (item, product.product_id)
    # The global top K under max must be in at least one reference's top K: otherwise
    # that reference already supplies K candidates ahead of it under the same score/ID order.
    selected = sorted(best.values(), key=lambda pair: (-pair[0].score, pair[0].product_id))[
        : request.limit
    ]
    representation_fitted = model.vectorizer is not None or bool(model.scalers)
    return ContextRecommendationResponse(
        **metadata,
        representation_fitted=representation_fitted,
        model_fingerprint=model.fingerprint if representation_fitted else None,
        eligible_count=eligible_count,
        excluded_reference_group_count=len(request.catalog) - len(candidates),
        items=[item for item, _ in selected],
        matches=[
            ContextMatch(product_id=item.product_id, reference_product_id=pid)
            for item, pid in selected
        ],
        fallback_reason=None
        if selected
        else "no_eligible_products"
        if not eligible_count
        else "no_supported_preferences"
        if not supported_reference
        else "below_relevance_floor"
        if positive_match
        else "no_matching_features",
    )
