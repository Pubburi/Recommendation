"""Lossless explicit Backend preference input for the existing B1 request engines."""

from pubburi_recommendation.baseline import Constraints
from pubburi_recommendation.content_contracts import ContentProfile
from pubburi_recommendation.search_phrases import SearchPreferenceSnapshot


def resolve_preferences(preferences: SearchPreferenceSnapshot, constraints: Constraints):
    soft = preferences.softPreferences
    profile = ContentProfile(
        categories=soft.categories or [],
        taste_tags=soft.tasteTags or [],
        aroma_tags=soft.aromaTags or [],
        preferred_abv_percent=None
        if soft.targetAbvPercent is None
        else float(soft.targetAbvPercent),
    )
    # BE GET owns Java canonicalization. The existing B1 profile must preserve
    # every literal atom; never silently normalize/drop an incompatible value.
    if profile.taste_tags != (soft.tasteTags or []) or profile.aroma_tags != (soft.aromaTags or []):
        raise ValueError("preferences_require_lossless_b1_tag_literals")
    hard = preferences.hardConstraints
    values = constraints.model_dump()
    for field, stored in (
        ("min_price_krw", hard.minPriceKrw),
        ("max_price_krw", hard.maxPriceKrw),
        ("min_abv_percent", hard.minAbvPercent),
        ("max_abv_percent", hard.maxAbvPercent),
    ):
        if stored is None:
            continue
        stored = float(stored) if "abv" in field else stored
        current = values[field]
        values[field] = (
            stored
            if current is None
            else max(current, stored)
            if field.startswith("min_")
            else min(current, stored)
        )
    for lower, upper in (
        ("min_price_krw", "max_price_krw"),
        ("min_abv_percent", "max_abv_percent"),
    ):
        if (
            values[lower] is not None
            and values[upper] is not None
            and values[lower] > values[upper]
        ):
            raise ValueError("preferences_and_request_hard_bounds_conflict")
    return profile, Constraints.model_validate(values)
