from fastapi.testclient import TestClient

from mock_usaspending.app import app


def test_mock_toptier_agencies():
    with TestClient(app) as client:
        response = client.get("/api/v2/references/toptier_agencies/")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 5
        assert data["results"][0]["abbreviation"] == "DOD"

def test_mock_scenario_error_400():
    with TestClient(app) as client:
        response = client.get("/api/v2/references/toptier_agencies/?scenario=error_400")
        assert response.status_code == 400
        assert response.json()["detail"] == "Mock Validation Error"

def test_mock_scenario_empty():
    with TestClient(app) as client:
        response = client.get("/api/v2/references/toptier_agencies/?scenario=empty")
        assert response.status_code == 200
        assert response.json()["results"] == []
