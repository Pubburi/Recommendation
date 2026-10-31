"""In-memory B1 product representation fit; no user learning, persistence or network."""

import hashlib
import json
from typing import Annotated, Literal, Self

import numpy as np
import sklearn
from pydantic import Field, StringConstraints, model_validator
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import MinMaxScaler

from pubburi_recommendation.baseline import (
    Abv,
    CatalogProduct,
    Category,
    Constraints,
    ContractModel,
    ProductId,
    within_range,
)

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


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def product_tokens(product: ContentProduct) -> list[str]:
    # Atomic namespaced tags preserve Korean one-character/multi-word facts. No tokenizer inference.
    return sorted(
        ([f"category:{product.category}"] if product.category is not None else [])
        + [f"taste:{tag}" for tag in product.taste_tags or []]
        + [f"aroma:{tag}" for tag in product.aroma_tags or []]
    )


def profile_tokens(profile: ContentProfile) -> list[str]:
    return sorted(
        [f"category:{category}" for category in profile.categories]
        + [f"taste:{tag}" for tag in profile.taste_tags]
        + [f"aroma:{tag}" for tag in profile.aroma_tags]
    )


def atomic_tokens(tokens: list[str]) -> list[str]:
    return tokens


def validate_catalog(products: list[ContentProduct], *, allow_empty: bool = False) -> None:
    if not isinstance(products, list) or any(not isinstance(p, ContentProduct) for p in products):
        raise ValueError("validated_product_list_required")
    if len(products) > 1000 or (not products and not allow_empty):
        raise ValueError("catalog_requires_1_to_1000_products")
    if len({p.product_id for p in products}) != len(products):
        raise ValueError("catalog_product_ids_must_be_unique")


def eligible(product: ContentProduct, constraints: Constraints) -> bool:
    return (
        product.available
        and product.product_id not in constraints.exclude_product_ids
        and (not constraints.categories or product.category in constraints.categories)
        and within_range(product.price_krw, constraints.min_price_krw, constraints.max_price_krw)
        and within_range(
            product.abv_percent, constraints.min_abv_percent, constraints.max_abv_percent
        )
    )


def filter_reasons(constraints: Constraints) -> list[str]:
    reasons = ["available"]
    if constraints.categories:
        reasons.append("category_match")
    if (constraints.min_price_krw, constraints.max_price_krw) != (None, None):
        reasons.append("price_within_range")
    if (constraints.min_abv_percent, constraints.max_abv_percent) != (None, None):
        reasons.append("abv_within_range")
    return reasons


