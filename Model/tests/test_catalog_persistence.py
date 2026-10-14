"""Comprehensive tests for durable, restart-safe crowdsourced catalog persistence."""

import json
import pytest
from fastapi.testclient import TestClient

from Model.api.catalog_store import CatalogStore
from Model.api.app import app, _submission_to_feature_row
import Model.api.app as app_module
from Model.recommender.algorithms import RecommenderAlgorithms
import pandas as pd


SAMPLE_SUBMISSION = {
    "canonical_id": "dest-crowd-durable-001",
    "name": "Pantai Indah Way Haru",
    "primary_category": "beach",
    "category_tags": ["pantai", "alam"],
    "city_or_regency": "Kabupaten Pesisir Barat",
    "address": "Pesisir Barat, Lampung",
    "district": "Bengkunat",
    "village": "Way Haru",
    "latitude": -5.6123,
    "longitude": 104.3412,
    "description": "Pantai asri tersembunyi dengan pasir putih dan deburan ombak Samudra Hindia.",
    "facilities": ["has_parking", "has_toilet", "has_camping"],
    "opening_hours": None,
    "price_min_idr": 15000.0,
    "price_max_idr": 25000.0,
    "price_status": "paid",
    "operational_status": "open",
    "review_count": 12,
    "review_rating_mean": 4.8,
}


def test_catalog_store_atomic_write_and_restart(tmp_path):
    store_file = tmp_path / "test_approved_catalog.json"
    store1 = CatalogStore(str(store_file))

    # Empty initially
    assert store1.list_records() == []

    # First insertion succeeds
    created = store1.add_if_absent(SAMPLE_SUBMISSION)
    assert created is True

    # Duplicate insertion returns False (idempotent)
    created_again = store1.add_if_absent(SAMPLE_SUBMISSION)
    assert created_again is False

    # Simulate restart with a new store instance pointing to same file
    store2 = CatalogStore(str(store_file))
    reloaded = store2.list_records()
    assert len(reloaded) == 1
    assert reloaded[0]["canonical_id"] == "dest-crowd-durable-001"
    assert reloaded[0]["name"] == "Pantai Indah Way Haru"

    # Verify atomic format and envelope
    raw = json.loads(store_file.read_text(encoding="utf-8"))
    assert raw["format_version"] == 1
    assert isinstance(raw["records"], list)
    assert len(raw["records"]) == 1


def test_catalog_store_invalid_format_detection(tmp_path):
    store_file = tmp_path / "corrupt_catalog.json"
    store_file.write_text('{"format_version": 999, "records": []}', encoding="utf-8")
    store = CatalogStore(str(store_file))
    with pytest.raises(RuntimeError, match="Unsupported catalog store format"):
        store.list_records()

    store_file.write_text('not-valid-json', encoding="utf-8")
    store_corrupt = CatalogStore(str(store_file))
    with pytest.raises(RuntimeError, match="Unable to read catalog store"):
        store_corrupt.list_records()


def test_api_catalog_sync_and_restart_simulation(tmp_path, monkeypatch):
    monkeypatch.delenv("ML_SYNC_HMAC_SECRET", raising=False)
    store_file = tmp_path / "app_catalog_submissions.json"
    monkeypatch.setenv("CATALOG_SUBMISSIONS_PATH", str(store_file))

    # Isolate app state for this test
    app_module.catalog_store = CatalogStore(str(store_file))
    app_module.df_features = app_module.df_features.iloc[:3130].copy()
    app_module.recommender_engine = RecommenderAlgorithms(app_module.df_features)

    client = TestClient(app)

    # 1. Base dataset verification
    health_resp = client.get("/api/v1/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["total_attractions_loaded"] == 3130

    # 2. Publish crowdsourced destination
    post_resp = client.post("/api/v1/catalog/submissions", json=SAMPLE_SUBMISSION)
    assert post_resp.status_code == 200
    post_data = post_resp.json()
    assert post_data["status"] == "success"
    assert post_data["canonical_id"] == "dest-crowd-durable-001"
    assert post_data["total_attractions_loaded"] == 3131
    assert post_data["created"] is True
    assert post_data["persisted"] is True

    # 3. Verify destination is retrievable via GET /api/v1/destinations
    dest_resp = client.get("/api/v1/destinations", params={"search": "Way Haru"})
    assert dest_resp.status_code == 200
    dest_data = dest_resp.json()
    assert dest_data["total_items"] >= 1
    found = [d for d in dest_data["destinations"] if d["canonical_id"] == "dest-crowd-durable-001"]
    assert len(found) == 1
    assert found[0]["name"] == "Pantai Indah Way Haru"
    assert found[0]["city_or_regency"] == "Kabupaten Pesisir Barat"

    # 4. Verify destination participates in recommendations
    rec_resp = client.post("/api/v1/recommendations", json={
        "category": "beach",
        "city_or_regency": "Kabupaten Pesisir Barat",
        "facilities": ["has_camping", "has_parking"],
        "top_k": 10
    })
    assert rec_resp.status_code == 200
    rec_data = rec_resp.json()
    assert rec_data["status"] == "success"
    assert any(item["canonical_id"] == "dest-crowd-durable-001" for item in rec_data["recommendations"])

    # 5. Idempotent re-submission (same ID)
    dup_resp = client.post("/api/v1/catalog/submissions", json=SAMPLE_SUBMISSION)
    assert dup_resp.status_code == 200
    dup_data = dup_resp.json()
    assert dup_data["canonical_id"] == "dest-crowd-durable-001"
    assert dup_data["total_attractions_loaded"] == 3131
    assert dup_data["created"] is False
    assert dup_data["persisted"] is True

    # 6. Simulate service restart
    # New store instance reads from disk and replays rows into fresh df_features
    restarted_store = CatalogStore(str(store_file))
    persisted_rows = restarted_store.list_records()
    assert len(persisted_rows) == 1

    # Reload simulated dataset
    simulated_df = app_module.df_features.iloc[:3130].copy()
    assert len(simulated_df) == 3130
    for record in persisted_rows:
        if str(record.get("canonical_id")) not in set(simulated_df["canonical_id"].astype(str)):
            simulated_df = pd.concat([simulated_df, pd.DataFrame([_submission_to_feature_row(record)], columns=simulated_df.columns)], ignore_index=True)
    assert len(simulated_df) == 3131
    assert "dest-crowd-durable-001" in set(simulated_df["canonical_id"].astype(str))
