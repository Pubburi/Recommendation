from fastapi import FastAPI

app = FastAPI(
    title="Pubburi Recommendation",
    description="Service bootstrap. Recommendation algorithms are planned separately.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Report process availability without requiring a database or a model."""
    return {"status": "ok", "service": "pubburi-recommendation"}
