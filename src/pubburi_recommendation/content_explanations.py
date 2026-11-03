"""Bounded R04 evidence from actual B1 contributions and request facts; no scorer or fit."""

import math

from pubburi_recommendation.baseline import Constraints, within_range
from pubburi_recommendation.content_contracts import (
    AbvFilterEvidence,
    AbvScoreEvidence,
    AromaScoreEvidence,
    AvailabilityEvidence,
    CategoryFilterEvidence,
    CategoryScoreEvidence,
    ContentProduct,
    ContentProfile,
    ContentResponse,
    ItemExplanation,
    PriceFilterEvidence,
    ProfileComparison,
    TasteScoreEvidence,
    VolumeScoreEvidence,
)

MAX_EXPLANATION_BYTES = 4096
MAX_SCORE_EVIDENCE = 3


def enforce_explanation_bound(explanation: ItemExplanation) -> None:
    if len(explanation.model_dump_json().encode("utf-8")) > MAX_EXPLANATION_BYTES:
        raise ValueError("explanation_exceeds_bound")


def score_evidence(part, product, profile):
    if part.component == "text":
        namespace, separator, value = part.feature.partition(":")
        options = {
            "category": (CategoryScoreEvidence, [product.category], profile.categories),
            "taste": (TasteScoreEvidence, product.taste_tags or [], profile.taste_tags),
            "aroma": (AromaScoreEvidence, product.aroma_tags or [], profile.aroma_tags),
        }
        if not separator or namespace not in options:
            raise ValueError("explanation_evidence_conflicts")
        evidence, actual, requested = options[namespace]
        if value not in actual or value not in requested:
            raise ValueError("explanation_evidence_conflicts")
        return evidence(actual_value=value, target_value=value, contribution=part.contribution)
    if part.feature != part.component:
        raise ValueError("explanation_evidence_conflicts")
    actual, target = (
        getattr(product, part.component),
        getattr(profile, "preferred_" + part.component),
    )
    if actual is None or target is None:
        raise ValueError("explanation_evidence_conflicts")
    evidence = AbvScoreEvidence if part.component == "abv_percent" else VolumeScoreEvidence
    return evidence(actual_value=actual, target_value=target, contribution=part.contribution)


def filter_evidence(product, constraints, reasons):
    expected = {"available"}
    if not product.available or product.product_id in constraints.exclude_product_ids:
        raise ValueError("explanation_evidence_conflicts")
    evidence = [AvailabilityEvidence()]
    if constraints.categories:
        expected.add("category_match")
        if product.category not in constraints.categories:
            raise ValueError("explanation_evidence_conflicts")
        evidence.append(
            CategoryFilterEvidence(
                actual_value=product.category,
                allowed_category_count=len(set(constraints.categories)),
            )
        )
    for attribute, minimum, maximum, cls in (
        ("price_krw", constraints.min_price_krw, constraints.max_price_krw, PriceFilterEvidence),
        (
            "abv_percent",
            constraints.min_abv_percent,
            constraints.max_abv_percent,
            AbvFilterEvidence,
        ),
    ):
        if minimum is None and maximum is None:
            continue
        expected.add("price_within_range" if attribute == "price_krw" else "abv_within_range")
        actual = getattr(product, attribute)
        if actual is None or not within_range(actual, minimum, maximum):
            raise ValueError("explanation_evidence_conflicts")
        evidence.append(cls(actual_value=actual, minimum=minimum, maximum=maximum))
    hard_codes = {"available", "category_match", "price_within_range", "abv_within_range"}
    if set(reasons) & hard_codes != expected:
        raise ValueError("explanation_evidence_conflicts")
    return evidence


def annotate_explanations(
    response: ContentResponse,
    products: list[ContentProduct],
    profile: ContentProfile,
    constraints: Constraints,
) -> None:
    by_id = {product.product_id: product for product in products}
    for item in response.items:
        product = by_id[item.product_id]
        positive = sorted(
            (part for part in item.contributions if part.contribution > 0),
            key=lambda part: (-part.contribution, part.component, part.feature),
        )
        if bool(item.score > 0) != bool(positive) or not math.isclose(
            item.score, sum(part.contribution for part in positive), abs_tol=1e-9
        ):
            raise ValueError("explanation_evidence_conflicts")
        # Validate every used fact, even when only the top three are shown. Do not alter
        # raw atoms (including commas/newlines), infer unknown facts or recompute scores.
        all_evidence = [score_evidence(part, product, profile) for part in positive]
        explanation = ItemExplanation(
            basis="content_similarity"
            if item.score > 0
            else "deterministic_baseline"
            if "deterministic_baseline" in item.reasons
            else "no_shared_features",
            comparison=ProfileComparison(),
            score_evidence=all_evidence[:MAX_SCORE_EVIDENCE],
            total_positive_contributions=len(positive),
            score_evidence_truncated=len(positive) > MAX_SCORE_EVIDENCE,
            filter_evidence=filter_evidence(product, constraints, item.reasons),
            fallback_reason=response.fallback_reason,
        )
        enforce_explanation_bound(explanation)
        item.explanation = explanation
