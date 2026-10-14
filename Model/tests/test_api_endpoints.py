import pytest
import json
from fastapi.testclient import TestClient
from Model.api.app import app
from Model.api.catalog_store import CatalogStore

client = TestClient(app)


@pytest.fixture(autouse=True)
def _isolate_catalog(monkeypatch, tmp_path):
    """Redirect catalog state and isolate local HMAC configuration for tests."""
    monkeypatch.delenv("ML_SYNC_HMAC_SECRET", raising=False)
    test_file = tmp_path / "approved_catalog.json"
    monkeypatch.setenv("CATALOG_SUBMISSIONS_PATH", str(test_file))
    # The module-level `catalog_store` is constructed at import time. Re-assign it.
    import Model.api.app as app_module
    app_module.catalog_store = CatalogStore(str(test_file))
    # Also ensure the in-memory dataframe is pristine by dropping any rows added by
    # previous tests. The frozen parquet has exactly 3130 rows.
    from Model.api import app as app_state
    app_state.df_features = app_state.df_features.iloc[:3130].copy()
    app_state.recommender_engine = app_state.RecommenderAlgorithms(app_state.df_features)
    yield


def test_health_check_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["total_attractions_loaded"] == 3130
    assert data["model_version"] == "v1.0"


def test_catalog_submission_endpoint():
    payload = {
        "canonical_id": "dest-sub-test-001",
        "name": "Test Pantai Baru",
        "primary_category": "beach",
        "category_tags": [],
        "city_or_regency": "Kabupaten Pesawaran",
        "address": "Jl. Pantai Baru No. 1",
        "latitude": -5.5123,
        "longitude": 105.2512,
        "description": "A test beach for catalog sync",
        "facilities": ["has_parking", "has_toilet"],
        "opening_hours": None,
        "price_min_idr": 10000,
        "price_max_idr": 50000,
        "price_status": "paid",
        "operational_status": "open",
        "review_count": 0,
        "review_rating_mean": None,
    }
    response = client.post("/api/v1/catalog/submissions", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["canonical_id"] == "dest-sub-test-001"
    assert data["total_attractions_loaded"] == 3131
    assert data["created"] is True
    assert data["persisted"] is True

    # Second call with same ID should return existing count (idempotent)
    response2 = client.post("/api/v1/catalog/submissions", json=payload)
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["total_attractions_loaded"] == 3131
    assert data2["created"] is False
    assert data2["persisted"] is True


def test_catalog_submission_hmac_verification(monkeypatch):
    import hmac
    import hashlib
    import time
    secret = "test-secret-key-12345678901234567890"
    monkeypatch.setenv("ML_SYNC_HMAC_SECRET", secret)

    payload = {
        "canonical_id": "dest-sub-hmac-001",
        "name": "Pantai HMAC Test",
        "primary_category": "beach",
        "category_tags": [],
        "city_or_regency": "Kabupaten Pesawaran",
        "address": "Lampung",
        "latitude": -5.5,
        "longitude": 105.2,
        "description": "Test destination",
        "facilities": [],
        "opening_hours": None,
        "price_min_idr": 10000,
        "price_max_idr": 20000,
        "price_status": "paid",
        "operational_status": "open",
        "review_count": 0,
        "review_rating_mean": None,
    }
    raw_body = json.dumps(payload).encode("utf-8")

    # 1. Missing signature header -> 401
    resp_no_sig = client.post("/api/v1/catalog/submissions", content=raw_body, headers={"Content-Type": "application/json"})
    assert resp_no_sig.status_code == 401

    # 2. Invalid signature -> 401
    resp_bad_sig = client.post(
        "/api/v1/catalog/submissions",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "x-ml-timestamp": str(int(time.time())),
            "x-ml-signature": "sha256=" + "0" * 64,
        },
    )
    assert resp_bad_sig.status_code == 401

    # 3. Valid signature -> 200
    ts = str(int(time.time()))
    sig = "sha256=" + hmac.new(secret.encode("utf-8"), ts.encode("ascii") + b"." + raw_body, hashlib.sha256).hexdigest()
    resp_valid = client.post(
        "/api/v1/catalog/submissions",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "x-ml-timestamp": ts,
            "x-ml-signature": sig,
        },
    )
    assert resp_valid.status_code == 200
    assert resp_valid.json()["canonical_id"] == "dest-sub-hmac-001"


def test_catalog_submission_restart_survival(tmp_path):
    # Use the real catalog store mechanism by monkeypatching the path.
    store = CatalogStore(str(tmp_path / "approved_catalog.json"))
    record = {
        "canonical_id": "crowd-restart-001",
        "name": "Pantai Restart",
        "primary_category": "beach",
        "city_or_regency": "Kabupaten Pesawaran",
        "latitude": -5.5,
        "longitude": 105.2,
    }
    assert store.add_if_absent(record) is True
    assert store.add_if_absent(record) is False

    # Simulate a fresh process: new store instance must replay the durable row.
    reloaded = CatalogStore(str(tmp_path / "approved_catalog.json"))
    replayed = reloaded.list_records()
    assert len(replayed) == 1
    assert replayed[0]["canonical_id"] == "crowd-restart-001"


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
