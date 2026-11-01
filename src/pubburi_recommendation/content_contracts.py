"""Lightweight B1 data contracts; no model-library import or fit at service startup."""

from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from pubburi_recommendation.baseline import Abv, CatalogProduct, Category, ContractModel, ProductId

ALGORITHM = "b1-tfidf-minmax-v1"
Tag = Annotated[
    str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=1, max_length=40)
]
GroupId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
Volume = Annotated[int, Field(ge=1, le=1_000_000)]
Score = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class ContentProduct(CatalogProduct):
    """Caller-reviewed SKU facts; source permission is a separate catalog-audit decision."""

    sku_group: GroupId
    taste_tags: list[Tag] | None = Field(default=None, max_length=20)
    aroma_tags: list[Tag] | None = Field(default=None, max_length=20)
    volume_ml: Volume | None = None

    @model_validator(mode="after")
    def unique_tags(self) -> Self:
        for tags in (self.taste_tags, self.aroma_tags):
            if tags is not None and len(tags) != len(set(tags)):
                raise ValueError("normalized_tags_must_be_unique")
        return self


class ContentProfile(ContractModel):
    categories: list[Category] = Field(default_factory=list, max_length=32)
    taste_tags: list[Tag] = Field(default_factory=list, max_length=20)
    aroma_tags: list[Tag] = Field(default_factory=list, max_length=20)
    preferred_abv_percent: Abv | None = None
    preferred_volume_ml: Volume | None = None

    @model_validator(mode="after")
    def unique_preferences(self) -> Self:
        for values in (self.categories, self.taste_tags, self.aroma_tags):
            if len(values) != len(set(values)):
                raise ValueError("normalized_preferences_must_be_unique")
        return self


class Contribution(ContractModel):
    component: Literal["text", "abv_percent", "volume_ml"]
    feature: str
    contribution: Score


class ContentItem(ContractModel):
    product_id: ProductId
    score: Score
    reasons: list[str]
    contributions: list[Contribution]


class ContentResponse(ContractModel):
    algorithm: Literal["b1-tfidf-minmax-v1"] = ALGORITHM
    model_fingerprint: str
    items: list[ContentItem]
    eligible_count: int
    supported_profile_tokens: int
    unknown_profile_tokens: int
    active_numeric_preferences: list[str]
    fallback_reason: (
        Literal["no_eligible_products", "no_supported_preferences", "no_matching_features"] | None
    ) = None


def profile_tokens(profile: ContentProfile) -> list[str]:
    return sorted(
        [f"category:{category}" for category in profile.categories]
        + [f"taste:{tag}" for tag in profile.taste_tags]
        + [f"aroma:{tag}" for tag in profile.aroma_tags]
    )


def validate_catalog(products: list[ContentProduct], *, allow_empty: bool = False) -> None:
    if not isinstance(products, list) or any(not isinstance(p, ContentProduct) for p in products):
        raise ValueError("validated_product_list_required")
    if len(products) > 1000 or (not products and not allow_empty):
        raise ValueError("catalog_requires_1_to_1000_products")
    if len({p.product_id for p in products}) != len(products):
        raise ValueError("catalog_product_ids_must_be_unique")
