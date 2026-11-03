"""R06 explicit search intent, without catalog access, inferred thresholds or model fit."""

import math
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BeforeValidator, Field, StringConstraints, field_validator, model_validator

from pubburi_recommendation.baseline import ContractModel, Price

Category = Literal["탁주", "약 · 청주", "과실주", "증류주", "위스키", "양주", "맥주", "사케"]
SearchField = Literal["categories", "tasteTags", "aromaTags", "targetAbvPercent"]
SearchLabel = Literal[
    "전체 상품 보기",
    "지정 조건으로 상품 보기",
    "선택한 취향 조건으로 검색",
    "탁주 조건으로 검색",
    "약 · 청주 조건으로 검색",
    "과실주 조건으로 검색",
    "증류주 조건으로 검색",
    "위스키 조건으로 검색",
    "양주 조건으로 검색",
    "맥주 조건으로 검색",
    "사케 조건으로 검색",
]
FIELD_ORDER = ("categories", "tasteTags", "aromaTags", "targetAbvPercent")
ASCII_JAVA_WHITESPACE = "\t\n\v\f\r\x1c\x1d\x1e\x1f "


def exact_abv(value):
    if type(value) not in (int, float, Decimal) or (
        isinstance(value, float) and not math.isfinite(value)
    ):
        raise ValueError("abv_requires_json_number")
    number = Decimal(str(value))
    if not number.is_finite() or number.as_tuple().exponent < -2:
        raise ValueError("abv_requires_at_most_two_decimal_places")
    # Java BigDecimal's zero has no negative sign; retain the real zero and scale.
    return number.copy_abs() if number.is_zero() else number


SearchAbv = Annotated[
    Decimal,
    BeforeValidator(exact_abv, json_schema_input_type=int | float),
    Field(ge=0, le=100, multiple_of=Decimal("0.01")),
]
QueryAbv = Annotated[str, StringConstraints(pattern=r"^[0-9]{1,3}(\.[0-9]{1,2})?$")]


def java_whitespace(character):
    point = ord(character)
    return (
        character in ASCII_JAVA_WHITESPACE
        or point in (0x1680, 0x2028, 0x2029, 0x205F, 0x3000)
        or 0x2000 <= point <= 0x2006
        or 0x2008 <= point <= 0x200A
    )


def literal_tags(values):
    if values is None:
        return None
    for value in values:
        try:
            length = len(value.encode("utf-16-le")) // 2
        except UnicodeError as error:
            raise ValueError("tags_require_valid_unicode") from error
        if not 1 <= length <= 40 or all(java_whitespace(char) for char in value):
            raise ValueError("tags_require_nonblank_one_to_forty_utf16_units")
        # These are already-normalized BE GET values. Do not approximate Java's full
        # Unicode normalization with Python strip/lower, or alter literal atoms.
        if value.isascii() and value != value.strip(ASCII_JAVA_WHITESPACE).lower():
            raise ValueError("ascii_tags_require_backend_canonical_values")
    if len(values) != len(set(values)):
        raise ValueError("literal_tags_must_be_unique")
    return values


class SearchSoftPreferences(ContractModel):
    categories: list[Category] | None = Field(max_length=8)
    tasteTags: list[str] | None = Field(max_length=20)
    aromaTags: list[str] | None = Field(max_length=20)
    targetAbvPercent: SearchAbv | None

    @field_validator("tasteTags", "aromaTags")
    @classmethod
    def validate_tags(cls, values):
        return literal_tags(values)

    @field_validator("categories")
    @classmethod
    def unique_categories(cls, values):
        if values is not None and len(values) != len(set(values)):
            raise ValueError("categories_must_be_unique")
        return values


class SearchHardConstraints(ContractModel):
    minPriceKrw: Price | None
    maxPriceKrw: Price | None
    minAbvPercent: SearchAbv | None
    maxAbvPercent: SearchAbv | None

    @model_validator(mode="after")
    def ordered_ranges(self) -> Self:
        for lower, upper in (
            (self.minPriceKrw, self.maxPriceKrw),
            (self.minAbvPercent, self.maxAbvPercent),
        ):
            if lower is not None and upper is not None and lower > upper:
                raise ValueError("hard_lower_must_not_exceed_upper")
        return self


class SearchPreferenceSnapshot(ContractModel):
    surveyStatus: Literal["NOT_STARTED", "SKIPPED", "COMPLETED"]
    softPreferences: SearchSoftPreferences
    hardConstraints: SearchHardConstraints

    @model_validator(mode="after")
    def survey_consistency(self) -> Self:
        if self.surveyStatus != "COMPLETED" and any(
            value is not None
            for group in (self.softPreferences, self.hardConstraints)
            for value in group.__dict__.values()
        ):
            raise ValueError("uncompleted_survey_requires_unknown_fields")
        return self


class SearchPhraseRequest(ContractModel):
    preferences: SearchPreferenceSnapshot
    search_opt_in_fields: list[SearchField] = Field(
        default_factory=list, max_length=4, json_schema_extra={"default": []}
    )
    limit: int = Field(default=5, ge=1, le=5)

    @field_validator("search_opt_in_fields")
    @classmethod
    def unique_fields(cls, values):
        if len(values) != len(set(values)):
            raise ValueError("search_opt_in_fields_must_be_unique")
        return values


