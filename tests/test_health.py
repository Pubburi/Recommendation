from fastapi.testclient import TestClient

from pubburi_recommendation.main import app


def test_service_starts_without_database_or_model() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "pubburi-recommendation"}
