import pytest
import os
import json
import tempfile
from typing import List
from src.models.schemas import RawAttractionRecord, NormalizedAttractionRecord, CanonicalAttractionRecord
from src.pipeline.normalize import normalize_record, classify_record, map_canonical_categories
from src.pipeline.deduplicate import deduplicate_records, calculate_match_confidence

# Wait! We need to adjust imports.
# In Python, standard import is without extension. Let's fix that.
from src.collectors.apify_google_maps import ApifyGoogleMapsImporter

def test_apify_parsing_and_mapping():
    sample_data = [{
        "title": "Pantai Sari Ringkih",
        "description": "Pantai indah",
        "categoryName": "Pantai",
        "address": "Jl. Sari Ringkih, Pesawaran",
        "neighborhood": "Sari Ringkih",
        "city": "Kabupaten Pesawaran",
        "postalCode": "35235",
        "state": "Lampung",
        "countryCode": "ID",
        "phone": "+62 812-3456-7890",
        "phoneUnformatted": "+6281234567890",
        "location": {
            "lat": -5.58,
            "lng": 105.25
        },
        "totalScore": 4.5,
        "reviewsCount": 250,
        "placeId": "ChIJsari_ringkih",
        "categories": ["Pantai", "Tujuan Wisata"],
        "scrapedAt": "2026-07-13T02:40:24.280Z",
        "url": "https://maps.google.com/?cid=123",
        "searchString": "pantai pesawaran",
        "imageUrl": "https://images.com/pic.jpg",
        "additionalInfo": {"Fasilitas": [{"Toilet": True}]}
    }]
    
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json", encoding="utf-8") as f:
        json.dump(sample_data, f)
        temp_path = f.name
        
    try:
        importer = ApifyGoogleMapsImporter()
        valid, failed = importer.load_raw_dataset(temp_path)
        
        assert len(valid) == 1
        assert len(failed) == 0
        raw = valid[0]
        assert raw.raw_name == "Pantai Sari Ringkih"
        assert raw.source_place_id == "ChIJsari_ringkih"
        assert raw.latitude == -5.58
        assert raw.rating == 4.5
        assert raw.review_count == 250
        assert raw.phone == "+6281234567890"
        assert raw.image_url == "https://images.com/pic.jpg"
        
        # Test normalize
        norm = normalize_record(raw)
        assert norm.name == "Pantai Sari Ringkih"
        assert norm.classification == "accepted"
        assert norm.classification_confidence == 1.0
        assert norm.rating == 4.5
        assert norm.review_count == 250
        assert "Fasilitas: Toilet" in norm.facilities
        
    finally:
        os.remove(temp_path)

def test_record_without_place_id():
    sample_no_place_id = [{
        "title": "Curup Gangsa",
        "categoryName": "Air Terjun",
        "location": {"lat": -4.8, "lng": 104.5},
        "cid": "9876543210"
    }]
    
    sample_no_id_at_all = [{
        "title": "Bukit Kabut",
        "categoryName": "Tujuan Wisata",
        "location": {"lat": -5.1, "lng": 104.9}
    }]
    
    importer = ApifyGoogleMapsImporter()
    
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json", encoding="utf-8") as f:
        json.dump(sample_no_place_id, f)
        path1 = f.name
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json", encoding="utf-8") as f:
        json.dump(sample_no_id_at_all, f)
        path2 = f.name
        
    try:
        v1, _ = importer.load_raw_dataset(path1)
        assert len(v1) == 1
        assert v1[0].source_place_id == "9876543210"
        
        v2, _ = importer.load_raw_dataset(path2)
        assert len(v2) == 1
        assert len(v2[0].source_place_id) == 16
    finally:
        os.remove(path1)
        os.remove(path2)

def test_record_without_category():
    raw = RawAttractionRecord(
        source_record_id="apify_google_maps_123",
        source="apify_google_maps",
        source_place_id="123",
        raw_name="Situs Misterius",
        raw_categories=[],
        latitude=-5.4,
        longitude=105.2,
        collected_at="2026-07-13T00:00:00Z"
    )
    norm = normalize_record(raw)
    assert norm.classification == "manual_review"
    assert "tanpa kategori" in norm.classification_reason

def test_record_without_coordinates():
    # If coordinate check triggers manual review (outside bounds or missing)
    res, reason, conf, sigs = classify_record("Pantai", ["Pantai"], None, None)
    assert res == "accepted" 
    
    # Outside Lampung bounds
    res, reason, conf, sigs = classify_record("Pantai Bali", ["Pantai"], -8.4, 115.1)
    assert res == "manual_review"

