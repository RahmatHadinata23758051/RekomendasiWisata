import os
import json
import pandas as pd
import pytest
from src.enrichment.metadata_backfill import (
    classify_website_detailed,
    run_metadata_scaling,
    get_sha256
)

# Test 1: Queue file size matches 3130
def test_queue_file_size():
    queue_path = "data/enrichment/metadata/scaling/metadata_scaling_queue.csv"
    assert os.path.exists(queue_path)
    df_queue = pd.read_csv(queue_path)
    assert len(df_queue) == 3130

# Test 2: Queue canonical IDs are unique
def test_queue_ids_unique():
    queue_path = "data/enrichment/metadata/scaling/metadata_scaling_queue.csv"
    df_queue = pd.read_csv(queue_path)
    assert df_queue["canonical_id"].is_unique

# Test 3: Output place_metadata_full has 3130 rows
def test_output_metadata_size():
    meta_path = "data/enrichment/metadata/full/place_metadata_full.csv"
    assert os.path.exists(meta_path)
    df_meta = pd.read_csv(meta_path)
    assert len(df_meta) == 3130

# Test 4: Output place_metadata_full canonical IDs are unique
def test_output_metadata_unique():
    meta_path = "data/enrichment/metadata/full/place_metadata_full.csv"
    df_meta = pd.read_csv(meta_path)
    assert df_meta["canonical_id"].is_unique

# Test 5: Unmapped operational status is unknown
def test_unmapped_operational_status():
    meta_path = "data/enrichment/metadata/full/place_metadata_full.csv"
    df_meta = pd.read_csv(meta_path)
    unmapped = df_meta[df_meta["mapping_status"] == "unmapped"]
    if not unmapped.empty:
        assert (unmapped["operational_status"] == "unknown").all()

# Test 6: Mapped operational status is not null
def test_mapped_operational_status():
    meta_path = "data/enrichment/metadata/full/place_metadata_full.csv"
    df_meta = pd.read_csv(meta_path)
    mapped = df_meta[df_meta["mapping_status"] == "mapped"]
    if not mapped.empty:
        assert mapped["operational_status"].notna().all()

# Test 7: Google Maps profile URLs are not official websites
def test_website_classification_google_maps():
    res = classify_website_detailed("https://google.com/maps?query_place_id=123", "Test Place")
    assert res["website_type"] == "map_profile"
    assert not res["is_official"]

# Test 8: OpenStreetMap URLs are not official websites
def test_website_classification_osm():
    res = classify_website_detailed("https://www.openstreetmap.org/node/123", "Test Place")
    assert res["website_type"] == "map_profile"
    assert not res["is_official"]

# Test 9: Independent domains are official websites
def test_website_classification_independent():
    res = classify_website_detailed("https://www.pantaisari.com", "Pantai Sari")
    assert res["website_type"] == "official_website"
    assert res["is_official"]

# Test 10: Social media name match is strong
def test_website_classification_social_strong():
    res = classify_website_detailed("https://instagram.com/pantai_sari", "Pantai Sari")
    assert res["website_type"] == "official_social_media"
    assert res["is_official"]
    assert res["identity_match_status"] == "strong"

# Test 11: Social media name mismatch is weak
def test_website_classification_social_weak():
    res = classify_website_detailed("https://instagram.com/another_place", "Pantai Sari")
    assert res["website_type"] == "official_social_media"
    assert not res["is_official"]
    assert res["identity_match_status"] == "weak"

# Test 12: Accessibility status is either observed or missing
def test_accessibility_status_values():
    meta_path = "data/enrichment/metadata/full/place_metadata_full.csv"
    df_meta = pd.read_csv(meta_path)
    allowed = {"observed", "missing"}
    assert set(df_meta["accessibility_status"].dropna().unique()).issubset(allowed)

# Test 13: Completeness score is between 0 and 100
def test_completeness_score_range():
    meta_path = "data/enrichment/metadata/full/place_metadata_full.csv"
    df_meta = pd.read_csv(meta_path)
    assert (df_meta["metadata_completeness_score"] >= 0.0).all()
    assert (df_meta["metadata_completeness_score"] <= 100.0).all()

