import uuid
import math
import logging
import os
import csv
from typing import List, Tuple, Dict, Any, Optional
from urllib.parse import urlparse
from rapidfuzz import fuzz
from src.models.schemas import NormalizedAttractionRecord, CanonicalAttractionRecord
from datetime import datetime, timezone
from src.pipeline.normalize import map_canonical_categories

logger = logging.getLogger("scraper.pipeline.deduplicate")

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on the earth in meters.
    """
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return float('inf')
        
    R = 6371000.0  # Earth radius in meters
    
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

def calculate_match_confidence(rec1: NormalizedAttractionRecord, rec2: NormalizedAttractionRecord) -> Tuple[float, bool, str]:
    """
    Compares two records and returns a confidence score, match status, and match reason.
    """
    is_g1 = rec1.source in ["google_places", "apify_google_maps"]
    is_g2 = rec2.source in ["google_places", "apify_google_maps"]
    
    # 1. Block different Google place IDs from being merged
    if is_g1 and is_g2 and rec1.source_place_id != rec2.source_place_id:
        return 0.0, False, "different_google_place_ids"
        
    # 2. Match exact Google place ID across different crawler formats
    if is_g1 and is_g2 and rec1.source_place_id == rec2.source_place_id:
        return 1.0, True, "same_google_place_id"

    # 3. Exact ID match (same source and source_place_id)
    if rec1.source == rec2.source and rec1.source_place_id == rec2.source_place_id:
        return 1.0, True, "same_source_id"

    # 4. Same phone match (must not be empty/invalid)
    if rec1.phone and rec2.phone and rec1.phone.strip() and rec1.phone == rec2.phone:
        return 0.95, True, "same_phone"

    # 5. Same website match (must not be empty/invalid)
    if rec1.website and rec2.website and rec1.website.strip() and rec1.website == rec2.website:
        domain1 = urlparse(rec1.website).netloc
        domain2 = urlparse(rec2.website).netloc
        if domain1 == domain2 and domain1 not in ["instagram.com", "facebook.com", "maps.google.com", "google.com", ""]:
            return 0.95, True, "same_website"

    name1 = rec1.normalized_name
    name2 = rec2.normalized_name
    
    fuzzy_score = fuzz.token_sort_ratio(name1, name2)
    has_coords = rec1.latitude is not None and rec1.longitude is not None and rec2.latitude is not None and rec2.longitude is not None
    dist = haversine_distance(rec1.latitude, rec1.longitude, rec2.latitude, rec2.longitude) if has_coords else float('inf')

    if has_coords:
        # Check exact name match + distance <= 500m
        if name1 == name2 and dist <= 500:
            return 1.0, True, "exact_name_distance_500m"
            
        # Check fuzzy name >= 90 + distance <= 300m
        # Skip if they represent a likely parent-child relationship (e.g. one name is part of another)
        if fuzzy_score >= 90 and dist <= 300:
            is_sub = (name1 in name2 or name2 in name1)
            if name1 != name2 and (is_sub or fuzzy_score < 95):
                return 0.0, False, "potential_parent_child"
            return 0.9, True, "fuzzy_name_distance_300m"

        # Check address similarity >= 85 + distance <= 500m
        if rec1.address and rec2.address:
            addr_score = fuzz.token_sort_ratio(rec1.address.lower(), rec2.address.lower())
            if addr_score >= 85 and dist <= 500:
                return 0.85, True, "similar_address_distance_500m"

    return 0.0, False, "no_match"

def merge_records(canonical: CanonicalAttractionRecord, record: NormalizedAttractionRecord, confidence: float) -> CanonicalAttractionRecord:
    """
    Updates canonical record fields using information from the new matching record.
    """
    canonical.source_count += 1
    canonical.dedup_confidence = min(canonical.dedup_confidence, confidence)
    
    if confidence < 0.85 or record.classification == "manual_review":
        canonical.needs_manual_review = True
        
    # Merge coordinates if missing
    if canonical.latitude is None or canonical.longitude is None:
        canonical.latitude = record.latitude
        canonical.longitude = record.longitude
        
    # Merge address and regional info
    if not canonical.address and record.address:
        canonical.address = record.address
    if not canonical.city_regency and record.city_regency:
        canonical.city_regency = record.city_regency
    if not canonical.district and record.district:
        canonical.district = record.district
    if not canonical.village and record.village:
        canonical.village = record.village

    # Merge contact & website info
    if not canonical.phone and record.phone:
        canonical.phone = record.phone
    if not canonical.website and record.website:
        canonical.website = record.website
        
    # Merge opening hours
    if not canonical.opening_hours and record.opening_hours:
        canonical.opening_hours = record.opening_hours
        
    # Merge categories
    for cat in record.categories:
        if cat not in canonical.category_tags:
            canonical.category_tags.append(cat)
            
    primary_cat, tags = map_canonical_categories(canonical.name, canonical.category_tags)
    canonical.normalized_category = primary_cat
    canonical.category_tags = tags
    
    # Merge ratings and review counts
    if record.rating is not None:
        if canonical.rating is None:
            canonical.rating = record.rating
            canonical.review_count = record.review_count
        else:
            c_reviews = canonical.review_count or 0
            r_reviews = record.review_count or 0
            if c_reviews + r_reviews > 0:
                canonical.rating = round(((canonical.rating * c_reviews) + (record.rating * r_reviews)) / (c_reviews + r_reviews), 2)
                canonical.review_count = c_reviews + r_reviews
            else:
                canonical.rating = round((canonical.rating + record.rating) / 2, 2)
                
    # Update timeline
    canonical.last_collected_at = max(canonical.last_collected_at, record.collected_at)
    
    # Merge classification details
    if record.classification:
        if canonical.classification != "accepted":
            # Upgrade classification if we merge with accepted record
            canonical.classification = record.classification
            canonical.classification_reason = record.classification_reason
            canonical.classification_confidence = record.classification_confidence
            canonical.classification_signals = record.classification_signals
            
    # Facilities merge
    for f in record.facilities:
        if f not in canonical.facilities:
            canonical.facilities.append(f)
            
    return canonical

def is_forbidden_parent_child(name: str) -> bool:
    n_clean = name.lower()
    forbidden = [
        "biro", "travel", "tour", "agent", "trip", "sewa", "rent", 
        "pelabuhan", "bakauheni",
        "desa", "kecamatan", "kabupaten", "provinsi", "pekon", "kelurahan",
        "kota", "posko", "sekretariat", "pam terbengkalai", "terbengkalai"
    ]
    return any(w in n_clean for w in forbidden)

def get_facility_type(name: str) -> Optional[str]:
    n_clean = name.lower()
    if any(w in n_clean for w in ["parkiran", "parkir", "parking"]):
        return "parking"
    if any(w in n_clean for w in ["gapura", "gerbang", "pintu masuk", "entrance"]):
        return "gate"
    if any(w in n_clean for w in ["transportasi", "sewa motor", "sewa mobil", "rental", "ojek", "travel", "biro", "tour operator", "tour"]):
        return "transportation"
    if any(w in n_clean for w in ["kantor", "office", "posko", "sekretariat", "pam terbengkalai", "terbengkalai"]):
        return "office"
    if any(w in n_clean for w in ["dermaga", "pelabuhan"]):
        return "dock"
    return None

def deduplicate_records(records: List[NormalizedAttractionRecord]) -> Tuple[List[CanonicalAttractionRecord], List[Dict]]:
    """
    Deduplicates normalized attraction records, establishes parent-child relationships,
    and returns canonical attractions list and mapping dicts.
    """
    # 1. Hapus duplikasi source_record_id sebelum clustering
    seen_source_ids = set()
    unique_records = []
    for r in records:
        if r.source_record_id not in seen_source_ids:
            seen_source_ids.add(r.source_record_id)
            unique_records.append(r)
            
    logger.info(f"Filtered out {len(records) - len(unique_records)} duplicate source_record_ids before clustering.")
    
    canonical_list: List[CanonicalAttractionRecord] = []
    mapping_list: List[Dict] = []
    
    # Priority for canonical anchor creation
    source_priority = {"google_places": 0, "apify_google_maps": 0, "osm": 1, "official_sites": 2}
    sorted_records = sorted(unique_records, key=lambda x: source_priority.get(x.source, 9))
    
    for record in sorted_records:
        matched_canonical = None
        best_confidence = 0.0
        match_reason = "new_record"
        
        # Check against existing canonical entries
        for canonical in canonical_list:
            canonical_normalized = NormalizedAttractionRecord(
                source_record_id=canonical.canonical_id,
                source=canonical.primary_source,
                source_place_id=canonical.canonical_id,
                name=canonical.name,
                normalized_name=canonical.normalized_name,
                address=canonical.address,
                city_regency=canonical.city_regency,
                district=canonical.district,
                village=canonical.village,
                latitude=canonical.latitude,
                longitude=canonical.longitude,
                categories=canonical.category_tags,
                phone=canonical.phone,
                website=canonical.website,
                collected_at=canonical.last_collected_at,
                classification=canonical.classification,
                classification_reason=canonical.classification_reason,
                classification_confidence=canonical.classification_confidence,
                classification_signals=canonical.classification_signals
            )
            
            confidence, is_match, reason = calculate_match_confidence(record, canonical_normalized)
            if is_match and confidence > best_confidence:
                matched_canonical = canonical
                best_confidence = confidence
                match_reason = reason
                
        if matched_canonical:
            merge_records(matched_canonical, record, best_confidence)
            
            # Save mapping info on the record itself
            record.dedup_cluster_id = matched_canonical.canonical_id
            record.dedup_reason = match_reason
            
            mapping_list.append({
                "source_record_id": record.source_record_id,
                "canonical_id": matched_canonical.canonical_id,
                "confidence": best_confidence,
                "match_status": "merged",
                "dedup_reason": match_reason
            })
        else:
            canonical_id = f"can_{uuid.uuid4().hex[:12]}"
            
            primary_cat, tags = map_canonical_categories(record.name, record.categories)
            
            # Mark mapping info on the record itself
            record.dedup_cluster_id = canonical_id
            record.dedup_reason = "new_record"
            
            new_canonical = CanonicalAttractionRecord(
                canonical_id=canonical_id,
                name=record.name,
                normalized_name=record.normalized_name,
                description=None,
                normalized_category=primary_cat,
                category_tags=tags,
                address=record.address,
                city_regency=record.city_regency,
                district=record.district,
                village=record.village,
                latitude=record.latitude,
                longitude=record.longitude,
                rating=record.rating,
                review_count=record.review_count,
                price_min=record.price_min,
                price_max=record.price_max,
                currency=record.currency,
                price_notes=record.price_notes,
                opening_hours=record.opening_hours,
                phone=record.phone,
                website=record.website,
                business_status=record.business_status or "OPERATIONAL",
                facilities=record.facilities,
                primary_source=record.source,
                source_count=1,
                first_collected_at=record.collected_at,
                last_collected_at=record.collected_at,
                last_verified_at=datetime.now(timezone.utc).isoformat(),
                dedup_confidence=1.0,
                needs_manual_review=(record.classification == "manual_review"),
                classification=record.classification,
                classification_confidence=record.classification_confidence,
                classification_signals=record.classification_signals,
                classification_reason=record.classification_reason,
                dedup_cluster_id=canonical_id,
                dedup_reason="canonical_root"
            )
            canonical_list.append(new_canonical)
            mapping_list.append({
                "source_record_id": record.source_record_id,
                "canonical_id": canonical_id,
                "confidence": 1.0,
                "match_status": "new",
                "dedup_reason": "new_record"
            })
            
    # Post-process parent-child relationships
    # Strict matching constraints: Strong distance, name boundary match, category/facilities signals
    for i in range(len(canonical_list)):
        for j in range(len(canonical_list)):
            if i == j:
                continue
            rec1 = canonical_list[i]
            rec2 = canonical_list[j]
            
            if rec1.latitude is None or rec1.longitude is None or rec2.latitude is None or rec2.longitude is None:
                continue
                
            dist = haversine_distance(rec1.latitude, rec1.longitude, rec2.latitude, rec2.longitude)
            if dist <= 300:
                n1 = rec1.normalized_name
                n2 = rec2.normalized_name
                
                if n1 == n2:
                    continue
                    
                # 2. Parent-child wajib berada di region administratif yang sama (kabupaten/kota)
                c1 = (rec1.city_regency or "").lower().strip()
                c2 = (rec2.city_regency or "").lower().strip()
                if c1 and c2 and c1 != c2:
                    continue
                
                # Exclude generic administrative keywords
                if is_forbidden_parent_child(rec1.name) or is_forbidden_parent_child(rec2.name):
                    continue
                
                # Check for whole-word containment (e.g. "lembah hijau" inside "waterpark lembah hijau")
                w1 = f" {n1} "
                w2 = f" {n2} "
                is_word_sub = (w1 in w2 or w2 in w1)
                
                fuzzy_score = fuzz.token_sort_ratio(n1, n2)
                
                # Parent-child relation criteria
                if is_word_sub or (fuzzy_score >= 80 and fuzzy_score < 90):
                    if len(n1) < len(n2):
                        parent = rec1
                        child = rec2
                    else:
                        parent = rec2
                        child = rec1
                        
                    # 3. Type compatibility: check child category type
                    facility_type = get_facility_type(child.name)
                    if facility_type is not None:
                        # Simpan sebagai supporting_facility
                        if child.parent_canonical_id is None:
                            child.parent_canonical_id = parent.canonical_id
                            child.place_relationship = "supporting_facility"
                            child.needs_manual_review = True
                            if parent.place_relationship is None:
                                parent.place_relationship = "same_place"
                    else:
                        # Standard child attraction
                        if child.parent_canonical_id is None:
                            child.parent_canonical_id = parent.canonical_id
                            child.place_relationship = "part_of"
                            child.needs_manual_review = True
                            if parent.place_relationship is None:
                                parent.place_relationship = "same_place"
                                
    # 5. Get constituent Google place IDs for possible duplicate finder
    canonical_to_place_ids = {}
    for mapping in mapping_list:
        cid = mapping["canonical_id"]
        sid = mapping["source_record_id"]
        for record in unique_records:
            if record.source_record_id == sid:
                if record.source in ["google_places", "apify_google_maps"] and record.source_place_id:
                    if cid not in canonical_to_place_ids:
                        canonical_to_place_ids[cid] = []
                    canonical_to_place_ids[cid].append(record.source_place_id)

    # Find possible duplicate candidates (different Google place IDs, similar names, distance <= 100m)
    possible_duplicates = []
    for i in range(len(canonical_list)):
        for j in range(i + 1, len(canonical_list)):
            rec1 = canonical_list[i]
            rec2 = canonical_list[j]
            
            pids1 = canonical_to_place_ids.get(rec1.canonical_id, [])
            pids2 = canonical_to_place_ids.get(rec2.canonical_id, [])
            
            if pids1 and pids2:
                if not set(pids1).intersection(set(pids2)):
                    fuzzy_score = fuzz.token_sort_ratio(rec1.normalized_name, rec2.normalized_name)
                    if fuzzy_score >= 85:
                        dist = haversine_distance(rec1.latitude, rec1.longitude, rec2.latitude, rec2.longitude)
                        if dist <= 100:
                            c1 = rec1.normalized_category
                            c2 = rec2.normalized_category
                            if c1 == c2 or c1 in ["other", None] or c2 in ["other", None]:
                                possible_duplicates.append({
                                    "canonical_id_1": rec1.canonical_id,
                                    "name_1": rec1.name,
                                    "place_id_1": pids1[0],
                                    "canonical_id_2": rec2.canonical_id,
                                    "name_2": rec2.name,
                                    "place_id_2": pids2[0],
                                    "distance_meters": round(dist, 1),
                                    "fuzzy_score": round(fuzzy_score, 1)
                                })
                                
    # Write reports/possible_duplicate_candidates.csv (use test filename in pytest)
    reports_dir = "reports"
    os.makedirs(reports_dir, exist_ok=True)
    csv_filename = "test_possible_duplicate_candidates.csv" if "PYTEST_CURRENT_TEST" in os.environ else "possible_duplicate_candidates.csv"
    csv_path = os.path.join(reports_dir, csv_filename)
    try:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "canonical_id_1", "name_1", "place_id_1",
                "canonical_id_2", "name_2", "place_id_2",
                "distance_meters", "fuzzy_score"
            ])
            writer.writeheader()
            writer.writerows(possible_duplicates)
        logger.info(f"Saved {len(possible_duplicates)} possible duplicate candidates to {csv_path}")
    except Exception as e:
        logger.error(f"Failed to write possible duplicates to CSV: {e}")
                            
    return canonical_list, mapping_list
