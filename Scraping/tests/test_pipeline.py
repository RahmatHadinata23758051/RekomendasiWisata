import pytest
import os
import json
import tempfile
import shutil
from src.pipeline.normalize import (
    normalize_name_for_matching,
    parse_indonesian_price,
    parse_coordinate,
    is_within_lampung,
    normalize_record
)
from src.pipeline.deduplicate import haversine_distance, calculate_match_confidence, deduplicate_records
from src.models.schemas import RawAttractionRecord, NormalizedAttractionRecord
from src.storage.writer import save_dataset

# 1. Normalisasi nama tempat
def test_normalize_name():
    assert normalize_name_for_matching("Pantai Mutun") == "mutun"
    assert normalize_name_for_matching("Objek Wisata Pantai Mutun Lampung") == "mutun"
    assert normalize_name_for_matching("Mutun Beach") == "mutun"
    assert normalize_name_for_matching("Air Terjun Curup Tujuh") == "tujuh"

# 2. Normalisasi harga Indonesia
def test_normalize_price():
    assert parse_indonesian_price("Rp 15.000") == 15000.0
    assert parse_indonesian_price("Rp. 20.000,00") == 20000.0
    assert parse_indonesian_price("Rp10k") == 10000.0
    assert parse_indonesian_price("Gratis") == 0.0
    assert parse_indonesian_price("Free entry") == 0.0

# 3. Parsing koordinat
def test_parse_coordinate():
    assert parse_coordinate("-5.3971") == -5.3971
    assert parse_coordinate(105.2663) == 105.2663
    assert parse_coordinate("invalid") is None

# 4. Validasi koordinat Lampung
def test_validate_lampung_bounds():
    # Inside Lampung
    assert is_within_lampung(-5.4, 105.2) is True
    # Outside Lampung (Jakarta / alternative region)
    assert is_within_lampung(-6.2, 106.8) is False # outside broad box (longitude 106.8 > 106.5)
    # Far away (Bali)
    assert is_within_lampung(-8.4, 115.1) is False

# 5. Deduplication nama yang mirip & tempat berjauhan
def test_deduplication_matching():
    # Similar name, close distance -> MATCH
    rec1 = NormalizedAttractionRecord(
        source_record_id="src_1", source="osm", source_place_id="1",
        name="Pantai Mutun", normalized_name="mutun",
        latitude=-5.601, longitude=105.250, collected_at="2026-07-13"
    )
    rec2 = NormalizedAttractionRecord(
        source_record_id="src_2", source="google_places", source_place_id="2",
        name="Mutun Beach", normalized_name="mutun",
        latitude=-5.602, longitude=105.251, collected_at="2026-07-13"
    )
    
    dist = haversine_distance(rec1.latitude, rec1.longitude, rec2.latitude, rec2.longitude)
    assert dist <= 300
    
    conf, is_match, reason = calculate_match_confidence(rec1, rec2)
    assert is_match is True
    assert conf >= 0.9

    # Same name, far apart -> NO MATCH
    rec3 = NormalizedAttractionRecord(
        source_record_id="src_3", source="osm", source_place_id="3",
        name="Pantai Mutun", normalized_name="mutun",
        latitude=-5.601, longitude=105.250, collected_at="2026-07-13"
    )
    rec4 = NormalizedAttractionRecord(
        source_record_id="src_4", source="google_places", source_place_id="4",
        name="Pantai Mutun", normalized_name="mutun",
        latitude=-5.100, longitude=104.500, collected_at="2026-07-13"
    )
    
    conf_far, is_match_far, reason_far = calculate_match_confidence(rec3, rec4)
    assert is_match_far is False

# 6. Parser OSM node, way, relation
def test_osm_parsing_mapping():
    # Simulating raw OSM responses parsed into RawAttractionRecord
    raw_node = RawAttractionRecord(
        source_record_id="osm_node_123",
        source="osm",
        source_place_id="node/123",
        raw_name="Pantai Gigi Hiu",
        latitude=-5.750,
        longitude=104.600,
        collected_at="2026-07-13T00:00:00Z"
    )
    
    norm = normalize_record(raw_node)
    assert norm.name == "Pantai Gigi Hiu"
    assert norm.normalized_name == "gigi hiu"
    assert norm.latitude == -5.750
    assert norm.longitude == 104.600

# 7. Storage saving
def test_save_dataset():
    temp_dir = tempfile.mkdtemp()
    records = [
        {"id": "1", "name": "Place A", "coords": [1.0, 2.0]},
        {"id": "2", "name": "Place B", "coords": [3.0, 4.0]}
    ]
    try:
        res = save_dataset(records, temp_dir, "test_file")
        assert os.path.exists(res["csv"])
        assert os.path.exists(res["jsonl"])
        assert os.path.exists(res["parquet"])
        
        # Verify loading works
        import pandas as pd
        df = pd.read_parquet(res["parquet"])
        assert len(df) == 2
        assert df.iloc[0]["name"] == "Place A"
    finally:
        shutil.rmtree(temp_dir)
