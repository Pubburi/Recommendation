"""Request-local HTTP adapter for the existing B1 known-catalog representation engine."""

from typing import Literal, Self

from pydantic import Field, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from pubburi_recommendation.baseline import Constraints, ContractModel
from pubburi_recommendation.content_contracts import (
    ContentProduct,
    ContentProfile,
    ContentResponse,
    profile_tokens,
    validate_catalog,
)
from pubburi_recommendation.preference_input import resolve_preferences
from pubburi_recommendation.search_phrases import SearchPreferenceSnapshot


class ContentRecommendationRequest(ContractModel):
    catalog: list[ContentProduct] = Field(max_length=1000)
    profile: ContentProfile = Field(default_factory=ContentProfile)
    constraints: Constraints = Field(default_factory=Constraints)
    limit: int = Field(default=12, ge=1, le=100)
    include_explanations: bool = Field(default=False, exclude_if=lambda value: not value)
    preferences: SearchPreferenceSnapshot | SkipJsonSchema[None] = Field(
        default=None,
        exclude_if=lambda value: value is None,
        json_schema_extra=lambda schema: schema.pop("default", None),
    )

    @field_validator("preferences")
    @classmethod
    def explicit_preferences_require_snapshot(cls, value):
        if value is None:
            raise ValueError("preferences_require_complete_backend_snapshot")
        return value

    @model_validator(mode="after")
    def unique_catalog(self) -> Self:
        validate_catalog(self.catalog, allow_empty=True)
        if self.preferences is not None:
            if "profile" in self.model_fields_set:
                raise ValueError("preferences_and_profile_are_mutually_exclusive")
            resolve_preferences(self.preferences, self.constraints)
        return self

    def resolved(self) -> Self:
        if self.preferences is None:
            return self
        profile, constraints = resolve_preferences(self.preferences, self.constraints)
        return self.model_copy(
            update={"profile": profile, "constraints": constraints, "preferences": None}
        )


class ContentRecommendationResponse(ContentResponse):
    fit_scope: Literal["request_catalog"] = "request_catalog"
    representation_fitted: bool
    model_fingerprint: str | None = None


def recommend_content(request: ContentRecommendationRequest) -> ContentRecommendationResponse:
    request = request.resolved()
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
    result = model.rank(
        request.catalog,
        request.profile,
        request.constraints,
        limit=request.limit,
        include_explanations=request.include_explanations,
    )
    # Executing fit on an uninformative catalog is not a usable learned representation.
    representation_fitted = model.vectorizer is not None or bool(model.scalers)
    values = result.model_dump()
    if not representation_fitted:
        values["model_fingerprint"] = None
    return ContentRecommendationResponse(representation_fitted=representation_fitted, **values)
