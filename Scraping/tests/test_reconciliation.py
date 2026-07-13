import os
import json
import pytest
from src.models.schemas import RawAttractionRecord
from src.pipeline.deduplicate import deduplicate_records

def test_legacy_staging_not_included_in_manifest():
    manifest_path = "data/raw_records/apify_google_maps/manifest.json"
    assert os.path.exists(manifest_path), "manifest.json must exist"
    
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    for entry in manifest:
        assert entry["region"] != "unknown_region", "unknown_region must not be in active manifest"
        assert "unknown_region" not in entry["filepath"], "stale filepath must not be in active manifest"

def test_pesisir_barat_raw_count():
    # Verify pesisir_barat raw records count is exactly 177
    pesisir_path = "data/raw_records/apify_google_maps/pesisir_barat/2026-07-13/places.jsonl"
    assert os.path.exists(pesisir_path), "Pesisir Barat staging places.jsonl must exist"
    
    count = 0
    with open(pesisir_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1
    assert count == 177, f"Pesisir Barat raw records count should be 177, got {count}"

def test_reconciliation_total_raw():
    import glob
    import hashlib
    import re
    import pandas as pd
    from datetime import datetime, timezone
    
    manifest_path = "data/raw_records/apify_google_maps/manifest.json"
    assert os.path.exists(manifest_path), "manifest.json must exist"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    # Check that there are at least 15 active regions (or exactly 15 active manifest entries)
    assert len(manifest) >= 15, f"Expected at least 15 active manifest entries, got {len(manifest)}"
    
    # Check that entries are unique based on filepath and checksum
    filepaths = [entry["filepath"] for entry in manifest]
    checksums = [entry["checksum"] for entry in manifest]
    assert len(filepaths) == len(set(filepaths)), "Duplicate filepaths found in manifest"
    assert len(checksums) == len(set(checksums)), "Duplicate checksums found in manifest"
    
    expected_apify_raw = 0
    for entry in manifest:
        raw_path = entry["filepath"]
        if not os.path.exists(raw_path):
            raw_path = os.path.join(os.getcwd(), raw_path)
        assert os.path.exists(raw_path), f"Raw source file {raw_path} not found"
        
        # Verify checksum
        hasher = hashlib.sha256()
        with open(raw_path, "rb") as bf:
            for chunk in iter(lambda: bf.read(4096), b""):
                hasher.update(chunk)
        current_checksum = hasher.hexdigest()
        assert current_checksum == entry["checksum"], f"Checksum mismatch for {raw_path}"
        
        # Count elements in raw source
        with open(raw_path, "r", encoding="utf-8") as rf:
            raw_data = json.load(rf)
            raw_count = len(raw_data)
            
        # Determine date folder from path
        path_parts = os.path.normpath(raw_path).replace("\\", "/").split("/")
        date_str = None
        date_pat = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        for part in path_parts:
            if date_pat.match(part):
                date_str = part
                break
        if not date_str:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            
        # Verify staging file count matches raw count
        staging_path = os.path.join("data/raw_records/apify_google_maps", entry["region"], date_str, "places.jsonl")
        assert os.path.exists(staging_path), f"Staging file {staging_path} not found"
        with open(staging_path, "r", encoding="utf-8") as sf:
            staging_count = sum(1 for line in sf if line.strip())
        assert staging_count == raw_count, f"Staging file count mismatch for {staging_path}: staging={staging_count}, raw={raw_count}"
        
        expected_apify_raw += raw_count
        
    # Load and verify OSM elements
    osm_dir = "data/raw_records/osm"
    osm_files = glob.glob(os.path.join(osm_dir, "*.jsonl"))
    expected_osm_raw = 0
    for filepath in osm_files:
        with open(filepath, "r", encoding="utf-8") as f:
            expected_osm_raw += sum(1 for line in f if line.strip())
            
    expected_total_raw = expected_apify_raw + expected_osm_raw
    
    # Compare with report statistics (canonical_reconciliation.csv)
    report_csv_path = "reports/canonical_reconciliation.csv"
    if os.path.exists(report_csv_path):
        df_recon = pd.read_csv(report_csv_path)
        # Find raw counts from report
        osm_report = int(df_recon[df_recon["Metric"] == "OSM Raw Records"]["Count"].values[0])
        apify_report = int(df_recon[df_recon["Metric"] == "Apify Raw Records"]["Count"].values[0])
        total_report = int(df_recon[df_recon["Metric"] == "Total Raw Input Records"]["Count"].values[0])
        
        assert osm_report == expected_osm_raw, f"Report OSM raw count {osm_report} does not match expected {expected_osm_raw}"
        assert apify_report == expected_apify_raw, f"Report Apify raw count {apify_report} does not match expected {expected_apify_raw}"
        assert total_report == expected_total_raw, f"Report total raw count {total_report} does not match expected {expected_total_raw}"

def test_no_double_counted_regions():
    manifest_path = "data/raw_records/apify_google_maps/manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    regions = [entry["region"] for entry in manifest]
    assert len(regions) == len(set(regions)), "No region should be double counted in manifest"

def test_canonical_regions_only():
    from src.pipeline.normalize import REGION_MAP
    canonical_regions = set(REGION_MAP.values())
    
    normalized_path = "data/normalized/all_normalized.jsonl"
    if os.path.exists(normalized_path):
        with open(normalized_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    reg = item.get("city_regency")
                    assert reg in canonical_regions, f"Non-canonical region found in staging: {reg}"
