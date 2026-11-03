"""R03 adapter for existing product similarity, without inventing user preferences."""

from typing import Literal, Self

from pydantic import Field, model_validator

from pubburi_recommendation.baseline import Constraints, ContractModel, ProductId
from pubburi_recommendation.content_api import ContentRecommendationResponse
from pubburi_recommendation.content_contracts import ContentProduct, GroupId, validate_catalog


class SimilarRecommendationRequest(ContractModel):
    catalog: list[ContentProduct] = Field(max_length=1000)
    reference_product_id: ProductId
    constraints: Constraints = Field(default_factory=Constraints)
    limit: int = Field(default=12, ge=1, le=100)
    include_explanations: bool = Field(default=False, exclude_if=lambda value: not value)

    @model_validator(mode="after")
    def unique_catalog(self) -> Self:
        validate_catalog(self.catalog, allow_empty=True)
        return self


class SimilarRecommendationResponse(ContentRecommendationResponse):
    reference_product_id: ProductId
    reference_sku_group: GroupId | None
    reference_state: Literal["missing", "unavailable", "available"]
    profile_source: Literal["reference_product_facts"] = "reference_product_facts"
    reference_group_policy: Literal["exclude_reference_group"] = "exclude_reference_group"
    # Without a usable reference its group cannot define the candidate set.
    # None means not evaluated, rather than an observed zero eligible candidates.
    eligible_count: int | None = Field(default=None, ge=0, le=1000)
    excluded_reference_group_count: int | None = Field(default=None, ge=0, le=1000)
    fallback_reason: (
        Literal[
            "reference_not_in_catalog",
            "reference_unavailable",
            "no_eligible_products",
            "no_supported_preferences",
            "no_matching_features",
        ]
        | None
    ) = None


def recommend_similar(request: SimilarRecommendationRequest) -> SimilarRecommendationResponse:
    reference = next(
        (p for p in request.catalog if p.product_id == request.reference_product_id), None
    )
    metadata = {
        "reference_product_id": request.reference_product_id,
        "reference_sku_group": None if reference is None else reference.sku_group,
        "reference_state": "missing"
        if reference is None
        else "available"
        if reference.available
        else "unavailable",
    }
    if reference is None or not reference.available:
        # Schema/startup and unusable references require no model runtime or fit.
        return SimilarRecommendationResponse(
            **metadata,
            representation_fitted=False,
            items=[],
            supported_profile_tokens=0,
            unknown_profile_tokens=0,
            active_numeric_preferences=[],
            fallback_reason="reference_not_in_catalog"
            if reference is None
            else "reference_unavailable",
        )

    from pubburi_recommendation.content_model import FittedContentModel

    # Request-local known-catalog fit, including the reference. No model/cache/user state.
    model = FittedContentModel.fit(request.catalog)
    candidates = [p for p in request.catalog if p.sku_group != reference.sku_group]
    result = model.similar(
        reference,
        candidates,
        request.constraints,
        limit=request.limit,
        include_explanations=request.include_explanations,
    )
    values = result.model_dump()
    representation_fitted = model.vectorizer is not None or bool(model.scalers)
    if not representation_fitted:
        values["model_fingerprint"] = None
    # A deterministic zero-score fallback is not evidence of a similar product.
    # Scarcity never restores the reference, its variants, hard failures or unrelated fill.
    values["items"] = [item for item in result.items if item.score > 0]
    return SimilarRecommendationResponse(
        **metadata,
        **values,
        representation_fitted=representation_fitted,
        excluded_reference_group_count=len(request.catalog) - len(candidates),
    )
