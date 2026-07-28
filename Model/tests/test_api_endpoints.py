import pytest
from fastapi.testclient import TestClient
from Model.api.app import app

client = TestClient(app)

def test_health_check_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["total_attractions_loaded"] == 3130
    assert data["model_version"] == "v1.0"

def test_recommendations_endpoint():
    payload = {
        "category": "beach",
        "city_or_regency": "Kabupaten Pesawaran",
        "facilities": ["has_parking", "has_toilet", "has_food"],
        "latitude": -5.50,
        "longitude": 105.20,
        "top_k": 5
    }
    response = client.post("/api/v1/recommendations", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["total_returned"] <= 5
    assert data["execution_latency_ms"] < 200.0  # SLA < 200ms

    recs = data["recommendations"]
    assert len(recs) > 0
    first_item = recs[0]
    assert "canonical_id" in first_item
    assert "reason_codes" in first_item
    assert "score_breakdown" in first_item
    assert first_item["rank"] == 1

def test_sentiment_analyze_endpoint():
    payload = {
        "text": "Pantai Mutun sangat indah, bersih, dan memuaskan!"
    }
    response = client.post("/api/v1/sentiment/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["sentiment_label"] in ["positive", "neutral", "negative"]
    assert "sentiment_score" in data
