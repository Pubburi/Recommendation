from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from pubburi_recommendation.baseline import (
    RecommendationRequest,
    RecommendationResponse,
    recommend_baseline,
)
from pubburi_recommendation.request_limits import CatalogRequestLimit

app = FastAPI(
    title="Pubburi Recommendation",
    description="Stateless constrained B0 baseline. No trained model or user preference learning.",
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
    responses={413: {"description": "Catalog request exceeds 524288 bytes"}},
)
def baseline(request: RecommendationRequest) -> RecommendationResponse:
    """Filter an explicit catalog, then return an untrained product-ID baseline."""
    return recommend_baseline(request)
