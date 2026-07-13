import os
import json
import pytest
import pandas as pd
from src.enrichment.pilot_selector import select_pilot_places, is_real_website

def test_pilot_selector_correctness():
    input_path = "data/canonical/attractions_master_verified.jsonl"
    sources_path = "data/canonical/attraction_sources.parquet"
    normalized_path = "data/normalized/all_normalized.jsonl"
    possible_dup_path = "reports/possible_duplicate_candidates.csv"
    
    # 1. Output count is exactly 300
    df_pilot = select_pilot_places(
        input_path=input_path,
        sources_path=sources_path,
        normalized_path=normalized_path,
        possible_dup_path=possible_dup_path,
        size=300,
        seed=42
    )
    assert len(df_pilot) == 300, f"Expected 300, got {len(df_pilot)}"
    
    # 2. All canonical_id are unique
    assert df_pilot["canonical_id"].is_unique, "canonical_id values are not unique"
    
    # 3. Only comes from verified master
    df_verified = pd.read_parquet(input_path.replace(".jsonl", ".parquet"))
    verified_ids = set(df_verified["canonical_id"])
    pilot_ids = set(df_pilot["canonical_id"])
    assert pilot_ids.issubset(verified_ids), "Some pilot IDs are not in verified master"
    
    # 4. All 15 regions are represented
    regions = df_pilot["region"].unique()
    assert len(regions) == 15, f"Expected 15 regions, got {len(regions)}"
    
    # 5. Maximum share per region (15% = 45 records for Bandar Lampung) is respected
    bl_count = sum(df_pilot["region"] == "Kota Bandar Lampung")
    assert bl_count <= 45, f"Kota Bandar Lampung exceeded max share: got {bl_count}"
    
    # 6. Random seed produces identical output
    df_pilot_again = select_pilot_places(
        input_path=input_path,
        sources_path=sources_path,
        normalized_path=normalized_path,
        possible_dup_path=possible_dup_path,
        size=300,
        seed=42
    )
    pd.testing.assert_frame_equal(
        df_pilot.drop(columns=["selected_at"]).reset_index(drop=True), 
        df_pilot_again.drop(columns=["selected_at"]).reset_index(drop=True)
    )
    
    # Check that a different seed produces a different output (mostly different)
    df_pilot_diff = select_pilot_places(
        input_path=input_path,
        sources_path=sources_path,
        normalized_path=normalized_path,
        possible_dup_path=possible_dup_path,
        size=300,
        seed=100
    )
    # Check they are not identical
    assert not df_pilot["canonical_id"].equals(df_pilot_diff["canonical_id"])

    # 7. Rare categories are represented
    # Verify that culture, education, religious, river, which are rare, are in the pilot
    for cat in ["culture", "education", "religious", "river"]:
        assert cat in df_pilot["primary_category"].values, f"Rare category {cat} missing from pilot"

    # 8. Correct rating segmentation
    for _, row in df_pilot.iterrows():
        rating = row["rating"]
        seg = row["rating_segment"]
        if pd.isna(rating) or rating is None or str(rating).strip().lower() in ["none", "nan", "null"]:
            assert seg == "empty"
        else:
            val = float(rating)
            if val >= 4.5:
                assert seg == "high"
            elif val >= 4.0:
                assert seg == "medium"
            else:
                assert seg == "low"

    # 9. Correct review count segmentation
    for _, row in df_pilot.iterrows():
        c = row["review_count"]
        seg = row["review_count_segment"]
        if pd.isna(c) or c is None or str(c).strip().lower() in ["none", "nan", "null"]:
            assert seg == "no_review"
        else:
            val = int(c)
            if val >= 1000:
                assert seg == "popular"
            elif val >= 100:
                assert seg == "medium"
            elif val >= 1:
                assert seg == "low"
            else:
                assert seg == "no_review"

    # 10. Record without Google Place ID remains in pilot with has_google_place_id = False
    no_g_records = df_pilot[~df_pilot["has_google_place_id"]]
    assert len(no_g_records) > 0, "Expected at least one record without Google Place ID"
    for _, row in no_g_records.iterrows():
        assert pd.isna(row["google_place_id"]) or row["google_place_id"] is None or row["google_place_id"] == ""

def test_enrichment_schema_mandatory_columns():
    schema_dir = "data/enrichment/schema"
    
    # Verify prices.csv columns
    prices_path = os.path.join(schema_dir, "prices.csv")
    assert os.path.exists(prices_path)
    df_prices = pd.read_csv(prices_path)
    expected_prices_cols = [
        "price_id", "canonical_id", "price_type", "amount_min", "amount_max", "currency", 
        "applies_to", "unit", "valid_day_type", "source_name", "source_url", "observed_at", 
        "effective_date", "confidence", "verification_status", "notes"
    ]
    assert list(df_prices.columns) == expected_prices_cols
    
    # Verify reviews.csv columns
    reviews_path = os.path.join(schema_dir, "reviews.csv")
    assert os.path.exists(reviews_path)
    df_reviews = pd.read_csv(reviews_path)
    expected_reviews_cols = [
        "review_id", "canonical_id", "source", "source_place_id", "rating", "review_text", 
        "review_date", "language", "sentiment_bucket", "sentiment_method", "review_url", 
        "collected_at", "is_duplicate", "content_hash"
    ]
    assert list(df_reviews.columns) == expected_reviews_cols

def test_pilot_selector_fails_if_size_too_large():
    input_path = "data/canonical/attractions_master_verified.jsonl"
    sources_path = "data/canonical/attraction_sources.parquet"
    normalized_path = "data/normalized/all_normalized.jsonl"
    possible_dup_path = "reports/possible_duplicate_candidates.csv"
    
    with pytest.raises(ValueError) as excinfo:
        select_pilot_places(
            input_path=input_path,
            sources_path=sources_path,
            normalized_path=normalized_path,
            possible_dup_path=possible_dup_path,
            size=10000, # way larger than dataset
            seed=42
        )
    assert "is larger than verified dataset count" in str(excinfo.value)
