import os
import json
import pytest
import hashlib
import pandas as pd
from src.enrichment.consolidated_master import run_master_consolidation, validate_master_dataset

@pytest.fixture(scope="module")
def full_df():
    path = "data/enrichment/consolidated/attractions_enrichment_master_full.parquet"
    if os.path.exists(path):
        return pd.read_parquet(path)
    return None

def test_consolidated_master_full_build():
    population_path = "data/canonical/attractions_master_verified.parquet"
    canonical = "data/canonical/attractions_master_verified.parquet"
    reviews = "data/enrichment/final/reviews.parquet"
    metadata = "data/enrichment/metadata/full/place_metadata_full.parquet"
    facilities = "data/enrichment/metadata/relations/facilities_full.parquet"
    opening_hours = "data/enrichment/metadata/relations/opening_hours_full.parquet"
    local_price_obs = "data/enrichment/price/research/price_observations.csv"
    external_cov = "data/enrichment/price/external/external_verification_coverage.csv"
    external_prices = "data/enrichment/price/final/prices_external_verified.csv"
    
    output_dir = "data/enrichment/consolidated/test_output_full"
    reports_dir = "reports/test_output_full"
    
    # Run master consolidation for full population
    df_master = run_master_consolidation(
        pilot_population_path=population_path,
        canonical_path=canonical,
        reviews_path=reviews,
        metadata_path=metadata,
        facilities_path=facilities,
        opening_hours_path=opening_hours,
        local_price_obs_path=local_price_obs,
        external_coverage_path=external_cov,
        external_prices_path=external_prices,
        output_dir=output_dir,
        reports_dir=reports_dir,
        master_version="test_consolidated_version_full",
        dry_run=False,
        strict=True,
        force=True
    )
    
    assert len(df_master) == 3130
    assert df_master['canonical_id'].nunique() == 3130
    
    # Check that required output files exist
    assert os.path.exists(os.path.join(output_dir, "attractions_enrichment_master_full.csv"))
    assert os.path.exists(os.path.join(output_dir, "attractions_enrichment_master_full.parquet"))
    assert os.path.exists(os.path.join(output_dir, "attractions_enrichment_master_full.jsonl"))
    
    # Check relation files
    assert os.path.exists(os.path.join(output_dir, "relations", "review_summary.csv"))
    assert os.path.exists(os.path.join(output_dir, "relations", "opening_hours_normalized.csv"))
    assert os.path.exists(os.path.join(output_dir, "relations", "facilities_normalized.csv"))
    assert os.path.exists(os.path.join(output_dir, "relations", "local_price_evidence.csv"))
    assert os.path.exists(os.path.join(output_dir, "relations", "external_price_status.csv"))
    
    # Clean up test output
    for f in [
        "attractions_enrichment_master_full.csv",
        "attractions_enrichment_master_full.parquet",
        "attractions_enrichment_master_full.jsonl"
    ]:
        path = os.path.join(output_dir, f)
        if os.path.exists(path):
            os.remove(path)
            
    for rel_f in [
        "review_summary.csv", "review_summary.parquet",
        "opening_hours_normalized.csv", "opening_hours_normalized.parquet",
        "facilities_normalized.csv", "facilities_normalized.parquet",
        "local_price_evidence.csv", "local_price_evidence.parquet",
        "external_price_status.csv", "external_price_status.parquet"
    ]:
        path = os.path.join(output_dir, "relations", rel_f)
        if os.path.exists(path):
            os.remove(path)
            
    if os.path.exists(os.path.join(output_dir, "relations")):
        os.rmdir(os.path.join(output_dir, "relations"))
    if os.path.exists(output_dir):
        os.rmdir(output_dir)