class FittedContentModel:
    """Fit vocabulary/IDF and observed numeric ranges on the caller's training partition only."""

    @classmethod
    def fit(cls, training: list[ContentProduct]) -> "FittedContentModel":
        validate_catalog(training)
        model = cls()
        training = sorted(training, key=lambda product: product.product_id)
        documents = [product_tokens(product) for product in training]
        model.vectorizer = None
        if any(documents):
            model.vectorizer = TfidfVectorizer(analyzer=atomic_tokens, norm="l2", smooth_idf=True)
            model.vectorizer.fit(documents)
        model.scalers = {}
        numeric_summary = {}
        for attribute in ("abv_percent", "volume_ml"):
            values = [getattr(product, attribute) for product in training]
            observed = [value for value in values if value is not None]
            scaler = None
            if observed:
                scaler = MinMaxScaler(clip=False).fit(np.array(observed).reshape(-1, 1))
                # A constant training attribute supplies no learned distance scale.
                if scaler.data_range_[0] > 0:
                    model.scalers[attribute] = scaler
            numeric_summary[attribute] = {
                "observed_count": len(observed),
                "missing_count": len(values) - len(observed),
                "active": attribute in model.scalers,
                "minimum": None if scaler is None else float(scaler.data_min_[0]),
                "maximum": None if scaler is None else float(scaler.data_max_[0]),
            }
        vocabulary = (
            [] if model.vectorizer is None else model.vectorizer.get_feature_names_out().tolist()
        )
        idf = [] if model.vectorizer is None else model.vectorizer.idf_.tolist()
        training_hash = digest([product.model_dump(mode="json") for product in training])
        model.summary = {
            "algorithm": ALGORITHM,
            "sklearn_version": sklearn.__version__,
            "training_sha256": training_hash,
            "training_products": len(training),
            "training_groups": len({product.sku_group for product in training}),
            "vocabulary_size": len(vocabulary),
            "numeric_fit": numeric_summary,
            "unknown_tags": {
                name: sum(getattr(product, name) is None for product in training)
                for name in ("taste_tags", "aroma_tags")
            },
            "reviewed_empty_tags": {
                name: sum(getattr(product, name) == [] for product in training)
                for name in ("taste_tags", "aroma_tags")
            },
        }
        model.fingerprint = digest({**model.summary, "vocabulary": vocabulary, "idf": idf})
        return model

    def rank(
        self,
        candidates: list[ContentProduct],
        profile: ContentProfile,
        constraints: Constraints | None = None,
        *,
        limit: int = 12,
    ) -> ContentResponse:
        validate_catalog(candidates, allow_empty=True)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit_requires_integer_1_to_100")
        if not isinstance(profile, ContentProfile):
            raise ValueError("validated_profile_required")
        constraints = constraints if constraints is not None else Constraints()
        if not isinstance(constraints, Constraints):
            raise ValueError("validated_constraints_required")
        products = sorted(
            (product for product in candidates if eligible(product, constraints)),
            key=lambda product: product.product_id,
        )
        query = None
        tokens = profile_tokens(profile)
        supported_tokens = 0
        if self.vectorizer is not None:
            supported_tokens = sum(token in self.vectorizer.vocabulary_ for token in tokens)
            transformed = self.vectorizer.transform([tokens])
            if transformed.nnz:
                query = transformed
        requested_numeric = {
            "abv_percent": profile.preferred_abv_percent,
            "volume_ml": profile.preferred_volume_ml,
        }
        active_numeric = {
            name: value
            for name, value in requested_numeric.items()
            if value is not None and name in self.scalers
        }
        component_count = int(query is not None) + len(active_numeric)
        results = []
        vectors = None
        names = []
        if query is not None and products:
            vectors = self.vectorizer.transform([product_tokens(product) for product in products])
            names = self.vectorizer.get_feature_names_out()
        for row, product in enumerate(products):
            contributions = []
            if query is not None:
                overlap = vectors[row].multiply(query).tocoo()
                for column, value in zip(overlap.col, overlap.data, strict=True):
                    if value > 0:
                        contributions.append(
                            Contribution(
                                component="text",
                                feature=str(names[column]),
                                contribution=min(1.0, float(value) / component_count),
                            )
                        )
            for attribute, target in active_numeric.items():
                actual = getattr(product, attribute)
                if actual is None:
                    continue  # Unknown is neither zero nor evidence of numeric similarity.
                positions = self.scalers[attribute].transform([[target], [actual]])[:, 0]
                similarity = max(0.0, 1.0 - abs(float(positions[0] - positions[1])))
                if similarity > 0:
                    contributions.append(
                        Contribution(
                            component=attribute,
                            feature=attribute,
                            contribution=similarity / component_count,
                        )
                    )
            contributions.sort(key=lambda part: (part.component, part.feature))
            score = min(1.0, sum(part.contribution for part in contributions))
            reasons = filter_reasons(constraints)
            reasons.append(
                "deterministic_baseline"
                if not component_count
                else "content_similarity"
                if score > 0
                else "no_shared_features"
            )
            results.append(
                ContentItem(
                    product_id=product.product_id,
                    score=score,
                    reasons=reasons,
                    contributions=contributions,
                )
            )
        results.sort(key=lambda item: (-item.score, item.product_id))
        no_matches = bool(results) and all(item.score == 0 for item in results)
        if no_matches and component_count:
            for item in results:
                item.reasons.append("deterministic_baseline")
        return ContentResponse(
            model_fingerprint=self.fingerprint,
            items=results[:limit],
            eligible_count=len(products),
            supported_profile_tokens=supported_tokens,
            unknown_profile_tokens=len(tokens) - supported_tokens,
            active_numeric_preferences=sorted(active_numeric),
            fallback_reason="no_eligible_products"
            if not products
            else "no_supported_preferences"
            if not component_count
            else "no_matching_features"
            if no_matches
            else None,
        )

    def similar(
        self,
        reference: ContentProduct,
        candidates: list[ContentProduct],
        constraints: Constraints | None = None,
        *,
        limit: int = 12,
    ) -> ContentResponse:
        if not isinstance(reference, ContentProduct):
            raise ValueError("validated_reference_product_required")
        constraints = constraints if constraints is not None else Constraints()
        constraints = Constraints.model_validate(
            {
                **constraints.model_dump(),
                "exclude_product_ids": sorted(
                    set(constraints.exclude_product_ids) | {reference.product_id}
                ),
            }
        )
        return self.rank(
            candidates,
            ContentProfile(
                categories=[] if reference.category is None else [reference.category],
                taste_tags=reference.taste_tags or [],
                aroma_tags=reference.aroma_tags or [],
                preferred_abv_percent=reference.abv_percent,
                preferred_volume_ml=reference.volume_ml,
            ),
            constraints,
            limit=limit,
        )
