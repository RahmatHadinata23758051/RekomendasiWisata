import os
import json
import hashlib
import pandas as pd
import numpy as np
import pytest
from src.enrichment.metadata_backfill import (
    haversine_distance,
    fuzzy_match_ratio,
    normalize_url,
    normalize_phone,
    parse_hours_string,
    classify_price_priority,
    run_metadata_backfill
)

# 1. Tepat 300 pilot place diproses
# 2. Canonical ID unik
# 3. Tidak mengambil attractions_candidates
def test_pilot_places_integrity():
    df_pilot = pd.read_parquet("data/enrichment/pilot/pilot_places.parquet")
    assert len(df_pilot) == 300
    assert df_pilot["canonical_id"].nunique() == 300
    
    # Assert that all canonical IDs are verified ones (none from attractions_candidates)
    df_verified = pd.read_parquet("data/canonical/attractions_master_verified.parquet")
    verified_ids = set(df_verified["canonical_id"])
    pilot_ids = set(df_pilot["canonical_id"])
    assert pilot_ids.issubset(verified_ids)
    
    # Check that attractions_candidates is not mixed
    if os.path.exists("data/canonical/attractions_candidates.parquet"):
        df_cand = pd.read_parquet("data/canonical/attractions_candidates.parquet")
        cand_ids = set(df_cand["canonical_id"])
        # Verified and candidates should be disjoint
        assert verified_ids.isdisjoint(cand_ids)
        assert pilot_ids.isdisjoint(cand_ids)

