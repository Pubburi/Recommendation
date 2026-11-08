import json
import logging
from contextlib import asynccontextmanager
from decimal import Decimal, DecimalException
from importlib import import_module
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from pubburi_recommendation.baseline import (
    RecommendationRequest,
    RecommendationResponse,
    recommend_baseline,
)
from pubburi_recommendation.content_api import (
    ContentRecommendationRequest,
    ContentRecommendationResponse,
    recommend_content,
)
from pubburi_recommendation.context_api import (
    ContextRecommendationRequest,
    ContextRecommendationResponse,
    recommend_context,
)
from pubburi_recommendation.exploration import (
    ExplorationRequest,
    ExplorationResponse,
    recommend_exploration,
)
from pubburi_recommendation.feedback_api import (
    FeedbackRecommendationRequest,
    FeedbackRecommendationResponse,
    recommend_feedback,
)
from pubburi_recommendation.request_limits import CatalogRequestLimit
from pubburi_recommendation.search_phrases import (
    SearchPhraseRequest,
    SearchPhraseResponse,
    recommend_search_phrases,
)
from pubburi_recommendation.similar_api import (
    SimilarRecommendationRequest,
    SimilarRecommendationResponse,
    recommend_similar,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Pay dependency initialization before accepting B1 traffic; never fit sample/user data.
    # Numerical dependency failures must leave the independent health/B0 paths available.
    try:
        import_module("pubburi_recommendation.content_model")
    except Exception as error:
        logging.getLogger(__name__).warning(
            "B1 dependency preparation failed (%s); health/B0 remain available",
            type(error).__name__,
        )
    yield


app = FastAPI(
    title="Pubburi Recommendation",
    description=(
        "Stateless constrained B0 and request-local B1 known-catalog representations. "
        "No model persistence or user preference learning."
    ),
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(CatalogRequestLimit)


@app.exception_handler(RequestValidationError)
async def validation_error(_request, error: RequestValidationError) -> JSONResponse:
    # Do not echo catalog contents or non-JSON numeric values in validation errors.
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {key: item[key] for key in ("type", "loc", "msg")} for item in error.errors()
            ]
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Report process availability without requiring a database or a model."""
    return {"status": "ok", "service": "pubburi-recommendation"}


async def precise_body(model, raw_request: Request):
    # Revalidate only explicit BE-shaped inputs after the original body/schema path.
    # The bounded cached body retains BigDecimal scale lost by binary JSON floats.
    try:
        exact_body = json.loads(await raw_request.body(), parse_float=Decimal)
    except DecimalException as error:
        raise RequestValidationError(
            [
                {
                    "type": "decimal_parsing",
                    "loc": ("body",),
                    "msg": "JSON decimal exponent exceeds the supported range",
                }
            ]
        ) from error
    try:
        precise = model.model_validate(exact_body)
    except ValidationError as error:
        raise RequestValidationError(
            [dict(item, loc=("body", *item["loc"])) for item in error.errors()]
        ) from error
    return precise


async def content_input(request: ContentRecommendationRequest, raw_request: Request):
    return (
        await precise_body(type(request), raw_request)
        if request.preferences is not None
        else request
    )


async def exploration_input(request: ExplorationRequest, raw_request: Request):
    return (
        await precise_body(type(request), raw_request)
        if request.preferences is not None
        else request
    )


async def feedback_input(request: FeedbackRecommendationRequest, raw_request: Request):
    return (
        await precise_body(type(request), raw_request)
        if request.preferences is not None
        else request
    )


@app.post(
    "/v1/recommendations/search-phrases",
    response_model=SearchPhraseResponse,
    responses={
        413: {"description": "Request exceeds 524288 bytes"},
        408: {"description": "Request body timed out"},
    },
)
async def search_phrases(
    request: SearchPhraseRequest, raw_request: Request
) -> SearchPhraseResponse:
    return recommend_search_phrases(await precise_body(SearchPhraseRequest, raw_request))


@app.post(
    "/v1/recommendations/baseline",
    response_model=RecommendationResponse,
    responses={
        413: {"description": "Catalog request exceeds 524288 bytes"},
        408: {"description": "Catalog request body timed out"},
    },
)
def baseline(request: RecommendationRequest) -> RecommendationResponse:
    """Filter an explicit catalog, then return an untrained product-ID baseline."""
    return recommend_baseline(request)


@app.post(
    "/v1/recommendations/content",
    response_model=ContentRecommendationResponse,
    responses={
        413: {"description": "Catalog request exceeds 524288 bytes"},
        408: {"description": "Catalog request body timed out"},
    },
)
def content(
    request: Annotated[ContentRecommendationRequest, Depends(content_input)],
) -> ContentRecommendationResponse:
    """Fit this request's explicit catalog and rank it without retaining model/user state."""
    return recommend_content(request)


@app.post(
    "/v1/recommendations/exploration",
    response_model=ExplorationResponse,
    responses={
        413: {"description": "Catalog request exceeds 524288 bytes"},
        408: {"description": "Catalog request body timed out"},
    },
)
def exploration(
    request: Annotated[ExplorationRequest, Depends(exploration_input)],
) -> ExplorationResponse:
    """Select a bounded diverse pool without relaxing B1 relevance or hard constraints."""
    return recommend_exploration(request)


@app.post(
    "/v1/recommendations/similar",
    response_model=SimilarRecommendationResponse,
    responses={
        413: {"description": "Catalog request exceeds 524288 bytes"},
        408: {"description": "Catalog request body timed out"},
    },
)
def similar(request: SimilarRecommendationRequest) -> SimilarRecommendationResponse:
    """Rank against known reference facts without returning that reference or its variants."""
    return recommend_similar(request)


@app.post(
    "/v1/recommendations/context",
    response_model=ContextRecommendationResponse,
    responses={
        413: {"description": "Catalog request exceeds 524288 bytes"},
        408: {"description": "Catalog request body timed out"},
    },
)
def context(request: ContextRecommendationRequest) -> ContextRecommendationResponse:
    """Match explicit cart/demo-order facts without claiming co-purchase or whole-cart fit."""
    return recommend_context(request)


@app.post(
    "/v1/recommendations/feedback",
    response_model=FeedbackRecommendationResponse,
    responses={
        413: {"description": "Catalog request exceeds 524288 bytes"},
        408: {"description": "Catalog request body timed out"},
    },
)
def feedback(
    request: Annotated[FeedbackRecommendationRequest, Depends(feedback_input)],
) -> FeedbackRecommendationResponse:
    """Apply explicit feedback facts and exclusions without learning or storing user state."""
    return recommend_feedback(request)
