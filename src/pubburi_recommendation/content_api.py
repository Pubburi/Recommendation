"""Request-local HTTP adapter for the existing B1 known-catalog representation engine."""

from typing import Literal, Self

from pydantic import Field, model_validator

from pubburi_recommendation.baseline import Constraints, ContractModel
from pubburi_recommendation.content_contracts import (
    ContentProduct,
    ContentProfile,
    ContentResponse,
    profile_tokens,
    validate_catalog,
)


class ContentRecommendationRequest(ContractModel):
    catalog: list[ContentProduct] = Field(max_length=1000)
    profile: ContentProfile = Field(default_factory=ContentProfile)
    constraints: Constraints = Field(default_factory=Constraints)
    limit: int = Field(default=12, ge=1, le=100)

    @model_validator(mode="after")
    def unique_catalog(self) -> Self:
        validate_catalog(self.catalog, allow_empty=True)
        return self


class ContentRecommendationResponse(ContentResponse):
    fit_scope: Literal["request_catalog"] = "request_catalog"
    representation_fitted: bool
    model_fingerprint: str | None = None


def recommend_content(request: ContentRecommendationRequest) -> ContentRecommendationResponse:
    if not request.catalog:
        return ContentRecommendationResponse(
            representation_fitted=False,
            items=[],
            eligible_count=0,
            supported_profile_tokens=0,
            unknown_profile_tokens=len(profile_tokens(request.profile)),
            active_numeric_preferences=[],
            fallback_reason="no_eligible_products",
        )
    # Schema/startup and empty inputs must not import the numerical/model runtime.
    from pubburi_recommendation.content_model import FittedContentModel

    # Fit only this explicitly supplied catalog; no shared model/cache/user state is retained.
    model = FittedContentModel.fit(request.catalog)
    result = model.rank(request.catalog, request.profile, request.constraints, limit=request.limit)
    # Executing fit on an uninformative catalog is not a usable learned representation.
    representation_fitted = model.vectorizer is not None or bool(model.scalers)
    values = result.model_dump()
    if not representation_fitted:
        values["model_fingerprint"] = None
    return ContentRecommendationResponse(representation_fitted=representation_fitted, **values)