class SearchConditions(ContractModel):
    type: Category | None = None
    minPriceKrw: Price | None
    maxPriceKrw: Price | None
    minAbvPercent: QueryAbv | None
    maxAbvPercent: QueryAbv | None
    tasteTag: list[str] = Field(default_factory=list, max_length=20)
    aromaTag: list[str] = Field(default_factory=list, max_length=20)


class SearchQueryPair(ContractModel):
    name: Literal[
        "type",
        "minPriceKrw",
        "maxPriceKrw",
        "minAbvPercent",
        "maxAbvPercent",
        "tasteTag",
        "aromaTag",
    ]
    value: str


class SearchPhraseItem(ContractModel):
    template_id: Literal["all_products", "hard_conditions", "selected_preferences"]
    label: SearchLabel
    conditions: SearchConditions
    query_pairs: list[SearchQueryPair] = Field(max_length=45)
    backend_unicode_revalidation_required: bool


class SearchFieldDiagnostic(ContractModel):
    field: SearchField
    code: Literal[
        "soft_not_selected",
        "selected_unknown",
        "selected_empty",
        "backend_unicode_revalidation_required",
    ]


class SearchPhraseResponse(ContractModel):
    algorithm: Literal["r06-explicit-search-phrases-v1"] = "r06-explicit-search-phrases-v1"
    items: list[SearchPhraseItem] = Field(max_length=5)
    candidate_count: int = Field(ge=0, le=8)
    omitted_count: int = Field(ge=0, le=7)
    product_count: None = None
    diagnostics: list[SearchFieldDiagnostic] = Field(max_length=8)
    fallback_reason: (
        Literal[
            "no_explicit_search_conditions",
            "no_search_opt_in",
            "selected_preferences_unknown",
            "selected_preferences_empty",
            "selected_target_outside_hard_bounds",
        ]
        | None
    )


def query_pairs(conditions):
    pairs = []
    for name, value in conditions.model_dump().items():
        if value is None:
            continue
        for atom in value if isinstance(value, list) else [value]:
            pairs.append(SearchQueryPair(name=name, value=str(atom)))
    return pairs


def recommend_search_phrases(request: SearchPhraseRequest) -> SearchPhraseResponse:
    soft, hard = request.preferences.softPreferences, request.preferences.hardConstraints
    selected = set(request.search_opt_in_fields)
    diagnostics = []
    missing, empty = False, False
    for field in FIELD_ORDER:
        value = getattr(soft, field)
        code = None
        if field not in selected and value is not None:
            code = "soft_not_selected"
        elif field in selected and value is None:
            code, missing = "selected_unknown", True
        elif field in selected and value == []:
            code, empty = "selected_empty", True
        if code is not None:
            diagnostics.append(SearchFieldDiagnostic(field=field, code=code))

    def response(items, fallback, count=None):
        count = len(items) if count is None else count
        return SearchPhraseResponse(
            items=items[: request.limit],
            candidate_count=count,
            omitted_count=max(0, count - request.limit),
            diagnostics=diagnostics,
            fallback_reason=fallback,
        )

    if missing or empty:
        return response(
            [], "selected_preferences_unknown" if missing else "selected_preferences_empty"
        )
    values = hard.model_dump()
    for field in ("minAbvPercent", "maxAbvPercent"):
        if values[field] is not None:
            values[field] = format(values[field], "f")
    if "targetAbvPercent" in selected:
        target = soft.targetAbvPercent
        if (hard.minAbvPercent is not None and target < hard.minAbvPercent) or (
            hard.maxAbvPercent is not None and target > hard.maxAbvPercent
        ):
            return response([], "selected_target_outside_hard_bounds")
        values["minAbvPercent"] = values["maxAbvPercent"] = format(target, "f")
    unicode_revalidation = False
    for source, parameter in (("tasteTags", "tasteTag"), ("aromaTags", "aromaTag")):
        if source in selected:
            values[parameter] = sorted(
                getattr(soft, source), key=lambda atom: atom.encode("utf-16-be")
            )
            if any(not atom.isascii() for atom in values[parameter]):
                unicode_revalidation = True
                diagnostics.append(
                    SearchFieldDiagnostic(
                        field=source, code="backend_unicode_revalidation_required"
                    )
                )
    categories = sorted(soft.categories) if "categories" in selected else [None]
    has_hard = any(value is not None for value in hard.__dict__.values())
    template = (
        "selected_preferences" if selected else "hard_conditions" if has_hard else "all_products"
    )
    items = []
    for category in categories:
        conditions = SearchConditions(type=category, **values)
        label = (
            f"{category} 조건으로 검색"
            if category
            else (
                "선택한 취향 조건으로 검색"
                if selected
                else "지정 조건으로 상품 보기"
                if has_hard
                else "전체 상품 보기"
            )
        )
        items.append(
            SearchPhraseItem(
                template_id=template,
                label=label,
                conditions=conditions,
                query_pairs=query_pairs(conditions),
                backend_unicode_revalidation_required=unicode_revalidation,
            )
        )
    fallback = (
        None
        if selected
        else "no_search_opt_in"
        if has_hard or any(value is not None for value in soft.__dict__.values())
        else "no_explicit_search_conditions"
    )
    return response(items, fallback)
