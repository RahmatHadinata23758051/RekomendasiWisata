import os
import json
import pytest
import pandas as pd
from src.enrichment.consolidated_master import run_master_consolidation, validate_master_dataset

@pytest.fixture(scope="module")
def full_df():
    # Verify that the generated full dataset can be loaded
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
    assert os.path.exists(os.path.join(output_dir, "consolidated_master_manifest_full.json"))
    
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
        "attractions_enrichment_master_full.jsonl",
        "consolidated_master_manifest_full.json"
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
