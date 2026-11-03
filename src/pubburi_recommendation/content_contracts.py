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
PositiveScore = Annotated[float, Field(gt=0, le=1, allow_inf_nan=False)]


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


class ProfileComparison(ContractModel):
    kind: Literal["profile"] = "profile"


class ReferenceComparison(ContractModel):
    kind: Literal["reference_product"] = "reference_product"
    product_id: ProductId


class CategoryScoreEvidence(ContractModel):
    kind: Literal["category_match"] = "category_match"
    label: Literal["주종 일치"] = "주종 일치"
    actual_value: Category
    target_value: Category
    contribution: PositiveScore


class TasteScoreEvidence(ContractModel):
    kind: Literal["taste_match"] = "taste_match"
    label: Literal["맛 태그 일치"] = "맛 태그 일치"
    actual_value: Tag
    target_value: Tag
    contribution: PositiveScore


class AromaScoreEvidence(ContractModel):
    kind: Literal["aroma_match"] = "aroma_match"
    label: Literal["향 태그 일치"] = "향 태그 일치"
    actual_value: Tag
    target_value: Tag
    contribution: PositiveScore


class AbvScoreEvidence(ContractModel):
    kind: Literal["abv_comparison"] = "abv_comparison"
    label: Literal["도수 비교 근거"] = "도수 비교 근거"
    actual_value: Abv
    target_value: Abv
    unit: Literal["vol%"] = "vol%"
    contribution: PositiveScore


class VolumeScoreEvidence(ContractModel):
    kind: Literal["volume_comparison"] = "volume_comparison"
    label: Literal["용량 비교 근거"] = "용량 비교 근거"
    actual_value: Volume
    target_value: Volume
    unit: Literal["mL"] = "mL"
    contribution: PositiveScore


ScoreEvidence = Annotated[
    CategoryScoreEvidence
    | TasteScoreEvidence
    | AromaScoreEvidence
    | AbvScoreEvidence
    | VolumeScoreEvidence,
    Field(discriminator="kind"),
]


class AvailabilityEvidence(ContractModel):
    kind: Literal["availability_filter"] = "availability_filter"
    label: Literal["입력 가용 조건 충족"] = "입력 가용 조건 충족"
    actual_value: Literal[True] = True


class CategoryFilterEvidence(ContractModel):
    kind: Literal["category_filter"] = "category_filter"
    label: Literal["입력 주종 조건 충족"] = "입력 주종 조건 충족"
    actual_value: Category
    allowed_category_count: int = Field(ge=1, le=32)


class PriceFilterEvidence(ContractModel):
    kind: Literal["price_filter"] = "price_filter"
    label: Literal["입력 가격 조건 충족"] = "입력 가격 조건 충족"
    actual_value: Annotated[int, Field(ge=0, le=2_147_483_647)]
    minimum: Annotated[int, Field(ge=0, le=2_147_483_647)] | None
    maximum: Annotated[int, Field(ge=0, le=2_147_483_647)] | None
    unit: Literal["KRW"] = "KRW"


class AbvFilterEvidence(ContractModel):
    kind: Literal["abv_filter"] = "abv_filter"
    label: Literal["입력 도수 조건 충족"] = "입력 도수 조건 충족"
    actual_value: Abv
    minimum: Abv | None
    maximum: Abv | None
    unit: Literal["vol%"] = "vol%"


FilterEvidence = Annotated[
    AvailabilityEvidence | CategoryFilterEvidence | PriceFilterEvidence | AbvFilterEvidence,
    Field(discriminator="kind"),
]


class ItemExplanation(ContractModel):
    version: Literal["r04-facts-v1"] = "r04-facts-v1"
    basis: Literal["content_similarity", "deterministic_baseline", "no_shared_features"]
    comparison: Annotated[ProfileComparison | ReferenceComparison, Field(discriminator="kind")]
    score_evidence: list[ScoreEvidence] = Field(max_length=3)
    total_positive_contributions: int = Field(ge=0, le=43)
    score_evidence_truncated: bool
    filter_evidence: list[FilterEvidence] = Field(max_length=4)
    fallback_reason: (
        Literal["no_eligible_products", "no_supported_preferences", "no_matching_features"] | None
    )


class ContentItem(ContractModel):
    product_id: ProductId
    score: Score
    reasons: list[str]
    contributions: list[Contribution]
    explanation: ItemExplanation | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


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