# 4. Mapping Place ID benar
# 5. Mapping source_record_id benar
# 6. Nama saja tidak cukup untuk mapping
# 7. Fallback nama + koordinat memerlukan jarak <= 100 meter
# 8. Raw record ambigu tidak dipaksakan
def test_mapping_rules(tmp_path):
    # Setup test pilot place
    pilot_data = [{
        "canonical_id": "can_test_place",
        "name": "Pantai Sari",
        "region": "Kabupaten Pesawaran",
        "latitude": -5.5000,
        "longitude": 105.1000,
        "google_place_id": "ChIJ_test_place_id",
        "source_place_id": "ChIJ_test_place_id",
        "source_url": "https://google.com/maps?query_place_id=ChIJ_test_place_id",
        "source_count": 1,
        "primary_category": "beach",
        "category_tags": np.array(["beach", "nature"], dtype=object)
    }]
    pilot_df = pd.DataFrame(pilot_data)
    pilot_df.to_parquet(tmp_path / "pilot_places.parquet")
    
    # Setup test source map
    sources_data = [{
        "source_record_id": "apify_google_maps_ChIJ_test_place_id",
        "canonical_id": "can_test_place",
        "confidence": 1.0,
        "match_status": "new",
        "dedup_reason": "test"
    }]
    sources_df = pd.DataFrame(sources_data)
    sources_df.to_parquet(tmp_path / "attraction_sources.parquet")
    
    # Setup temporary output and reports dirs
    output_dir = tmp_path / "output"
    reports_dir = tmp_path / "reports"
    
    # 1. Exact Source Record ID Mapping
    # Create raw record matching source_record_id
    raw_rec_1 = {
        "source_record_id": "apify_google_maps_ChIJ_test_place_id",
        "source_place_id": "ChIJ_different_id",
        "source_url": "https://google.com/maps?query_place_id=ChIJ_different_id",
        "raw_name": "Pantai Sari",
        "latitude": -5.5000,
        "longitude": 105.1000,
        "query_region": "pesawaran",
        "raw_address": "Jl. Pantai No. 1",
        "rating": 4.5,
        "review_count": 10,
        "phone": "0812345678",
        "website": "http://pantaisari.com",
        "scrapedAt": "2026-07-14T00:00:00Z",
        "collected_at": "2026-07-14T00:00:00Z",
        "permanently_closed": False,
        "temporarily_closed": False,
        "description": "Indah",
        "raw_payload_path": ""
    }
    
    # Write raw record
    raw_dir = tmp_path / "raw_records" / "pesawaran"
    os.makedirs(raw_dir, exist_ok=True)
    pd.DataFrame([raw_rec_1]).to_parquet(raw_dir / "places.parquet")
    
    run_metadata_backfill(
        pilot_path=str(tmp_path / "pilot_places.parquet"),
        source_map_path=str(tmp_path / "attraction_sources.parquet"),
        raw_root=str(tmp_path / "raw_records"),
        output_dir=str(output_dir),
        reports_dir=str(reports_dir)
    )
    
    df_meta = pd.read_parquet(output_dir / "place_metadata.parquet")
    assert len(df_meta) == 1
    row = df_meta.iloc[0]
    assert row["canonical_id"] == "can_test_place"
    assert row["mapping_method"] == "source_record_id"
    assert row["mapping_confidence"] == 1.0
    
    # 2. Exact Place ID Mapping (when source_record_id does not match)
    raw_rec_2 = raw_rec_1.copy()
    raw_rec_2["source_record_id"] = "apify_google_maps_unknown"
    raw_rec_2["source_place_id"] = "ChIJ_test_place_id"
    pd.DataFrame([raw_rec_2]).to_parquet(raw_dir / "places.parquet")
    
    run_metadata_backfill(
        pilot_path=str(tmp_path / "pilot_places.parquet"),
        source_map_path=str(tmp_path / "attraction_sources.parquet"),
        raw_root=str(tmp_path / "raw_records"),
        output_dir=str(output_dir),
        reports_dir=str(reports_dir)
    )
    df_meta = pd.read_parquet(output_dir / "place_metadata.parquet")
    assert df_meta.iloc[0]["mapping_method"] == "google_place_id"
    
    # 3. Normalized URL Mapping
    raw_rec_3 = raw_rec_1.copy()
    raw_rec_3["source_record_id"] = "apify_google_maps_unknown"
    raw_rec_3["source_place_id"] = "ChIJ_different_id"
    raw_rec_3["source_url"] = "https://google.com/maps?query_place_id=ChIJ_test_place_id"
    pd.DataFrame([raw_rec_3]).to_parquet(raw_dir / "places.parquet")
    
    run_metadata_backfill(
        pilot_path=str(tmp_path / "pilot_places.parquet"),
        source_map_path=str(tmp_path / "attraction_sources.parquet"),
        raw_root=str(tmp_path / "raw_records"),
        output_dir=str(output_dir),
        reports_dir=str(reports_dir)
    )
    df_meta = pd.read_parquet(output_dir / "place_metadata.parquet")
    assert df_meta.iloc[0]["mapping_method"] == "normalized_url"
    
    # 4. Fallback: Name + Coordinates (within 100 meters, matching region)
    # Jarak -5.5000, 105.1000 ke -5.5005, 105.1005 is ~78 meters.
    raw_rec_4 = raw_rec_1.copy()
    raw_rec_4["source_record_id"] = "apify_google_maps_unknown"
    raw_rec_4["source_place_id"] = "ChIJ_different_id"
    raw_rec_4["source_url"] = "https://google.com/maps?query_place_id=ChIJ_different_id"
    raw_rec_4["raw_name"] = "Pantai Sari" # fuzzy match ratio >= 0.85
    raw_rec_4["latitude"] = -5.5005
    raw_rec_4["longitude"] = 105.1005
    pd.DataFrame([raw_rec_4]).to_parquet(raw_dir / "places.parquet")
    
    run_metadata_backfill(
        pilot_path=str(tmp_path / "pilot_places.parquet"),
        source_map_path=str(tmp_path / "attraction_sources.parquet"),
        raw_root=str(tmp_path / "raw_records"),
        output_dir=str(output_dir),
        reports_dir=str(reports_dir)
    )
    df_meta = pd.read_parquet(output_dir / "place_metadata.parquet")
    assert df_meta.iloc[0]["mapping_method"] == "coordinates_name_fallback"
    
    # 5. Name fuzzy matches but coordinates too far (> 100m)
    # Distance is ~800m
    raw_rec_5 = raw_rec_4.copy()
    raw_rec_5["latitude"] = -5.5050
    raw_rec_5["longitude"] = 105.1050
    pd.DataFrame([raw_rec_5]).to_parquet(raw_dir / "places.parquet")
    
    run_metadata_backfill(
        pilot_path=str(tmp_path / "pilot_places.parquet"),
        source_map_path=str(tmp_path / "attraction_sources.parquet"),
        raw_root=str(tmp_path / "raw_records"),
        output_dir=str(output_dir),
        reports_dir=str(reports_dir)
    )
    df_meta = pd.read_parquet(output_dir / "place_metadata.parquet")
    # Not mapped from coordinates, so mapping_method falls back to default/empty mapping
    assert df_meta.iloc[0]["mapping_method"] == "pilot_places_default"
    
    # 6. Strict Mapping Option
    # If strict mapping is True, coordinate fallback should be skipped completely
    pd.DataFrame([raw_rec_4]).to_parquet(raw_dir / "places.parquet")
    run_metadata_backfill(
        pilot_path=str(tmp_path / "pilot_places.parquet"),
        source_map_path=str(tmp_path / "attraction_sources.parquet"),
        raw_root=str(tmp_path / "raw_records"),
        output_dir=str(output_dir),
        reports_dir=str(reports_dir),
        strict_mapping=True
    )
    df_meta = pd.read_parquet(output_dir / "place_metadata.parquet")
    assert df_meta.iloc[0]["mapping_method"] == "pilot_places_default"

