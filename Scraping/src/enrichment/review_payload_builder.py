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
    batch_size: int = 70
) -> Dict[str, Any]:
    # 1. Validate input file
    if not os.path.exists(input_csv_path):
        raise FileNotFoundError(f"Input pilot file not found: {input_csv_path}")
        
    df = pd.read_csv(input_csv_path)
    
    # Assert validation rules
    total_places = len(df)
    assert total_places == 300, f"Expected exactly 300 places, got {total_places}"
    
    # In pandas, empty string or NaN is null
    # But wait, review_scrape_eligible is a string 'true'/'false' or boolean
    eligible_col = df["review_scrape_eligible"].astype(str).str.lower()
    eligible_mask = (eligible_col == "true") | (eligible_col == "1.0")
    
    df_eligible = df[eligible_mask]
    df_ineligible = df[~eligible_mask]
    
    assert len(df_eligible) == 271, f"Expected exactly 271 eligible places, got {len(df_eligible)}"
    assert len(df_ineligible) == 29, f"Expected exactly 29 ineligible places, got {len(df_ineligible)}"
    
    # Ensure google_place_id is not empty for eligible places
    for _, row in df_eligible.iterrows():
        g_id = row["google_place_id"]
        assert pd.notna(g_id) and str(g_id).strip() != "", f"Eligible place {row['canonical_id']} has empty google_place_id"
        
    logger.info("Pilot input validation successful. 271 eligible, 29 ineligible places.")
    
    # 2. Divide eligible place IDs into batches
    # Sort by canonical_id to ensure determinism
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
    
    # 3. Generate payloads
    modes = {
        "positive": {
            "maxReviews": 8,
            "reviewsSort": "highestRanking",
            "language": "id",
            "reviewsOrigin": "google",
            "personalData": False
        },
        "negative": {
            "maxReviews": 8,
            "reviewsSort": "lowestRanking",
            "language": "id",
            "reviewsOrigin": "google",
            "personalData": False
        },
        "neutral": {
            "maxReviews": 25,
            "reviewsSort": "newest",
            "language": "id",
            "reviewsOrigin": "google",
            "personalData": False
        }
    }
    
    for b_idx, batch in enumerate(batches):
        batch_num = b_idx + 1
        batch_id = f"batch_{batch_num:03d}"
        
        batch_place_ids = [str(r["google_place_id"]) for r in batch]
        batch_canonical_ids = [str(r["canonical_id"]) for r in batch]
        
        for mode, config in modes.items():
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
            
            manifest_entries.append({
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
                "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            })
            
    # Write manifest.json
    manifest_path = os.path.join(output_dir, "review_batch_manifest.json")
    # If manifest already exists, preserve status and runs (resume capability)
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
                existing_entries = existing_data.get("batches", [])
                # Map by (batch_id, mode) -> (status, apify_run_id, dataset_id)
                existing_map = {
                    (e["batch_id"], e["mode"]): (e.get("status"), e.get("apify_run_id"), e.get("dataset_id"))
                    for e in existing_entries
                }
                
                for entry in manifest_entries:
                    key = (entry["batch_id"], entry["mode"])
                    if key in existing_map:
                        status, run_id, dataset_id = existing_map[key]
                        entry["status"] = status or "pending"
                        entry["apify_run_id"] = run_id
                        entry["dataset_id"] = dataset_id
        except Exception as e:
            logger.warning(f"Failed to read existing manifest: {e}. Re-creating from scratch.")
            
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
        
    logger.info(f"Generated {len(manifest_entries)} payloads across {len(batches)} batches.")
    return manifest
