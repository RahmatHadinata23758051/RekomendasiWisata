import os
import json
import shutil
import pytest
import pandas as pd
from typing import Dict, Any, List

from src.enrichment.review_payload_builder import build_review_payloads
from src.enrichment.review_processor import process_and_select_reviews, normalize_text_for_similarity, compute_content_hash

def test_payload_generation_constraints():
    input_csv = "data/enrichment/pilot/pilot_google_places_input.csv"
    output_dir = "data/enrichment/apify_review_inputs_test"
    
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
        
    try:
        manifest = build_review_payloads(input_csv_path=input_csv, output_dir=output_dir, batch_size=70)
        
        # 1. Total eligible tetap 271
        assert manifest["total_eligible_places"] == 271
        
        # 2. Total batches
        assert manifest["total_batches"] == 4
        assert manifest["total_payloads"] == 12
        
        # Load batches and payloads
        batches = manifest["batches"]
        
        # Track place IDs per mode to check uniqueness
        place_ids_by_mode = {"positive": set(), "negative": set(), "neutral": set()}
        
        for b in batches:
            # 3. Batch size maksimal 70
            assert b["place_count"] <= 70
            
            payload_path = os.path.join(output_dir, b["payload_path"])
            assert os.path.exists(payload_path)
            
            with open(payload_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
                
            # 4. Check sort and parameters for each mode
            mode = b["mode"]
            assert payload["personalData"] is False
            assert payload["language"] == "id"
            assert payload["reviewsOrigin"] == "google"
            
            if mode == "positive":
                assert payload["maxReviews"] == 8
                assert payload["reviewsSort"] == "highestRanking"
            elif mode == "negative":
                assert payload["maxReviews"] == 8
                assert payload["reviewsSort"] == "lowestRanking"
            elif mode == "neutral":
                assert payload["maxReviews"] == 25
                assert payload["reviewsSort"] == "newest"
                
            # Uniqueness per mode
            for pid in payload["placeIds"]:
                assert pid not in place_ids_by_mode[mode]
                place_ids_by_mode[mode].add(pid)
                
        # Each mode should cover exactly 271 places
        for m, pids in place_ids_by_mode.items():
            assert len(pids) == 271
            
    finally:
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)