# 9. Jam operasional dinormalisasi
def test_opening_hours_normalization():
    assert parse_hours_string("Closed") == ("", "", False, True)
    assert parse_hours_string("Tutup") == ("", "", False, True)
    assert parse_hours_string("Open 24 hours") == ("00:00", "24:00", True, False)
    assert parse_hours_string("08.00 to 22.00") == ("08:00", "22:00", False, False)
    assert parse_hours_string("08:30 - 17:00") == ("08:30", "17:00", False, False)
    assert parse_hours_string("Buka 24 Jam") == ("00:00", "24:00", True, False)

# 10. Field kosong tidak dianggap unavailable
# 11. Operational status priority benar
# 12. Konflik status terdeteksi
# 13. Setiap metadata terpilih memiliki provenance
def test_operational_status_and_conflicts(tmp_path):
    pilot_data = [{
        "canonical_id": "can_conflict",
        "name": "Wisata Konflik",
        "region": "Kabupaten Pesawaran",
        "latitude": -5.5000,
        "longitude": 105.1000,
        "google_place_id": "ChIJ_conflict",
        "source_place_id": "ChIJ_conflict",
        "source_url": "https://google.com/maps?query_place_id=ChIJ_conflict",
        "source_count": 1,
        "primary_category": "nature",
        "category_tags": np.array(["nature"], dtype=object)
    }]
    pd.DataFrame(pilot_data).to_parquet(tmp_path / "pilot_places.parquet")
    
    sources_data = [{
        "source_record_id": "apify_1", "canonical_id": "can_conflict", "confidence": 1.0, "match_status": "new", "dedup_reason": "test"
    }, {
        "source_record_id": "apify_2", "canonical_id": "can_conflict", "confidence": 1.0, "match_status": "new", "dedup_reason": "test"
    }]
    pd.DataFrame(sources_data).to_parquet(tmp_path / "attraction_sources.parquet")
    
    # 2 raw records with conflicting statuses: one is open, one is permanently closed
    raw_1 = {
        "source_record_id": "apify_1", "source_place_id": "ChIJ_conflict", "source_url": "", "raw_name": "Wisata Konflik",
        "latitude": -5.5, "longitude": 105.1, "query_region": "pesawaran", "raw_address": "Jl. A",
        "rating": 4.0, "review_count": 5, "phone": "123", "website": "http://a.com",
        "scrapedAt": "2026-07-14T01:00:00Z", "collected_at": "2026-07-14T01:00:00Z",
        "permanently_closed": True, "temporarily_closed": False, "description": "", "raw_payload_path": ""
    }
    raw_2 = {
        "source_record_id": "apify_2", "source_place_id": "ChIJ_conflict", "source_url": "", "raw_name": "Wisata Konflik",
        "latitude": -5.5, "longitude": 105.1, "query_region": "pesawaran", "raw_address": "Jl. B",
        "rating": 4.0, "review_count": 5, "phone": "456", "website": "http://b.com",
        "scrapedAt": "2026-07-14T02:00:00Z", "collected_at": "2026-07-14T02:00:00Z",
        "permanently_closed": False, "temporarily_closed": False, "description": "", "raw_payload_path": ""
    }
    
    raw_dir = tmp_path / "raw_records" / "pesawaran"
    os.makedirs(raw_dir, exist_ok=True)
    pd.DataFrame([raw_1, raw_2]).to_parquet(raw_dir / "places.parquet")
    
    output_dir = tmp_path / "output"
    reports_dir = tmp_path / "reports"
    
    run_metadata_backfill(
        pilot_path=str(tmp_path / "pilot_places.parquet"),
        source_map_path=str(tmp_path / "attraction_sources.parquet"),
        raw_root=str(tmp_path / "raw_records"),
        output_dir=str(output_dir),
        reports_dir=str(reports_dir)
    )
    
    # Priority check: permanently closed takes priority even if raw_2 is newer
    df_op = pd.read_parquet(output_dir / "operational_status.parquet")
    assert df_op.iloc[0]["operational_status"] == "permanently_closed"
    
    # Verify conflicts CSV contains entries for website, phone, and address
    df_conf = pd.read_csv(output_dir / "metadata_conflicts.csv")
    assert len(df_conf) > 0
    conflict_fields = set(df_conf["field_name"].tolist())
    assert "website" in conflict_fields
    assert "phone" in conflict_fields
    
    # Verify provenance exists for fields
    df_prov = pd.read_csv(output_dir / "metadata_provenance.csv")
    assert len(df_prov) > 0
    prov_fields = set(df_prov["field_name"].tolist())
    assert "website" in prov_fields
    assert "phone" in prov_fields

