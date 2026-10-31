"""A deterministic, untrained baseline that never relaxes explicit constraints."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

ProductId = Annotated[int, Field(ge=1, le=2_147_483_647)]
Price = Annotated[int, Field(ge=0, le=2_147_483_647)]
Abv = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
Category = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
Reason = Literal[
    "available",
    "category_match",
    "price_within_range",
    "abv_within_range",
    "deterministic_baseline",
]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CatalogProduct(ContractModel):
    product_id: ProductId
    available: bool
    category: Category | None = None
    price_krw: Price | None = None
    abv_percent: Abv | None = None


class Constraints(ContractModel):
    categories: list[Category] = Field(default_factory=list, max_length=32)
    exclude_product_ids: list[ProductId] = Field(default_factory=list, max_length=1000)
    min_price_krw: Price | None = None
    max_price_krw: Price | None = None
    min_abv_percent: Abv | None = None
    max_abv_percent: Abv | None = None

    @model_validator(mode="after")
    def validate_ranges(self) -> Self:
        for lower, upper in (
            (self.min_price_krw, self.max_price_krw),
            (self.min_abv_percent, self.max_abv_percent),
        ):
            if lower is not None and upper is not None and lower > upper:
                raise ValueError("The lower constraint must not exceed the upper constraint")
        return self


class RecommendationRequest(ContractModel):
    catalog: list[CatalogProduct] = Field(max_length=1000)
    constraints: Constraints = Field(default_factory=Constraints)
    limit: Annotated[int, Field(ge=1, le=100)] = 12

    @model_validator(mode="after")
    def validate_product_ids(self) -> Self:
        ids = [product.product_id for product in self.catalog]
        if len(ids) != len(set(ids)):
            raise ValueError("Catalog product_id values must be unique")
        return self


class RecommendationItem(ContractModel):
    product_id: ProductId
    reasons: list[Reason]


class RecommendationResponse(ContractModel):
    algorithm: Literal["b0-id-ascending-v1"] = "b0-id-ascending-v1"
    items: list[RecommendationItem]
    eligible_count: int
    fallback_reason: Literal["no_eligible_products"] | None = None


def within_range(
    value: float | int | None, lower: float | int | None, upper: float | int | None
) -> bool:
    if lower is None and upper is None:
        return True
    if value is None:
        return False
    return (lower is None or value >= lower) and (upper is None or value <= upper)


def recommend_baseline(request: RecommendationRequest) -> RecommendationResponse:
    constraints = request.constraints
    categories = set(constraints.categories)
    excluded = set(constraints.exclude_product_ids)
    eligible = [
        product
        for product in request.catalog
        if product.available
        and product.product_id not in excluded
        and (not categories or product.category in categories)
        and within_range(product.price_krw, constraints.min_price_krw, constraints.max_price_krw)
        and within_range(
            product.abv_percent, constraints.min_abv_percent, constraints.max_abv_percent
        )
    ]
    # Eligibility precedes limit/order, so scarce candidates never relax constraints.
    eligible.sort(key=lambda product: product.product_id)
    reasons: list[Reason] = ["available"]
    if categories:
        reasons.append("category_match")
    if constraints.min_price_krw is not None or constraints.max_price_krw is not None:
        reasons.append("price_within_range")
    if constraints.min_abv_percent is not None or constraints.max_abv_percent is not None:
        reasons.append("abv_within_range")
    reasons.append("deterministic_baseline")
    return RecommendationResponse(
        items=[
            RecommendationItem(product_id=product.product_id, reasons=reasons.copy())
            for product in eligible[: request.limit]
        ],
        eligible_count=len(eligible),
        fallback_reason=None if eligible else "no_eligible_products",
    )
