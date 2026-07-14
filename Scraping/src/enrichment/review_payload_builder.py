import os
import json
import hashlib
import logging
from datetime import datetime, timezone
import pandas as pd
from typing import List, Dict, Any

logger = logging.getLogger("scraper.enrichment.payload")

def generate_checksum(data: Dict[str, Any]) -> str:
    # Deterministic JSON dump for checksum calculation
    serialized = json.dumps(data, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

def build_review_payloads(
    input_csv_path: str = "data/enrichment/pilot/pilot_google_places_input.csv",
    output_dir: str = "data/enrichment/apify_review_inputs",
    batch_size: int = 70,
    strategy_version: str = "review_strategy_v2"
) -> Dict[str, Any]:
    # 1. Validate input file
    if not os.path.exists(input_csv_path):
        raise FileNotFoundError(f"Input pilot file not found: {input_csv_path}")
        
    df = pd.read_csv(input_csv_path)
    
    # Assert validation rules
    total_places = len(df)
    assert total_places == 300, f"Expected exactly 300 places, got {total_places}"
    
    eligible_col = df["review_scrape_eligible"].astype(str).str.lower()
    eligible_mask = (eligible_col == "true") | (eligible_col == "1.0")
    
    df_eligible = df[eligible_mask]
    df_ineligible = df[~eligible_mask]
    
    assert len(df_eligible) == 271, f"Expected exactly 271 eligible places, got {len(df_eligible)}"
    assert len(df_ineligible) == 29, f"Expected exactly 29 ineligible places, got {len(df_ineligible)}"
    
    for _, row in df_eligible.iterrows():
        g_id = row["google_place_id"]
        assert pd.notna(g_id) and str(g_id).strip() != "", f"Eligible place {row['canonical_id']} has empty google_place_id"
        
    logger.info("Pilot input validation successful. 271 eligible, 29 ineligible places.")
    
    # 2. Divide eligible place IDs into batches
    df_eligible = df_eligible.sort_values(by="canonical_id").reset_index(drop=True)
    eligible_records = df_eligible.to_dict(orient="records")
    
    batches = []
    for i in range(0, len(eligible_records), batch_size):
        chunk = eligible_records[i : i + batch_size]
        batches.append(chunk)
        
    # Create subdirectories
    os.makedirs(os.path.join(output_dir, "positive"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "negative"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "neutral"), exist_ok=True)
    
    manifest_entries = []
    
    # Load existing manifest for resume capability / preservation
    manifest_path = os.path.join(output_dir, "review_batch_manifest.json")
    existing_map = {}
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
                existing_entries = existing_data.get("batches", [])
                existing_map = {
                    (e["batch_id"], e["mode"]): e
                    for e in existing_entries
                }
        except Exception as e:
            logger.warning(f"Failed to read existing manifest: {e}. Re-creating from scratch.")
            
    # Define strategy configurations
    modes_v1 = {
        "positive": {"maxReviews": 8, "reviewsSort": "highestRanking", "language": "id", "reviewsOrigin": "google", "personalData": False},
        "negative": {"maxReviews": 8, "reviewsSort": "lowestRanking", "language": "id", "reviewsOrigin": "google", "personalData": False},
        "neutral": {"maxReviews": 25, "reviewsSort": "newest", "language": "id", "reviewsOrigin": "google", "personalData": False}
    }
    
    modes_v2 = {
        "positive": {"maxReviews": 6, "reviewsSort": "highestRanking", "language": "id", "reviewsOrigin": "google", "personalData": False},
        "negative": {"maxReviews": 6, "reviewsSort": "lowestRanking", "language": "id", "reviewsOrigin": "google", "personalData": False},
        "neutral": {"maxReviews": 10, "reviewsSort": "newest", "language": "id", "reviewsOrigin": "google", "personalData": False}
    }
    
    for b_idx, batch in enumerate(batches):
        batch_num = b_idx + 1
        batch_id = f"batch_{batch_num:03d}"
        
        batch_place_ids = [str(r["google_place_id"]) for r in batch]
        batch_canonical_ids = [str(r["canonical_id"]) for r in batch]
        
        # Determine strategy version for this batch
        # batch_001 is locked to strategy v1. Other batches use the requested strategy_version.
        if batch_id == "batch_001":
            strat = "review_strategy_v1"
            modes_config = modes_v1
            rep_targets = {"positive": 5, "negative": 5, "neutral": 3}
            raw_limits = {"positive": 8, "negative": 8, "neutral": 25}
        else:
            strat = strategy_version
            if strat == "review_strategy_v2":
                modes_config = modes_v2
                rep_targets = {"positive": 5, "negative": 3, "neutral": 2}
                raw_limits = {"positive": 6, "negative": 6, "neutral": 10}
            else:
                modes_config = modes_v1
                rep_targets = {"positive": 5, "negative": 5, "neutral": 3}
                raw_limits = {"positive": 8, "negative": 8, "neutral": 25}
                
        for mode, config in modes_config.items():
            key = (batch_id, mode)
            
            # If batch is already completed in existing manifest, preserve everything exactly!
            if key in existing_map and existing_map[key].get("status") == "completed":
                entry = existing_map[key].copy()
                # Ensure strategy metadata is populated even for preserved completed ones
                if "strategy_version" not in entry:
                    entry["strategy_version"] = strat
                    entry["representative_target_positive"] = rep_targets["positive"]
                    entry["representative_target_negative"] = rep_targets["negative"]
                    entry["representative_target_neutral"] = rep_targets["neutral"]
                    entry["raw_limit_positive"] = raw_limits["positive"]
                    entry["raw_limit_negative"] = raw_limits["negative"]
                    entry["raw_limit_neutral"] = raw_limits["neutral"]
                manifest_entries.append(entry)
                logger.info(f"Preserved completed batch {batch_id} ({mode}) exactly with strategy info.")
                continue
                
            # Otherwise, build payload
            payload = {
                "placeIds": batch_place_ids,
                **config
            }
            
            payload_filename = f"{batch_id}.json"
            payload_rel_path = f"{mode}/{payload_filename}"
            payload_full_path = os.path.join(output_dir, payload_rel_path)
            
            with open(payload_full_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
                
            checksum = generate_checksum(payload)
            
            entry = {
                "batch_id": batch_id,
                "mode": mode,
                "payload_path": payload_rel_path.replace("\\", "/"),
                "place_count": len(batch),
                "canonical_ids": batch_canonical_ids,
                "google_place_ids": batch_place_ids,
                "payload_checksum": checksum,
                "status": "pending",
                "apify_run_id": None,
                "dataset_id": None,
                "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "strategy_version": strat,
                "representative_target_positive": rep_targets["positive"],
                "representative_target_negative": rep_targets["negative"],
                "representative_target_neutral": rep_targets["neutral"],
                "raw_limit_positive": raw_limits["positive"],
                "raw_limit_negative": raw_limits["negative"],
                "raw_limit_neutral": raw_limits["neutral"]
            }
            
            # Carry over run IDs if they exist but status is not completed (e.g. running/failed)
            if key in existing_map:
                entry["status"] = existing_map[key].get("status") or "pending"
                entry["apify_run_id"] = existing_map[key].get("apify_run_id")
                entry["dataset_id"] = existing_map[key].get("dataset_id")
                
            manifest_entries.append(entry)
            
    manifest = {
        "batch_size": batch_size,
        "total_eligible_places": len(df_eligible),
        "total_batches": len(batches),
        "total_payloads": len(manifest_entries),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "batches": manifest_entries
    }
    
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        
    logger.info(f"Generated/Updated {len(manifest_entries)} payloads across {len(batches)} batches.")
    return manifest