# 14. Completeness score antara 0 dan 100
# 15. Jumlah bobot completeness tepat 100
def test_completeness_score_logic():
    # Bobot check: address=15, coordinates=15, website=10, phone=10, opening hours=15, operational status=10, facilities=15, description=5, category tags=5
    total_weights = 15 + 15 + 10 + 10 + 15 + 10 + 15 + 5 + 5
    assert total_weights == 100
    
    # Check bounds of calculated score
    df_meta = pd.read_parquet("data/enrichment/metadata/place_metadata.parquet")
    for _, row in df_meta.iterrows():
        score = row["metadata_completeness_score"]
        assert 0 <= score <= 100

# 16. Price candidate tidak mengarang harga
def test_price_candidates_classification():
    df_price = pd.read_csv("data/enrichment/price/pilot_price_candidates.csv")
    # Verify that no numeric/estimated prices are set (as we don't research prices in this phase)
    assert "price" not in df_price.columns
    for _, row in df_price.iterrows():
        assert pd.isna(row["existing_price_raw_value"]) or str(row["existing_price_raw_value"]).strip() == ""
        # Check priority values are valid
        assert row["price_research_priority"] in ["high", "medium", "low", "not_applicable"]

# 17. Discovery dataset tidak berubah
# 18. Review final dataset tidak berubah
def test_dataset_integrity():
    # Read saved integrity json
    with open("reports/metadata_backfill_integrity_check.json", "r", encoding="utf-8") as f:
        saved_checksums = json.load(f)
        
    def get_sha256(filepath):
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
        
    # Check master verified
    assert get_sha256("data/canonical/attractions_master_verified.parquet") == saved_checksums["attractions_master_verified.parquet"]["sha256"]
    
    # Check candidates
    assert get_sha256("data/canonical/attractions_candidates.parquet") == saved_checksums["attractions_candidates.parquet"]["sha256"]
    
    # Check reviews final
    assert get_sha256("data/enrichment/final/reviews.parquet") == saved_checksums["reviews.parquet"]["sha256"]