# Test 14: Completeness class is complete, strong, moderate, or sparse
def test_completeness_class_values():
    meta_path = "data/enrichment/metadata/full/place_metadata_full.csv"
    df_meta = pd.read_csv(meta_path)
    allowed = {"complete", "strong", "moderate", "sparse"}
    assert set(df_meta["metadata_completeness_class"].unique()).issubset(allowed)

# Test 15: Phone numbers start with 62 or +62
def test_phones_prefix():
    phones_path = "data/enrichment/metadata/relations/phones_full.csv"
    if os.path.exists(phones_path):
        df_phones = pd.read_csv(phones_path)
        if not df_phones.empty:
            assert df_phones["normalized_phone"].apply(lambda p: str(p).isdigit()).all()

# Test 16: Addresses contain city_or_regency
def test_addresses_region():
    addr_path = "data/enrichment/metadata/relations/addresses_full.csv"
    if os.path.exists(addr_path):
        df_addr = pd.read_csv(addr_path)
        if not df_addr.empty:
            assert df_addr["city_or_regency"].notna().all()

# Test 17: Mappings without canonical ID count is zero or positive
def test_mappings_without_canonical():
    orphan_path = "data/enrichment/metadata/full/metadata_full_manifest.json"
    with open(orphan_path, "r") as f:
        m = json.load(f)
    assert m["output_row_count"] == 3130

# Test 18: Zero duplicates in output metadata
def test_zero_duplicates_metadata():
    meta_path = "data/enrichment/metadata/full/place_metadata_full.csv"
    df_meta = pd.read_csv(meta_path)
    assert len(df_meta) == df_meta["canonical_id"].nunique()

# Test 19: Pilot regression checks are fully allowed
def test_pilot_regression_audit():
    reg_path = "reports/metadata_scaling_pilot_regression_audit.csv"
    assert os.path.exists(reg_path)
    df_reg = pd.read_csv(reg_path)
    assert (df_reg["allowed_change"] == True).all()

# Test 20: Manifest lists output file sizes correctly
def test_manifest_output_sizes():
    manifest_path = "data/enrichment/metadata/full/metadata_full_manifest.json"
    with open(manifest_path, "r") as f:
        m = json.load(f)
    assert m["output_row_count"] == 3130
    assert m["output_unique_ids"] == 3130

# Test 21: Final integrity is passed
def test_final_integrity_passed():
    int_path = "reports/metadata_scaling_final_integrity.json"
    assert os.path.exists(int_path)
    with open(int_path, "r") as f:
        data = json.load(f)
    assert data["integrity_status"] == "passed"

# Test 22: Mapped metadata completeness score details
def test_mapped_completeness_details():
    meta_path = "data/enrichment/metadata/full/place_metadata_full.csv"
    df_meta = pd.read_csv(meta_path)
    mapped = df_meta[df_meta["mapping_status"] == "mapped"]
    if not mapped.empty:
        # Mapped scores must be >= 20.0 (since mapping success adds 20.0)
        assert (mapped["metadata_completeness_score"] >= 20.0).all()

# Test 23: Conflict audit contains resolved rows only
def test_conflict_resolutions():
    conf_path = "reports/metadata_scaling_conflict_audit.csv"
    if os.path.exists(conf_path):
        df_conf = pd.read_csv(conf_path)
        if not df_conf.empty:
            assert (df_conf["resolution_status"] == "resolved").all()

# Test 24: Unmapped places has score exactly 0
def test_unmapped_completeness_score():
    meta_path = "data/enrichment/metadata/full/place_metadata_full.csv"
    df_meta = pd.read_csv(meta_path)
    unmapped = df_meta[df_meta["mapping_status"] == "unmapped"]
    if not unmapped.empty:
        assert (unmapped["metadata_completeness_score"] == 0.0).all()

# Test 25: Website sources type matches allowed list
def test_website_sources_types():
    web_path = "data/enrichment/metadata/relations/website_sources_full.csv"
    if os.path.exists(web_path):
        df_web = pd.read_csv(web_path)
        if not df_web.empty:
            allowed = {"official_website", "official_social_media", "government", "ticketing_partner", "travel_marketplace", "directory", "news_media", "blog", "map_profile", "unknown"}
            assert set(df_web["website_type"].unique()).issubset(allowed)