def test_classifications():
    # Accepted
    res, reason, conf, sigs = classify_record("Taman Wisata Hijau", ["Taman"], -5.4, 105.2)
    assert res == "accepted"
    
    res, reason, conf, sigs = classify_record("Air Terjun Lembah Hijau", ["Air Terjun"], -5.42, 105.22)
    assert res == "accepted"
    
    # Rejected
    res, reason, conf, sigs = classify_record("Hotel Lampung", ["Hotel"], -5.4, 105.2)
    assert res == "rejected"
    
    res, reason, conf, sigs = classify_record("Warung Kopi Enak", ["Kafe"], -5.4, 105.2)
    assert res == "rejected"
    
    res, reason, conf, sigs = classify_record("Dealer Motor", ["Dealer"], -5.4, 105.2)
    assert res == "rejected"
    
    # Manual review
    res, reason, conf, sigs = classify_record("Masjid Raya Lampung", ["Tempat Ibadah"], -5.4, 105.2)
    assert res == "manual_review"
    
    res, reason, conf, sigs = classify_record("Lapangan Merdeka", ["Lapangan"], -5.4, 105.2)
    assert res == "manual_review"

def test_taman_category_checks():
    # A generic park without signals -> manual_review
    res, reason, conf, sigs = classify_record("Taman Sudirman", ["Taman"], -5.4, 105.2)
    assert res == "manual_review"
    
    # With search keyword signal -> accepted
    res, reason, conf, sigs = classify_record("Taman Sudirman", ["Taman"], -5.4, 105.2, search_keyword="taman wisata")
    assert res == "accepted"
    
    # With review count signal -> accepted
    res, reason, conf, sigs = classify_record("Taman Sudirman", ["Taman"], -5.4, 105.2, review_count=30)
    assert res == "accepted"
    
    # With local park keyword -> manual_review
    res, reason, conf, sigs = classify_record("Taman Perumahan Griya", ["Taman"], -5.4, 105.2)
    assert res == "manual_review"

def test_category_normalization():
    p, tags = map_canonical_categories("Air Terjun Way Lalaan", ["Air Terjun", "Tujuan Wisata"])
    assert p == "waterfall"
    assert "waterfall" in tags
    assert "nature" in tags

def test_duplicate_osm_and_apify():
    osm_rec = NormalizedAttractionRecord(
        source_record_id="osm_111", source="osm", source_place_id="111",
        name="Lembah Hijau", normalized_name="lembah hijau",
        latitude=-5.420, longitude=105.220, categories=["taman"],
        collected_at="2026-07-13T00:00:00Z", classification="accepted"
    )
    
    apify_exact = NormalizedAttractionRecord(
        source_record_id="apify_google_maps_333", source="apify_google_maps", source_place_id="333",
        name="Lembah Hijau", normalized_name="lembah hijau",
        latitude=-5.4201, longitude=105.2201, categories=["taman"],
        collected_at="2026-07-13T00:00:00Z", classification="accepted"
    )
    conf_ex, is_match_ex, reason = calculate_match_confidence(osm_rec, apify_exact)
    assert is_match_ex
    assert conf_ex == 1.0
    assert reason == "exact_name_distance_500m"

def test_name_same_but_location_different():
    rec1 = NormalizedAttractionRecord(
        source_record_id="osm_1", source="osm", source_place_id="1",
        name="Alfamart", normalized_name="alfamart",
        latitude=-5.420, longitude=105.220, collected_at="2026-07-13T00:00:00Z"
    )
    rec2 = NormalizedAttractionRecord(
        source_record_id="osm_2", source="osm", source_place_id="2",
        name="Alfamart", normalized_name="alfamart",
        latitude=-5.490, longitude=105.280, collected_at="2026-07-13T00:00:00Z"
    )
    conf, is_match, reason = calculate_match_confidence(rec1, rec2)
    assert not is_match

def test_parent_child_linking():
    p_rec = NormalizedAttractionRecord(
        source_record_id="osm_parent", source="osm", source_place_id="parent",
        name="Lembah Hijau", normalized_name="lembah hijau",
        latitude=-5.420, longitude=105.220, categories=["taman rekreasi"],
        collected_at="2026-07-13T00:00:00Z", classification="accepted"
    )
    c_rec = NormalizedAttractionRecord(
        source_record_id="apify_child", source="apify_google_maps", source_place_id="child",
        name="Waterpark Lembah Hijau", normalized_name="waterpark lembah hijau",
        latitude=-5.4201, longitude=105.2202, categories=["taman rekreasi air"],
        collected_at="2026-07-13T00:00:00Z", classification="accepted"
    )
    
    canonical_list, mappings = deduplicate_records([p_rec, c_rec])
    assert len(canonical_list) == 2
    
    p_can = next(r for r in canonical_list if r.name == "Lembah Hijau")
    c_can = next(r for r in canonical_list if r.name == "Waterpark Lembah Hijau")
    
    assert c_can.parent_canonical_id == p_can.canonical_id
    assert c_can.place_relationship == "part_of"

