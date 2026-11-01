from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

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
from pubburi_recommendation.exploration import (
    ExplorationRequest,
    ExplorationResponse,
    recommend_exploration,
)
from pubburi_recommendation.request_limits import CatalogRequestLimit

app = FastAPI(
    title="Pubburi Recommendation",
    description=(
        "Stateless constrained B0 and request-local B1 known-catalog representations. "
        "No model persistence or user preference learning."
    ),
    version="0.1.0",
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
def content(request: ContentRecommendationRequest) -> ContentRecommendationResponse:
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
def exploration(request: ExplorationRequest) -> ExplorationResponse:
    """Select a bounded diverse pool without relaxing B1 relevance or hard constraints."""
    return recommend_exploration(request)