def test_importer_and_processor():
    test_raw_dir = "data/enrichment/raw_reviews_test"
    test_processed_dir = "data/enrichment/processed_reviews_test"
    test_final_dir = "data/enrichment/final_test"
    test_reports_dir = "reports_test"
    
    for d in [test_raw_dir, test_processed_dir, test_final_dir, test_reports_dir]:
        if os.path.exists(d):
            shutil.rmtree(d)
            
    try:
        # Create directories
        os.makedirs(os.path.join(test_raw_dir, "positive"), exist_ok=True)
        os.makedirs(os.path.join(test_raw_dir, "negative"), exist_ok=True)
        os.makedirs(os.path.join(test_raw_dir, "neutral"), exist_ok=True)
        
        # We will create a few mock raw reviews
        # Place 1: can_59a8f91551ac (google_place_id = ChIJKxA7awAlQS4RNqFGu6sNH_Y)
        # Place 2: can_1fef284e7d10 (google_place_id = ChIJ8eabclElQS4RwcQA9UtEYfM)
        
        raw_pos = [
            {
                "id": "rev1",
                "placeId": "ChIJKxA7awAlQS4RNqFGu6sNH_Y",
                "stars": 5,
                "text": "Pantai indah sekali, airnya sangat jernih.",
                "publishAt": "2026-07-01T12:00:00Z",
                "authorName": "Ahmad"
            },
            {
                "id": "rev2",
                "placeId": "ChIJKxA7awAlQS4RNqFGu6sNH_Y",
                "stars": 4,
                "text": "Bagus sekali untuk rekreasi keluarga.",
                "publishAt": "2026-07-02T12:00:00Z",
                "authorName": "Budi"
            },
            {
                "id": "rev_empty",
                "placeId": "ChIJKxA7awAlQS4RNqFGu6sNH_Y",
                "stars": 5,
                "text": "  ", # Empty text
                "publishAt": "2026-07-03T12:00:00Z",
                "authorName": "Cici"
            }
        ]
        
        raw_neg = [
            {
                "id": "rev3",
                "placeId": "ChIJKxA7awAlQS4RNqFGu6sNH_Y",
                "stars": 1,
                "text": "Sangat kotor dan tidak terawat.",
                "publishAt": "2026-07-04T12:00:00Z",
                "authorName": "Dedi"
            },
            {
                "id": "rev1_dup", # Duplicate ID
                "placeId": "ChIJKxA7awAlQS4RNqFGu6sNH_Y",
                "stars": 1,
                "text": "Sangat kotor dan tidak terawat.",
                "publishAt": "2026-07-04T12:00:00Z",
                "authorName": "Dedi"
            }
        ]
        
        raw_neu = [
            {
                "id": "rev4",
                "placeId": "ChIJKxA7awAlQS4RNqFGu6sNH_Y",
                "stars": 3,
                "text": "Biasa saja, fasilitas minim.",
                "publishAt": "2026-07-05T12:00:00Z",
                "authorName": "Eko"
            }
        ]
        
        # Write positive batch
        with open(os.path.join(test_raw_dir, "positive", "batch_001.json"), "w", encoding="utf-8") as f:
            json.dump(raw_pos, f)
            
        # Write negative batch
        with open(os.path.join(test_raw_dir, "negative", "batch_001.json"), "w", encoding="utf-8") as f:
            json.dump(raw_neg, f)
            
        # Write neutral batch
        with open(os.path.join(test_raw_dir, "neutral", "batch_001.json"), "w", encoding="utf-8") as f:
            json.dump(raw_neu, f)
            
        # Run processing
        process_and_select_reviews(
            raw_dir=test_raw_dir,
            pilot_csv_path="data/enrichment/pilot/pilot_places.csv",
            manifest_path="data/enrichment/apify_review_inputs/review_batch_manifest.json",
            processed_dir=test_processed_dir,
            final_dir=test_final_dir,
            reports_dir=test_reports_dir
        )
        
        # Check reviews_all contains unique clean reviews
        df_all = pd.read_csv(os.path.join(test_processed_dir, "reviews_all.csv"))
        # Expected:
        # rev1 (positive)
        # rev2 (positive)
        # rev_empty (positive but has empty text - wait, empty text goes to empty text csv and all)
        # rev3 (negative)
        # rev4 (neutral)
        # rev1_dup is duplicate
        assert len(df_all) == 5
        
        # Check duplicate file
        df_dup = pd.read_csv(os.path.join(test_processed_dir, "reviews_duplicates.csv"))
        assert len(df_dup) == 1
        assert df_dup.iloc[0]["review_id"] == "rev3"
        
        # Check empty text file
        df_empty = pd.read_csv(os.path.join(test_processed_dir, "reviews_empty_text.csv"))
        assert len(df_empty) == 1
        assert df_empty.iloc[0]["review_id"] == "rev_empty"
        
        # Check final representative selected
        df_final = pd.read_csv(os.path.join(test_final_dir, "reviews.csv"))
        # Empty text (rev_empty) should not be selected!
        assert "rev_empty" not in df_final["review_id"].values
        # rev1 (positive), rev2 (positive), rev3 (negative), rev4 (neutral) should be selected
        assert set(df_final["review_id"].tolist()) == {"rev1", "rev2", "rev1_dup", "rev4"}
        
        # Check that no fake negative reviews are created for places that have none
        # (Place 2 has no reviews, so it shouldn't have any in df_final)
        df_place2 = df_final[df_final["canonical_id"] == "can_1fef284e7d10"]
        assert len(df_place2) == 0
        
    finally:
        for d in [test_raw_dir, test_processed_dir, test_final_dir, test_reports_dir]:
            if os.path.exists(d):
                shutil.rmtree(d)

def test_get_run_value_helper():
    from src.cli import get_run_value
    
    # 1. Pydantic-like object testing
    class MockPydanticRun:
        def __init__(self, run_id, dataset_id):
            self.id = run_id
            self.default_dataset_id = dataset_id
            
    pydantic_run = MockPydanticRun("run_abc", "dataset_xyz")
    assert get_run_value(pydantic_run, "id") == "run_abc"
    assert get_run_value(pydantic_run, "default_dataset_id", "defaultDatasetId") == "dataset_xyz"
    
    # 2. Legacy dictionary testing
    legacy_run = {
        "id": "run_123",
        "defaultDatasetId": "dataset_456"
    }
    assert get_run_value(legacy_run, "id") == "run_123"
    assert get_run_value(legacy_run, "default_dataset_id", "defaultDatasetId") == "dataset_456"
    
    # Test invalid type raising TypeError
    with pytest.raises(TypeError):
        get_run_value(42, "id")