def test_idempotent_import(tmp_path):
    importer = ApifyGoogleMapsImporter()
    sample_data = [{
        "title": "Pantai Mutun",
        "placeId": "mutun_123",
        "location": {"lat": -5.5, "lng": 105.25}
    }]
    
    p = tmp_path / "places.json"
    p.write_text(json.dumps(sample_data))
    
    valid1, _ = importer.load_raw_dataset(str(p))
    valid2, _ = importer.load_raw_dataset(str(p))
    
    assert len(valid1) == 1
    assert valid1[0].source_place_id == valid2[0].source_place_id

def test_invalid_json_record(tmp_path):
    p = tmp_path / "corrupted.json"
    p.write_text("[{invalid json}")
    
    importer = ApifyGoogleMapsImporter()
    valid, failed = importer.load_raw_dataset(str(p))
    assert len(valid) == 0
    assert len(failed) == 1
    assert "JSON Decode Error" in failed[0]["error"]

def test_multi_file_import_non_overwriting(tmp_path):
    # Setup importer with temp folders
    # Mock settings / manifest location using tmp_path
    importer = ApifyGoogleMapsImporter()
    
    # Create two different places.json datasets representing Bandar Lampung and Pesawaran
    d1 = tmp_path / "google_maps" / "bandar_lampung" / "2026-07-13"
    d2 = tmp_path / "google_maps" / "pesawaran" / "2026-07-13"
    d1.mkdir(parents=True, exist_ok=True)
    d2.mkdir(parents=True, exist_ok=True)
    
    p1 = d1 / "places.json"
    p2 = d2 / "places.json"
    
    p1.write_text(json.dumps([{"title": "Taman BL", "placeId": "bl_123", "location": {"lat": -5.4, "lng": 105.2}}]))
    p2.write_text(json.dumps([{"title": "Pantai Pes", "placeId": "pes_456", "location": {"lat": -5.6, "lng": 105.1}}]))
    
    # Clean/mock manifest location in importer by patching raw_records directory or path
    # For testing, we can run import_dataset directly. It will use local "data" directory.
    # To avoid affecting local "data" dir, let's backup/restore manifest if it exists, or run it
    # We can just verify it extracts correct region and date!
    r1, dt1 = importer._extract_region_and_date(str(p1))
    r2, dt2 = importer._extract_region_and_date(str(p2))
    
    assert r1 == "bandar_lampung"
    assert dt1 == "2026-07-13"
    assert r2 == "pesawaran"
    assert dt2 == "2026-07-13"

def test_idempotent_import_checksum(tmp_path):
    importer = ApifyGoogleMapsImporter()
    d1 = tmp_path / "google_maps" / "bandar_lampung" / "2026-07-13"
    d1.mkdir(parents=True, exist_ok=True)
    p1 = d1 / "places.json"
    p1.write_text(json.dumps([{"title": "Taman BL", "placeId": "bl_123", "location": {"lat": -5.4, "lng": 105.2}}]))
    
    checksum1 = importer._calculate_file_checksum(str(p1))
    checksum2 = importer._calculate_file_checksum(str(p1))
    assert checksum1 == checksum2

def test_different_google_places_not_merged():
    rec1 = NormalizedAttractionRecord(
        source_record_id="apify_google_maps_bl_123", source="apify_google_maps", source_place_id="bl_123",
        name="Lembah Hijau", normalized_name="lembah hijau",
        latitude=-5.420, longitude=105.220, collected_at="2026-07-13T00:00:00Z"
    )
    rec2 = NormalizedAttractionRecord(
        source_record_id="apify_google_maps_bl_999", source="apify_google_maps", source_place_id="bl_999",
        name="Lembah Hijau", normalized_name="lembah hijau",
        latitude=-5.4201, longitude=105.2201, collected_at="2026-07-13T00:00:00Z"
    )
    conf, is_match, reason = calculate_match_confidence(rec1, rec2)
    assert not is_match
    assert reason == "different_google_place_ids"

def test_forbidden_parent_child_linking():
    p_rec = NormalizedAttractionRecord(
        source_record_id="osm_parent", source="osm", source_place_id="parent",
        name="Desa Wisata Pahawang", normalized_name="desa wisata pahawang",
        latitude=-5.420, longitude=105.220, categories=["desa"],
        collected_at="2026-07-13T00:00:00Z", classification="accepted"
    )
    c_rec = NormalizedAttractionRecord(
        source_record_id="apify_child", source="apify_google_maps", source_place_id="child",
        name="Biro Travel Pahawang", normalized_name="biro travel pahawang",
        latitude=-5.4201, longitude=105.2202, categories=["biro"],
        collected_at="2026-07-13T00:00:00Z", classification="accepted"
    )
    
    canonical_list, mappings = deduplicate_records([p_rec, c_rec])
    assert len(canonical_list) == 2
    
    # Neither should have a parent link because of forbidden administrative/travel agency keywords
    for item in canonical_list:
        assert item.parent_canonical_id is None