def test_validate_master_dataset_full_duplicate(full_df):
    if full_df is None:
        pytest.skip("Full dataset not generated yet.")
    df_dup = full_df.copy()
    # Duplicate first row
    df_dup = pd.concat([df_dup, df_dup.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="Master row count is 3131, expected exactly 3130"):
        validate_master_dataset(df_dup, pd.DataFrame(), strict=True, expected_count=3130)

def test_non_pilot_reviews_fallback(full_df):
    if full_df is None:
        pytest.skip("Full dataset not generated yet.")
    
    # Pilot ID list (300 deterministic pilot places)
    df_pilot = pd.read_csv("data/enrichment/consolidated/pilot_population.csv")
    pilot_ids = set(df_pilot["canonical_id"])
    
    # Check non-pilot places reviews fallback
    non_pilot_df = full_df[~full_df["canonical_id"].isin(pilot_ids)]
    
    for _, row in non_pilot_df.iterrows():
        # Non-pilot place should either have scraped reviews (if available on disk)
        # or be marked as ineligible.
        if row["has_reviews"]:
            assert row["review_coverage_status"] == "scraped"
        else:
            assert row["review_coverage_status"] == "ineligible"

def test_metadata_one_to_one_join(full_df):
    if full_df is None:
        pytest.skip("Full dataset not generated yet.")
    mapped_count = (full_df["metadata_mapping_status"] == "mapped").sum()
    unmapped_count = (full_df["metadata_mapping_status"] == "unmapped").sum()
    assert int(mapped_count + unmapped_count) == 3130

def test_operational_and_hours_defaults(full_df):
    if full_df is None:
        pytest.skip("Full dataset not generated yet.")
    df_unknown_ops = full_df[full_df["operational_status"] == "unknown"]
    for _, row in df_unknown_ops.iterrows():
        assert row["operational_status_confidence"] == 0.0
    
    df_no_hours = full_df[~full_df["has_opening_hours"]]
    for _, row in df_no_hours.iterrows():
        assert row["opening_hours_status"] != "closed"

def test_price_defaults(full_df):
    if full_df is None:
        pytest.skip("Full dataset not generated yet.")
    df_no_ext = full_df[full_df["external_selected_price_count"] == 0]
    for _, row in df_no_ext.iterrows():
        assert pd.isna(row["external_price_min"])
        assert pd.isna(row["external_price_max"])

def test_quality_warnings_deterministic(full_df):
    if full_df is None:
        pytest.skip("Full dataset not generated yet.")
    for _, row in full_df.iterrows():
        ws_str = row["quality_warnings"]
        if pd.notna(ws_str):
            ws_list = json.loads(ws_str)
            assert len(ws_list) == row["quality_warning_count"]
            assert ws_list == sorted(ws_list)
            assert len(ws_list) == len(set(ws_list))

def test_completeness_score_range(full_df):
    if full_df is None:
        pytest.skip("Full dataset not generated yet.")
    assert full_df["overall_completeness_score"].min() >= 0.0
    assert full_df["overall_completeness_score"].max() <= 100.0

def test_manifest_row_counts_and_checksums():
    manifest_path = "data/enrichment/consolidated/consolidated_master_manifest_full.json"
    assert os.path.exists(manifest_path)
    with open(manifest_path, "r") as f:
        manifest = json.load(f)
    assert manifest["pilot_population_count"] == 3130
    assert manifest["master_row_count"] == 3130
    assert manifest["master_unique_ids"] == 3130
    assert len(manifest["output_checksums"]) > 0

def test_pilot_regression(full_df):
    if full_df is None:
        pytest.skip("Full dataset not generated yet.")
    df_pilot_pop = pd.read_csv("data/enrichment/consolidated/pilot_population.csv")
    pilot_ids = set(df_pilot_pop["canonical_id"])
    df_pilot_subset = full_df[full_df["canonical_id"].isin(pilot_ids)]
    
    pilot_frozen = pd.read_parquet("data/enrichment/consolidated/attractions_enrichment_master_pilot.parquet")
    for _, row_f in pilot_frozen.iterrows():
        row_m = df_pilot_subset[df_pilot_subset["canonical_id"] == row_f["canonical_id"]].iloc[0]
        assert row_f["name"] == row_m["name"]
        assert row_f["latitude"] == row_m["latitude"]
        assert row_f["longitude"] == row_m["longitude"]
        assert row_f["city_or_regency"] == row_m["city_or_regency"]

def test_region_and_category_totals(full_df):
    if full_df is None:
        pytest.skip("Full dataset not generated yet.")
    assert full_df["region"].notna().sum() == 3130
    assert full_df["region"].nunique() == 15
    assert full_df["primary_category"].notna().sum() == 3130

def test_dry_run_safety():
    population_path = "data/canonical/attractions_master_verified.parquet"
    canonical = "data/canonical/attractions_master_verified.parquet"
    reviews = "data/enrichment/final/reviews.parquet"
    metadata = "data/enrichment/metadata/full/place_metadata_full.parquet"
    facilities = "data/enrichment/metadata/relations/facilities_full.parquet"
    opening_hours = "data/enrichment/metadata/relations/opening_hours_full.parquet"
    local_price_obs = "data/enrichment/price/research/price_observations.csv"
    external_cov = "data/enrichment/price/external/external_verification_coverage.csv"
    external_prices = "data/enrichment/price/final/prices_external_verified.csv"
    
    output_dir = "data/enrichment/consolidated/test_output_dry_run"
    reports_dir = "reports/test_output_dry_run"
    
    df_dry = run_master_consolidation(
        pilot_population_path=population_path,
        canonical_path=canonical,
        reviews_path=reviews,
        metadata_path=metadata,
        facilities_path=facilities,
        opening_hours_path=opening_hours,
        local_price_obs_path=local_price_obs,
        external_coverage_path=external_cov,
        external_prices_path=external_prices,
        output_dir=output_dir,
        reports_dir=reports_dir,
        master_version="test_consolidated_version_full",
        dry_run=True,
        strict=True,
        force=True
    )
    
    assert len(df_dry) == 3130
    assert not os.path.exists(os.path.join(output_dir, "attractions_enrichment_master_full.csv"))
    assert not os.path.exists(os.path.join(output_dir, "attractions_enrichment_master_full.parquet"))

def test_two_run_determinism():
    assert os.path.exists("reports/consolidated_master_determinism_audit.json")
    with open("reports/consolidated_master_determinism_audit.json", "r") as f:
        det = json.load(f)
    assert det["matching"] == True

def test_frozen_input_integrity():
    # Calculate checksum of attractions_master_verified.parquet
    h = hashlib.sha256()
    with open("data/canonical/attractions_master_verified.parquet", "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    assert h.hexdigest() == "d9dd9500c0ab50cf3d0a6735c469ce95f75e2227782dce7072b010f282b9bde0"
