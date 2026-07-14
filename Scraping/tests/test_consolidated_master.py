import os
import json
import pytest
import hashlib
import pandas as pd
from src.enrichment.consolidated_master import run_master_consolidation, validate_master_dataset

@pytest.fixture(scope="module")
def master_df():
    return pd.read_parquet("data/enrichment/consolidated/attractions_enrichment_master_pilot.parquet")

def test_consolidated_master_build():
    pilot_pop = "data/enrichment/consolidated/pilot_population.csv"
    canonical = "data/canonical/attractions_master_verified.parquet"
    reviews = "data/enrichment/final/reviews.parquet"
    metadata = "data/enrichment/metadata/place_metadata.parquet"
    facilities = "data/enrichment/metadata/facilities.parquet"
    opening_hours = "data/enrichment/metadata/opening_hours.parquet"
    local_price_obs = "data/enrichment/price/research/price_observations.csv"
    external_cov = "data/enrichment/price/external/external_verification_coverage.csv"
    external_prices = "data/enrichment/price/final/prices_external_verified.csv"
    
    # 1. Output directory for test
    output_dir = "data/enrichment/consolidated/test_output"
    reports_dir = "reports/test_output"
    
    df_master = run_master_consolidation(
        pilot_population_path=pilot_pop,
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
        master_version="test_consolidated_version",
        dry_run=False,
        strict=True,
        force=True
    )
    
    # Check row count
    assert len(df_master) == 300
    assert df_master['canonical_id'].nunique() == 300
    
    # Check that required output files exist
    assert os.path.exists(os.path.join(output_dir, "attractions_enrichment_master_pilot.csv"))
    assert os.path.exists(os.path.join(output_dir, "attractions_enrichment_master_pilot.parquet"))
    assert os.path.exists(os.path.join(output_dir, "attractions_enrichment_master_pilot.jsonl"))
    
    # Check that relations exist
    assert os.path.exists(os.path.join(output_dir, "relations", "review_summary.csv"))
    assert os.path.exists(os.path.join(output_dir, "relations", "opening_hours_normalized.csv"))
    assert os.path.exists(os.path.join(output_dir, "relations", "facilities_normalized.csv"))
    assert os.path.exists(os.path.join(output_dir, "relations", "local_price_evidence.csv"))
    assert os.path.exists(os.path.join(output_dir, "relations", "external_price_status.csv"))
    
    # Validate JSONL completeness
    with open(os.path.join(output_dir, "attractions_enrichment_master_pilot.jsonl"), "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 300
        first_row = json.loads(lines[0])
        assert "canonical_id" in first_row
        
    # Test strict validation fails on duplicate canonical_id
    df_dup = df_master.copy()
    # duplicate first row
    df_dup = pd.concat([df_dup, df_dup.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="Master row count is 301, expected exactly 300|Duplicate canonical IDs found in master"):
        validate_master_dataset(df_dup, pd.DataFrame(), strict=True)
        
    # Clean up test output
    for f in [
        "attractions_enrichment_master_pilot.csv",
        "attractions_enrichment_master_pilot.parquet",
        "attractions_enrichment_master_pilot.jsonl"
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

# 1. Pilot population exactly 300.
def test_pilot_population_exactly_300():
    df = pd.read_csv("data/enrichment/consolidated/pilot_population.csv")
    assert len(df) == 300
    assert df['canonical_id'].nunique() == 300

# 2. Unique canonical IDs.
def test_unique_canonical_ids(master_df):
    assert master_df['canonical_id'].nunique() == 300

# 3. Master exactly 300 rows.
def test_master_exactly_300_rows(master_df):
    assert len(master_df) == 300

# 4. No join explosion.
def test_no_join_explosion(master_df):
    # If there was join explosion, len(master_df) would be > 300
    assert len(master_df) == 300

# 5. Review aggregation.
def test_review_aggregation(master_df):
    df_reviews = pd.read_parquet("data/enrichment/final/reviews.parquet")
    for _, row in master_df.head(10).iterrows():
        c_id = row['canonical_id']
        rev_subset = df_reviews[df_reviews['canonical_id'] == c_id]
        assert row['review_count'] == len(rev_subset)
        if len(rev_subset) > 0:
            assert abs(row['review_rating_mean'] - rev_subset['rating'].mean()) < 1e-5

# 6. Metadata unmapped semantics.
def test_metadata_unmapped_semantics(master_df):
    unmapped = master_df[master_df['metadata_mapping_status'] == 'unmapped']
    for _, row in unmapped.iterrows():
        assert row['metadata_completeness_score'] in [0.0, 20.0]
        assert row['operational_status'] == 'unknown'

# 7. Missing official website semantics.
def test_missing_official_website_semantics(master_df):
    for _, row in master_df.iterrows():
        web = row['official_website']
        if pd.isna(web) or str(web).strip() == "":
            assert row['website_status'] in ['missing', 'google_maps_only']
            if row['website_status'] == 'google_maps_only':
                assert pd.isna(web) or "google.com/maps" not in str(web).lower()

# 8. Facility unknown semantics.
def test_facility_unknown_semantics(master_df):
    unknowns = master_df[master_df['facility_count'] == 0]
    for _, row in unknowns.iterrows():
        assert row['has_parking'] == False
        assert row['has_toilet'] == False
        assert row['has_food'] == False
        assert row['has_prayer_room'] == False
        assert row['has_wheelchair_access'] == False
        assert row['facility_data_status'] == 'missing'

# 9. Opening-hours missing semantics.
def test_opening_hours_missing_semantics(master_df):
    missing = master_df[master_df['has_opening_hours'] == False]
    for _, row in missing.iterrows():
        assert row['opening_hours_status'] == 'missing'
        assert row['opening_days_count'] == 0
        assert row['open_24_hours'] == False

# 10. Local rejected prices excluded.
def test_local_rejected_prices_excluded():
    df_obs = pd.read_csv("data/enrichment/price/research/price_observations.csv")
    df_local_rel = pd.read_csv("data/enrichment/consolidated/relations/local_price_evidence.csv")
    rejected_ids = set(df_obs[df_obs['audit_decision'] == 'reject']['price_observation_id'])
    rel_ids = set(df_local_rel['local_observation_id'])
    assert not (rejected_ids & rel_ids)

# 11. Local historical prices not verified current.
def test_local_historical_prices_not_verified_current(master_df):
    for _, row in master_df.iterrows():
        if row['local_price_data_status'] == 'historical_only':
            assert row['has_verified_current_price'] == False

# 12. completed_no_price not free.
def test_completed_no_price_not_free(master_df):
    no_price = master_df[master_df['external_verification_status'] == 'completed_no_price']
    for _, row in no_price.iterrows():
        assert pd.isna(row['external_price_min'])
        assert pd.isna(row['external_price_max'])

# 13. completed_unresolved not zero.
def test_completed_unresolved_not_zero(master_df):
    unres = master_df[master_df['external_verification_status'] == 'completed_unresolved']
    for _, row in unres.iterrows():
        assert pd.isna(row['external_price_min'])
        assert pd.isna(row['external_price_max'])

# 14. External selected count matches relation.
def test_external_selected_count_matches_relation(master_df):
    df_ext_rel = pd.read_csv("data/enrichment/price/final/prices_external_verified.csv")
    for _, row in master_df.iterrows():
        pid = row['canonical_id']
        rel_count = len(df_ext_rel[df_ext_rel['canonical_id'] == pid])
        assert row['external_selected_price_count'] == rel_count

# 15. External min/max null when selected count is zero.
def test_external_min_max_null_when_selected_count_zero(master_df):
    zero_selected = master_df[master_df['external_selected_price_count'] == 0]
    for _, row in zero_selected.iterrows():
        assert pd.isna(row['external_price_min'])
        assert pd.isna(row['external_price_max'])

# 16. Completeness score range.
def test_completeness_score_range(master_df):
    assert master_df['overall_completeness_score'].between(0.0, 100.0).all()

# 17. Completeness class thresholds.
def test_completeness_class_thresholds(master_df):
    for _, row in master_df.iterrows():
        score = row['overall_completeness_score']
        c_class = row['overall_completeness_class']
        if score >= 90:
            assert c_class == 'complete'
        elif score >= 75:
            assert c_class == 'strong'
        elif score >= 50:
            assert c_class == 'moderate'
        else:
            assert c_class == 'sparse'

# 18. Sorted deterministic warnings.
def test_sorted_deterministic_warnings(master_df):
    for _, row in master_df.iterrows():
        warnings_str = row['quality_warnings']
        warnings = json.loads(warnings_str)
        assert warnings == sorted(warnings)

# 19. Manifest counts.
def test_manifest_counts(master_df):
    with open("data/enrichment/consolidated/consolidated_master_manifest.json", "r") as f:
        m = json.load(f)
    assert m['pilot_population_count'] == 300
    assert m['master_row_count'] == 300
    assert m['master_unique_ids'] == 300

# 20. Manifest checksums.
def test_manifest_checksums():
    with open("data/enrichment/consolidated/consolidated_master_manifest.json", "r") as f:
        m = json.load(f)
    for name, path in m['output_files'].items():
        if os.path.exists(path):
            expected_sha = m['output_checksums'][os.path.basename(path)]
            h = hashlib.sha256()
            with open(path, "rb") as f_bin:
                while True:
                    chunk = f_bin.read(65536)
                    if not chunk:
                        break
                    h.update(chunk)
            assert h.hexdigest() == expected_sha

# 21. Dry-run writes no outputs.
def test_dry_run_writes_no_outputs(tmp_path):
    pilot_pop = "data/enrichment/consolidated/pilot_population.csv"
    canonical = "data/canonical/attractions_master_verified.parquet"
    reviews = "data/enrichment/final/reviews.parquet"
    metadata = "data/enrichment/metadata/place_metadata.parquet"
    facilities = "data/enrichment/metadata/facilities.parquet"
    opening_hours = "data/enrichment/metadata/opening_hours.parquet"
    local_price_obs = "data/enrichment/price/research/price_observations.csv"
    external_cov = "data/enrichment/price/external/external_verification_coverage.csv"
    external_prices = "data/enrichment/price/final/prices_external_verified.csv"
    
    output_dir = tmp_path / "dry_run_output"
    reports_dir = tmp_path / "dry_run_reports"
    
    df_master = run_master_consolidation(
        pilot_population_path=pilot_pop,
        canonical_path=canonical,
        reviews_path=reviews,
        metadata_path=metadata,
        facilities_path=facilities,
        opening_hours_path=opening_hours,
        local_price_obs_path=local_price_obs,
        external_coverage_path=external_cov,
        external_prices_path=external_prices,
        output_dir=str(output_dir),
        reports_dir=str(reports_dir),
        master_version="dry_run_version",
        dry_run=True,
        strict=True,
        force=True
    )
    assert not os.path.exists(os.path.join(str(output_dir), "attractions_enrichment_master_pilot.csv"))

# 22. Two-run determinism.
def test_two_run_determinism(tmp_path):
    import shutil
    shutil.copy2("data/enrichment/consolidated/pilot_population.csv", tmp_path / "pilot_population.csv")
    shutil.copy2("data/canonical/attractions_master_verified.parquet", tmp_path / "attractions_master_verified.parquet")
    shutil.copy2("data/enrichment/final/reviews.parquet", tmp_path / "reviews.parquet")
    shutil.copy2("data/enrichment/metadata/place_metadata.parquet", tmp_path / "place_metadata.parquet")
    shutil.copy2("data/enrichment/metadata/operational_status.parquet", tmp_path / "operational_status.parquet")
    shutil.copy2("data/enrichment/metadata/facilities.parquet", tmp_path / "facilities.parquet")
    shutil.copy2("data/enrichment/metadata/opening_hours.parquet", tmp_path / "opening_hours.parquet")
    shutil.copy2("data/enrichment/price/research/price_observations.csv", tmp_path / "price_observations.csv")
    shutil.copy2("data/enrichment/price/external/external_verification_coverage.csv", tmp_path / "external_verification_coverage.csv")
    shutil.copy2("data/enrichment/price/final/prices_external_verified.csv", tmp_path / "prices_external_verified.csv")
    
    pilot_pop = str(tmp_path / "pilot_population.csv")
    canonical = str(tmp_path / "attractions_master_verified.parquet")
    reviews = str(tmp_path / "reviews.parquet")
    metadata = str(tmp_path / "place_metadata.parquet")
    facilities = str(tmp_path / "facilities.parquet")
    opening_hours = str(tmp_path / "opening_hours.parquet")
    local_price_obs = str(tmp_path / "price_observations.csv")
    external_cov = str(tmp_path / "external_verification_coverage.csv")
    external_prices = str(tmp_path / "prices_external_verified.csv")
    
    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"
    rep1 = tmp_path / "rep1"
    rep2 = tmp_path / "rep2"
    
    df1 = run_master_consolidation(
        pilot_population_path=pilot_pop,
        canonical_path=canonical,
        reviews_path=reviews,
        metadata_path=metadata,
        facilities_path=facilities,
        opening_hours_path=opening_hours,
        local_price_obs_path=local_price_obs,
        external_coverage_path=external_cov,
        external_prices_path=external_prices,
        output_dir=str(out1),
        reports_dir=str(rep1),
        master_version="det_v1",
        dry_run=False,
        strict=True,
        force=True
    )
    
    df2 = run_master_consolidation(
        pilot_population_path=pilot_pop,
        canonical_path=canonical,
        reviews_path=reviews,
        metadata_path=metadata,
        facilities_path=facilities,
        opening_hours_path=opening_hours,
        local_price_obs_path=local_price_obs,
        external_coverage_path=external_cov,
        external_prices_path=external_prices,
        output_dir=str(out2),
        reports_dir=str(rep2),
        master_version="det_v1",
        dry_run=False,
        strict=True,
        force=True
    )
    
    cols_to_compare = [c for c in df1.columns if c != 'generated_at']
    pd.testing.assert_frame_equal(df1[cols_to_compare], df2[cols_to_compare])

# 23. Frozen source integrity.
def test_frozen_source_integrity():
    with open("data/enrichment/consolidated/consolidated_master_manifest.json", "r") as f:
        m = json.load(f)
    for name, path in m['source_files'].items():
        if os.path.exists(path):
            h = hashlib.sha256()
            with open(path, "rb") as f_bin:
                while True:
                    chunk = f_bin.read(65536)
                    if not chunk:
                        break
                    h.update(chunk)
            assert h.hexdigest() == m['source_checksums'][name]

# 24. Schema invalid enum failure.
def test_schema_invalid_enum_failure():
    df_err = pd.read_parquet("data/enrichment/consolidated/attractions_enrichment_master_pilot.parquet")
    df_err.loc[0, 'latitude'] = 150.0
    with pytest.raises(ValueError, match="Latitude coordinate out of bounds"):
        validate_master_dataset(df_err, pd.DataFrame(), strict=True)

# 25. Duplicate canonical ID failure.
def test_duplicate_canonical_id_failure():
    df_err = pd.read_parquet("data/enrichment/consolidated/attractions_enrichment_master_pilot.parquet")
    df_err = pd.concat([df_err, df_err.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="Master row count is 301, expected exactly 300|Duplicate canonical IDs found in master"):
        validate_master_dataset(df_err, pd.DataFrame(), strict=True)