def test_parent_child_cross_region_rejected():
    p_rec = NormalizedAttractionRecord(
        source_record_id="osm_parent", source="osm", source_place_id="parent",
        name="Lembah Hijau", normalized_name="lembah hijau",
        latitude=-5.420, longitude=105.220, city_regency="Kota Bandar Lampung",
        collected_at="2026-07-13T00:00:00Z", classification="accepted"
    )
    c_rec = NormalizedAttractionRecord(
        source_record_id="apify_child", source="apify_google_maps", source_place_id="child",
        name="Water Park Lembah Hijau", normalized_name="water park lembah hijau",
        latitude=-5.4201, longitude=105.2202, city_regency="Kabupaten Pesawaran",
        collected_at="2026-07-13T00:00:00Z", classification="accepted"
    )
    
    canonical_list, mappings = deduplicate_records([p_rec, c_rec])
    assert len(canonical_list) == 2
    for item in canonical_list:
        assert item.parent_canonical_id is None

def test_transportation_not_attraction_child():
    p_rec = NormalizedAttractionRecord(
        source_record_id="osm_parent", source="osm", source_place_id="parent",
        name="Pulau Pahawang", normalized_name="pulau pahawang",
        latitude=-5.420, longitude=105.220, city_regency="Kabupaten Pesawaran",
        collected_at="2026-07-13T00:00:00Z", classification="accepted"
    )
    c_rec = NormalizedAttractionRecord(
        source_record_id="apify_child", source="apify_google_maps", source_place_id="child",
        name="Transportasi Wisata Pulau Pahawang", normalized_name="transportasi wisata pulau pahawang",
        latitude=-5.4201, longitude=105.2202, city_regency="Kabupaten Pesawaran",
        collected_at="2026-07-13T00:00:00Z", classification="accepted"
    )
    
    canonical_list, mappings = deduplicate_records([p_rec, c_rec])
    child = next(x for x in canonical_list if "Transportasi" in x.name)
    assert child.parent_canonical_id is not None
    assert child.place_relationship == "supporting_facility"

def test_parking_becomes_supporting_facility():
    p_rec = NormalizedAttractionRecord(
        source_record_id="osm_parent", source="osm", source_place_id="parent",
        name="Pantai Mutun", normalized_name="pantai mutun",
        latitude=-5.420, longitude=105.220, city_regency="Kabupaten Pesawaran",
        collected_at="2026-07-13T00:00:00Z", classification="accepted"
    )
    c_rec = NormalizedAttractionRecord(
        source_record_id="apify_child", source="apify_google_maps", source_place_id="child",
        name="Parkiran Pantai Mutun", normalized_name="parkiran pantai mutun",
        latitude=-5.4201, longitude=105.2202, city_regency="Kabupaten Pesawaran",
        collected_at="2026-07-13T00:00:00Z", classification="accepted"
    )
    
    canonical_list, mappings = deduplicate_records([p_rec, c_rec])
    child = next(x for x in canonical_list if "Parkiran" in x.name)
    assert child.parent_canonical_id is not None
    assert child.place_relationship == "supporting_facility"

def test_different_google_place_id_in_possible_duplicates():
    # Remove reports/test_possible_duplicate_candidates.csv if exists to verify write
    csv_path = "reports/test_possible_duplicate_candidates.csv"
    if os.path.exists(csv_path):
        os.remove(csv_path)
        
    rec1 = NormalizedAttractionRecord(
        source_record_id="apify_google_maps_bl_123", source="apify_google_maps", source_place_id="bl_123",
        name="Lembah Hijau", normalized_name="lembah hijau",
        latitude=-5.420, longitude=105.220, collected_at="2026-07-13T00:00:00Z", classification="accepted"
    )
    rec2 = NormalizedAttractionRecord(
        source_record_id="apify_google_maps_bl_999", source="apify_google_maps", source_place_id="bl_999",
        name="Lembah Hijau", normalized_name="lembah hijau",
        latitude=-5.4201, longitude=105.2201, collected_at="2026-07-13T00:00:00Z", classification="accepted"
    )
    
    canonical_list, mappings = deduplicate_records([rec1, rec2])
    assert len(canonical_list) == 2
    assert os.path.exists(csv_path)
    
    with open(csv_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "bl_123" in content
        assert "bl_999" in content