def test_recover_run_logic(monkeypatch):
    # Mock ApifyClient and get_run_value
    mock_run_calls = 0
    mock_actor_calls = 0
    mock_dataset_calls = 0
    
    class MockDataset:
        def list_items(self):
            class MockItems:
                items = [{"id": "rev1", "text": "excellent pantai", "stars": 5}]
            return MockItems()
            
    class MockRun:
        def get(self):
            nonlocal mock_run_calls
            mock_run_calls += 1
            class MockRunObj:
                id = "mock_run_id"
                status = "SUCCEEDED"
                default_dataset_id = "mock_dataset_id"
            return MockRunObj()
            
    class MockActor:
        def call(self, run_input=None):
            nonlocal mock_actor_calls
            mock_actor_calls += 1
            return {"id": "new_run_id", "defaultDatasetId": "new_dataset_id"}
            
    class MockApifyClient:
        def __init__(self, token):
            self.token = token
        def run(self, run_id):
            return MockRun()
        def dataset(self, dataset_id):
            nonlocal mock_dataset_calls
            mock_dataset_calls += 1
            return MockDataset()
        def actor(self, actor_id):
            return MockActor()
            
    # Mock apify_client import
    import sys
    from types import ModuleType
    mock_apify_mod = ModuleType("apify_client")
    mock_apify_mod.ApifyClient = MockApifyClient
    sys.modules["apify_client"] = mock_apify_mod
    
    monkeypatch.setenv("APIFY_TOKEN", "mock_token")
    
    test_manifest_dir = "data/enrichment/apify_review_inputs_test_rec"
    os.makedirs(test_manifest_dir, exist_ok=True)
    
    try:
        manifest_data = {
            "batches": [
                {
                    "batch_id": "batch_test",
                    "mode": "positive",
                    "payload_path": "positive/batch_test.json",
                    "place_count": 1,
                    "canonical_ids": ["can_1"],
                    "google_place_ids": ["g1"],
                    "payload_checksum": "xyz",
                    "status": "pending",
                    "apify_run_id": None,
                    "dataset_id": None
                }
            ]
        }
        
        backup_manifest = "data/enrichment/apify_review_inputs/review_batch_manifest.json.bak"
        actual_manifest = "data/enrichment/apify_review_inputs/review_batch_manifest.json"
        
        if os.path.exists(actual_manifest):
            shutil.copy(actual_manifest, backup_manifest)
            
        os.makedirs(os.path.dirname(actual_manifest), exist_ok=True)
        with open(actual_manifest, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f)
            
        test_raw_path = "data/enrichment/raw_reviews/positive/batch_test.json"
        if os.path.exists(test_raw_path):
            os.remove(test_raw_path)
            
        from src.cli import recover_review_run
        
        # 3. Recovery existing successful run
        recover_review_run(mode="positive", batch="batch_test", run_id="mock_run_id")
        
        assert mock_run_calls == 1
        assert mock_dataset_calls == 1
        # 4. Recovery does not trigger new Actor run
        assert mock_actor_calls == 0
        
        # Check manifest status is now completed
        with open(actual_manifest, "r", encoding="utf-8") as f:
            updated_manifest = json.load(f)
        assert updated_manifest["batches"][0]["status"] == "completed"
        assert updated_manifest["batches"][0]["apify_run_id"] == "mock_run_id"
        assert updated_manifest["batches"][0]["dataset_id"] == "mock_dataset_id"
        
        # 6. Idempotency check: running recovery again should NOT call run or dataset download
        mock_run_calls = 0
        mock_dataset_calls = 0
        recover_review_run(mode="positive", batch="batch_test", run_id="mock_run_id")
        assert mock_run_calls == 0
        assert mock_dataset_calls == 0
        
        # Cleanup test raw file
        if os.path.exists(test_raw_path):
            os.remove(test_raw_path)
            
        # Restore manifest
        if os.path.exists(backup_manifest):
            shutil.move(backup_manifest, actual_manifest)
        else:
            os.remove(actual_manifest)
            
    finally:
        if os.path.exists(test_manifest_dir):
            shutil.rmtree(test_manifest_dir)