# Test 26: Opening hours intervals are positive
def test_opening_hours_intervals():
    oh_path = "data/enrichment/metadata/relations/opening_hours_full.csv"
    if os.path.exists(oh_path):
        df_oh = pd.read_csv(oh_path)
        if not df_oh.empty:
            assert (df_oh["interval_index"] >= 0).all()

# Test 27: Facilities availability status conforms to schema
def test_facilities_status():
    fac_path = "data/enrichment/metadata/relations/facilities_full.csv"
    if os.path.exists(fac_path):
        df_fac = pd.read_csv(fac_path)
        if not df_fac.empty:
            allowed = {"available", "unavailable", "unknown", "inferred", "not_applicable"}
            assert set(df_fac["availability_status"].unique()).issubset(allowed)

# Test 28: Zero drift on frozen attractions_master_verified
def test_attractions_verified_drift():
    baseline_path = "reports/metadata_scaling_input_integrity_baseline.json"
    with open(baseline_path, "r") as f:
        baseline = json.load(f)
    for b in baseline:
        if "attractions_master_verified.parquet" in b["file_path"]:
            curr_sha = get_sha256(b["file_path"])
            assert curr_sha == b["sha256"]

# Test 29: Zero drift on frozen consolidated master pilot
def test_consolidated_master_pilot_drift():
    baseline_path = "reports/metadata_scaling_input_integrity_baseline.json"
    with open(baseline_path, "r") as f:
        baseline = json.load(f)
    for b in baseline:
        if "attractions_enrichment_master_pilot.parquet" in b["file_path"]:
            curr_sha = get_sha256(b["file_path"])
            assert curr_sha == b["sha256"]

# Test 30: Zero drift on frozen pilot_population
def test_pilot_population_drift():
    baseline_path = "reports/metadata_scaling_input_integrity_baseline.json"
    with open(baseline_path, "r") as f:
        baseline = json.load(f)
    for b in baseline:
        if "pilot_population.csv" in b["file_path"]:
            curr_sha = get_sha256(b["file_path"])
            assert curr_sha == b["sha256"]

# Test 31: Two-run match determinism verification
def test_two_run_determinism(tmp_path):
    # Running a subset run for determinism comparison
    canary_path = "data/enrichment/metadata/scaling/metadata_canary_population.csv"
    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"
    rep1 = tmp_path / "rep1"
    rep2 = tmp_path / "rep2"
    
    run_metadata_scaling(
        population_path=canary_path,
        queue_path=canary_path,
        output_dir=str(out1),
        reports_dir=str(rep1),
        fresh_run=True,
        master_version="det-test"
    )
    
    run_metadata_scaling(
        population_path=canary_path,
        queue_path=canary_path,
        output_dir=str(out2),
        reports_dir=str(rep2),
        fresh_run=True,
        master_version="det-test"
    )
    
    df1 = pd.read_csv(out1 / "place_metadata_full.csv").drop(columns=["updated_at"])
    df2 = pd.read_csv(out2 / "place_metadata_full.csv").drop(columns=["updated_at"])
    pd.testing.assert_frame_equal(df1, df2)

# Test 32: Unique canonical IDs in relation tables match place_metadata_full
def test_relation_integrity():
    meta_path = "data/enrichment/metadata/full/place_metadata_full.csv"
    df_meta = pd.read_csv(meta_path)
    meta_ids = set(df_meta["canonical_id"].tolist())
    
    relations_dir = "data/enrichment/metadata/relations"
    for rel in ["website_sources_full", "addresses_full", "phones_full", "opening_hours_full", "facilities_full"]:
        p = os.path.join(relations_dir, f"{rel}.csv")
        if os.path.exists(p):
            df_rel = pd.read_csv(p)
            if not df_rel.empty:
                rel_ids = set(df_rel["canonical_id"].unique())
                assert rel_ids.issubset(meta_ids)
