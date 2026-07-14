import os
import json
import re
import hashlib
import math
import difflib
import logging
import glob
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger("scraper.enrichment.metadata_backfill")

# Haversine distance formula
def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0  # meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0)**2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

# Fuzzy match ratio
def fuzzy_match_ratio(name1: str, name2: str) -> float:
    if not name1 or not name2:
        return 0.0
    return difflib.SequenceMatcher(None, name1.lower().strip(), name2.lower().strip()).ratio()

# Normalize URL
def normalize_url(url: Any) -> str:
    if not url or pd.isna(url):
        return ""
    u = str(url).strip().lower()
    # Remove protocol
    u = re.sub(r"^https?://(www\.)?", "", u)
    # Remove trailing slash
    u = u.rstrip("/")
    # Clean queries except place id search
    if "google.com/maps" in u:
        # Keep query_place_id
        m = re.search(r"query_place_id=([^&]+)", u)
        if m:
            return f"google_maps_place_id:{m.group(1)}"
    return u

# Normalize Phone
def normalize_phone(phone: Any) -> str:
    if not phone or pd.isna(phone):
        return ""
    p = str(phone).strip()
    # Remove all non-numeric characters (except leading +)
    has_plus = p.startswith("+")
    p = re.sub(r"\D", "", p)
    if not p:
        return ""
    if p.startswith("08"):
        p = "628" + p[2:]
    elif p.startswith("8") and not has_plus:
        p = "628" + p[1:]
    
    return "+" + p if not p.startswith("+") else p

# Parser for opening hours
def parse_hours_string(hours_str: str) -> Tuple[str, str, bool, bool]:
    h = str(hours_str).strip().lower()
    if h in ["closed", "tutup", "closed today", "tutup hari ini"]:
        return "", "", False, True
    if h in ["open 24 hours", "buka 24 jam", "24 jam", "24 hours", "buka 24jam"]:
        return "00:00", "24:00", True, False
    
    # Try finding time patterns like HH.MM - HH.MM
    m = re.findall(r"(\d{1,2})[.:](\d{2})", h)
    if len(m) == 2:
        try:
            open_h = int(m[0][0])
            open_m = int(m[0][1])
            close_h = int(m[1][0])
            close_m = int(m[1][1])
            return f"{open_h:02d}:{open_m:02d}", f"{close_h:02d}:{close_m:02d}", False, False
        except Exception:
            pass
    return "", "", False, False

# Cache for true raw places.json contents
raw_json_cache = {}

def get_raw_json_record(raw_payload_path: str, place_id: str) -> Optional[dict]:
    if not raw_payload_path or not place_id:
        return None
    if raw_payload_path not in raw_json_cache:
        if os.path.exists(raw_payload_path):
            try:
                with open(raw_payload_path, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                    records_map = {}
                    if isinstance(raw_data, list):
                        for item in raw_data:
                            pid = item.get("placeId")
                            if pid:
                                records_map[pid] = item
                    raw_json_cache[raw_payload_path] = records_map
            except Exception as e:
                logger.warning(f"Failed to load raw JSON file {raw_payload_path}: {e}")
                raw_json_cache[raw_payload_path] = {}
        else:
            raw_json_cache[raw_payload_path] = {}
            
    return raw_json_cache[raw_payload_path].get(place_id)

def classify_price_priority(primary_category: str, category_tags: List[str], status: str) -> Tuple[str, str]:
    if status == "permanently_closed":
        return "not_applicable", "Place is permanently closed"
        
    tags_str = " ".join([t.lower() for t in category_tags]) + " " + primary_category.lower()
    
    high_keywords = ["waterpark", "museum", "recreation", "camping", "island", "tour", "activity", "rental", "guided", "family", "taman bermain", "playground", "theme park"]
    medium_keywords = ["beach", "pantai", "taman", "park", "wisata", "zoo", "kebun binatang", "pool", "kolam"]
    low_keywords = ["mosque", "mushola", "gereja", "monument", "landmark", "danau", "lake", "viewpoint", "bukit", "hill", "air terjun", "waterfall", "mountain", "gunung", "forest", "hutan"]
    
    for kw in high_keywords:
        if kw in tags_str:
            return "high", f"Matches high priority keyword '{kw}'"
    for kw in medium_keywords:
        if kw in tags_str:
            return "medium", f"Matches medium priority keyword '{kw}'"
    for kw in low_keywords:
        if kw in tags_str:
            return "low", f"Matches low priority keyword '{kw}'"
            
    return "low", "Default priority for other categories"

def run_metadata_backfill(
    pilot_path: str = "data/enrichment/pilot/pilot_places.parquet",
    source_map_path: str = "data/canonical/attraction_sources.parquet",
    raw_root: str = "data/raw_records/apify_google_maps",
    output_dir: str = "data/enrichment/metadata",
    reports_dir: str = "reports",
    metadata_version: str = "metadata_backfill_pilot_v1",
    strict_mapping: bool = False,
    dry_run: bool = False
):
    logger.info(f"Starting metadata backfill. Pilot path: {pilot_path}, raw root: {raw_root}")
    
    # Check inputs
    if not os.path.exists(pilot_path):
        raise FileNotFoundError(f"Pilot places file not found: {pilot_path}")
    if not os.path.exists(source_map_path):
        raise FileNotFoundError(f"Source map file not found: {source_map_path}")
    
    # 1. Load data
    df_pilot = pd.read_parquet(pilot_path)
    df_sources = pd.read_parquet(source_map_path)
    
    # Load additional mappings from source_mappings.parquet if exists
    df_mappings = None
    if os.path.exists("data/canonical/source_mappings.parquet"):
        df_mappings = pd.read_parquet("data/canonical/source_mappings.parquet")
        
    # Build maps
    record_to_canon = {}
    for _, r in df_sources.iterrows():
        record_to_canon[r["source_record_id"]] = r["canonical_id"]
    if df_mappings is not None:
        for _, r in df_mappings.iterrows():
            record_to_canon[r["source_record_id"]] = r["canonical_id"]
            
    pilot_places = {} # canonical_id -> dict
    place_id_to_canon = {}
    url_to_canon = {}
    
    for _, row in df_pilot.iterrows():
        cid = row["canonical_id"]
        pilot_places[cid] = row.to_dict()
        
        g_id = row.get("google_place_id") or row.get("source_place_id")
        if pd.notna(g_id) and str(g_id).strip() != "":
            place_id_to_canon[str(g_id).strip()] = cid
            
        s_url = row.get("source_url")
        if pd.notna(s_url) and str(s_url).strip() != "":
            url_to_canon[normalize_url(s_url)] = cid
            
    # Region compatibility check
    region_mapping = {
        "Kota Bandar Lampung": ["bandar_lampung"],
        "Kabupaten Lampung Barat": ["lampung_barat"],
        "Kabupaten Lampung Selatan": ["lampung_selatan"],
        "Kabupaten Lampung Tengah": ["lampung_tengah"],
        "Kabupaten Lampung Timur": ["lampung_timur"],
        "Kabupaten Lampung Utara": ["lampung_utara"],
        "Kabupaten Mesuji": ["mesuji"],
        "Kabupaten Pesawaran": ["pesawaran"],
        "Kabupaten Pesisir Barat": ["pesisir_barat"],
        "Kabupaten Pringsewu": ["pringsewu"],
        "Kabupaten Tanggamus": ["tanggamus"],
        "Kabupaten Tulang Bawang": ["tulang_bawang"],
        "Kabupaten Tulang Bawang Barat": ["tulang_bawang_barat"],
        "Kabupaten Way Kanan": ["way_kanan"],
        "Kota Metro": ["metro"]
    }
    
    # 2. Load all raw records
    parquet_files = glob.glob(os.path.join(raw_root, "**/places.parquet"), recursive=True)
    raw_records = []
    
    for pf in parquet_files:
        try:
            df = pd.read_parquet(pf)
            for _, r in df.iterrows():
                raw_records.append(r.to_dict())
        except Exception as e:
            logger.error(f"Failed to load raw parquet {pf}: {e}")
            
    logger.info(f"Loaded {len(raw_records)} raw records from parquet files.")
    
    # 3. Mapping raw records to canonical_id (Task 2)
    mapped_count = 0
    unmapped_count = 0
    mapping_methods = {}
    
    mapped_by_canon = {} # canonical_id -> list of raw records
    unmapped_records = []
    
    for r in raw_records:
        rid = r.get("source_record_id")
        pid = r.get("source_place_id")
        url = r.get("source_url")
        name = r.get("raw_name")
        lat = r.get("latitude")
        lon = r.get("longitude")
        q_region = r.get("query_region")
        
        cid = None
        method = None
        confidence = 1.0
        
        # Step 1: source_record_id
        if rid and rid in record_to_canon:
            cid = record_to_canon[rid]
            method = "source_record_id"
            confidence = 1.0
            
        # Step 2: Place ID
        elif pid and pid in place_id_to_canon:
            cid = place_id_to_canon[pid]
            method = "google_place_id"
            confidence = 1.0
            
        # Step 3: Normalized URL
        elif url and normalize_url(url) in url_to_canon:
            cid = url_to_canon[normalize_url(url)]
            method = "normalized_url"
            confidence = 0.95
            
        # Step 4: Coordinates + Name Fallback (controlled fallback)
        elif not strict_mapping and pd.notna(lat) and pd.notna(lon) and name:
            best_cid = None
            best_conf = 0.0
            
            for p_cid, p in pilot_places.items():
                p_lat = p["latitude"]
                p_lon = p["longitude"]
                p_name = p["name"]
                p_region = p["region"]
                
                # Check region compatibility
                comp_regions = region_mapping.get(p_region, [])
                if q_region not in comp_regions:
                    continue
                    
                dist = haversine_distance(lat, lon, p_lat, p_lon)
                if dist <= 100.0:
                    f_match = fuzzy_match_ratio(name, p_name)
                    if f_match >= 0.85:
                        conf = f_match * (1.0 - (dist / 100.0) * 0.1)
                        if conf > best_conf:
                            best_conf = conf
                            best_cid = p_cid
            if best_cid:
                cid = best_cid
                method = "coordinates_name_fallback"
                confidence = round(best_conf, 2)
                
        if cid and cid in pilot_places:
            mapped_count += 1
            mapping_methods[method] = mapping_methods.get(method, 0) + 1
            if cid not in mapped_by_canon:
                mapped_by_canon[cid] = []
            
            # Enrich raw record with mapping details
            r_copy = r.copy()
            r_copy["mapped_canonical_id"] = cid
            r_copy["mapping_method"] = method
            r_copy["mapping_confidence"] = confidence
            mapped_by_canon[cid].append(r_copy)
        else:
            unmapped_count += 1
            unmapped_records.append(r)

    logger.info(f"Mapped {mapped_count} raw records. Unmapped {unmapped_count} raw records.")
    
    if dry_run:
        logger.info("Dry run requested. Estimating coverage and exiting.")
        print(f"Dry Run: Successfully mapped: {mapped_count}, Unmapped: {unmapped_count}")
        return
        
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)
    
    place_metadata_rows = []
    opening_hours_rows = []
    facilities_rows = []
    contacts_rows = []
    operational_status_rows = []
    metadata_provenance_rows = []
    metadata_conflicts_rows = []
    
    conflict_counter = 0
    provenance_counter = 0
    opening_hours_counter = 0
    facilities_counter = 0
    contacts_counter = 0
    status_counter = 0

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for cid, pilot in pilot_places.items():
        # Get raw records mapped to this canonical_id
        mapped_records = mapped_by_canon.get(cid, [])
        
        # Sort raw records by collected_at (newest first)
        def get_collected_time(rec):
            c = rec.get("collected_at")
            if not c or pd.isna(c):
                return ""
            return str(c)
        mapped_records.sort(key=get_collected_time, reverse=True)
        
        newest_rec = mapped_records[0] if mapped_records else {}
        
        # Metadata values initialization
        name = pilot["name"]
        region = pilot["region"]
        lat = pilot["latitude"]
        lon = pilot["longitude"]
        website = pilot.get("website") or ""
        phone = pilot.get("phone") or ""
        g_place_id = pilot.get("google_place_id") or pilot.get("source_place_id") or ""
        source_url = pilot.get("source_url") or ""
        
        desc = ""
        address = ""
        street = ""
        city = ""
        postal_code = ""
        rating_val = pilot.get("rating") or 0.0
        rev_count_val = pilot.get("review_count") or 0
        img_url = ""
        op_status = "open"
        is_perm_closed = False
        is_temp_closed = False
        
        mapping_method = newest_rec.get("mapping_method") or "pilot_places_default"
        mapping_confidence = newest_rec.get("mapping_confidence") or 1.0
        
        # Provenance selected tracking dictionary
        selected_provenance = {} # field_name -> dict
        
        # Read from newest record
        if newest_rec:
            # Address and details
            address = newest_rec.get("raw_address") or ""
            street = newest_rec.get("street") or ""
            city = newest_rec.get("city") or ""
            postal_code = newest_rec.get("postal_code") or newest_rec.get("postalCode") or ""
            desc = newest_rec.get("description") or ""
            img_url = newest_rec.get("image_url") or ""
            
            # Check closed status (Task 8)
            # Prioritas: permanently_closed > temporarily_closed > open > unknown
            # Sum/combine closed statuses from all mapped records
            any_perm = any(str(r.get("permanently_closed")).lower() in ["true", "1"] for r in mapped_records)
            any_temp = any(str(r.get("temporarily_closed")).lower() in ["true", "1"] for r in mapped_records)
            
            if any_perm:
                op_status = "permanently_closed"
                is_perm_closed = True
            elif any_temp:
                op_status = "temporarily_closed"
                is_temp_closed = True
            else:
                op_status = "open"
                
            # Website & Phone from raw
            raw_web = newest_rec.get("website")
            if raw_web and pd.notna(raw_web) and str(raw_web).strip() != "":
                website = str(raw_web).strip()
            raw_phone = newest_rec.get("phone")
            if raw_phone and pd.notna(raw_phone) and str(raw_phone).strip() != "":
                phone = str(raw_phone).strip()
                
            # Rating & Review Count
            if pd.notna(newest_rec.get("rating")):
                rating_val = float(newest_rec["rating"])
            if pd.notna(newest_rec.get("review_count")):
                rev_count_val = int(float(newest_rec["review_count"]))

        # Detect conflicts across mapped records (Task 10)
        # website, phone, address, coordinates, operational status
        for rec in mapped_records[1:]:
            rec_id = rec.get("source_record_id") or ""
            # Website
            w_candidate = rec.get("website")
            if w_candidate and pd.notna(w_candidate) and str(w_candidate).strip() != "" and normalize_url(w_candidate) != normalize_url(website):
                conflict_counter += 1
                metadata_conflicts_rows.append({
                    "conflict_id": f"conf_{conflict_counter:04d}", "canonical_id": cid, "field_name": "website",
                    "candidate_value_a": website, "candidate_value_b": str(w_candidate).strip(),
                    "source_a": newest_rec.get("source_record_id") or "pilot_default", "source_b": rec_id,
                    "observed_at_a": get_collected_time(newest_rec), "observed_at_b": get_collected_time(rec),
                    "resolution": "newest_source_priority", "selected_value": website,
                    "resolution_reason": "Selected value from newest raw scraper run", "requires_manual_review": True
                })
            # Phone
            p_candidate = rec.get("phone")
            if p_candidate and pd.notna(p_candidate) and str(p_candidate).strip() != "" and normalize_phone(p_candidate) != normalize_phone(phone):
                conflict_counter += 1
                metadata_conflicts_rows.append({
                    "conflict_id": f"conf_{conflict_counter:04d}", "canonical_id": cid, "field_name": "phone",
                    "candidate_value_a": phone, "candidate_value_b": str(p_candidate).strip(),
                    "source_a": newest_rec.get("source_record_id") or "pilot_default", "source_b": rec_id,
                    "observed_at_a": get_collected_time(newest_rec), "observed_at_b": get_collected_time(rec),
                    "resolution": "newest_source_priority", "selected_value": phone,
                    "resolution_reason": "Selected value from newest raw scraper run", "requires_manual_review": True
                })
            # Address
            a_candidate = rec.get("raw_address")
            if a_candidate and pd.notna(a_candidate) and str(a_candidate).strip() != "" and str(a_candidate).strip().lower() != address.lower():
                conflict_counter += 1
                metadata_conflicts_rows.append({
                    "conflict_id": f"conf_{conflict_counter:04d}", "canonical_id": cid, "field_name": "address",
                    "candidate_value_a": address, "candidate_value_b": str(a_candidate).strip(),
                    "source_a": newest_rec.get("source_record_id") or "pilot_default", "source_b": rec_id,
                    "observed_at_a": get_collected_time(newest_rec), "observed_at_b": get_collected_time(rec),
                    "resolution": "newest_source_priority", "selected_value": address,
                    "resolution_reason": "Selected value from newest raw scraper run", "requires_manual_review": True
                })
            # Coordinates
            lat_cand = rec.get("latitude")
            lon_cand = rec.get("longitude")
            if pd.notna(lat_cand) and pd.notna(lon_cand):
                dist = haversine_distance(lat, lon, lat_cand, lon_cand)
                if dist > 100.0:
                    conflict_counter += 1
                    metadata_conflicts_rows.append({
                        "conflict_id": f"conf_{conflict_counter:04d}", "canonical_id": cid, "field_name": "coordinates",
                        "candidate_value_a": f"{lat},{lon}", "candidate_value_b": f"{lat_cand},{lon_cand}",
                        "source_a": newest_rec.get("source_record_id") or "pilot_default", "source_b": rec_id,
                        "observed_at_a": get_collected_time(newest_rec), "observed_at_b": get_collected_time(rec),
                        "resolution": "newest_source_priority", "selected_value": f"{lat},{lon}",
                        "resolution_reason": "Selected coordinate coordinates from newest scraper run", "requires_manual_review": True
                    })
            # Operational Status
            perm_c = str(rec.get("permanently_closed")).lower() in ["true", "1"]
            temp_c = str(rec.get("temporarily_closed")).lower() in ["true", "1"]
            rec_status = "permanently_closed" if perm_c else ("temporarily_closed" if temp_c else "open")
            if rec_status != op_status:
                conflict_counter += 1
                metadata_conflicts_rows.append({
                    "conflict_id": f"conf_{conflict_counter:04d}", "canonical_id": cid, "field_name": "operational_status",
                    "candidate_value_a": op_status, "candidate_value_b": rec_status,
                    "source_a": newest_rec.get("source_record_id") or "pilot_default", "source_b": rec_id,
                    "observed_at_a": get_collected_time(newest_rec), "observed_at_b": get_collected_time(rec),
                    "resolution": "operational_status_priority", "selected_value": op_status,
                    "resolution_reason": "Closed priority logic: permanently_closed > temporarily_closed > open", "requires_manual_review": True
                })

        # Save Operational Status (Task 8)
        status_counter += 1
        operational_status_rows.append({
            "status_id": f"stat_{status_counter:04d}",
            "canonical_id": cid,
            "operational_status": op_status,
            "is_permanently_closed": is_perm_closed,
            "is_temporarily_closed": is_temp_closed,
            "raw_status": "permanently_closed" if is_perm_closed else ("temporarily_closed" if is_temp_closed else "open"),
            "source_name": "apify_google_maps",
            "source_record_id": newest_rec.get("source_record_id") or "pilot_default",
            "source_url": newest_rec.get("source_url") or "",
            "observed_at": get_collected_time(newest_rec) or now_str,
            "confidence": mapping_confidence
        })

        # Save Contacts (Task 7)
        if website:
            contacts_counter += 1
            contacts_rows.append({
                "contact_id": f"con_{contacts_counter:04d}", "canonical_id": cid, "contact_type": "website",
                "contact_value": website, "normalized_value": normalize_url(website), "source_name": "apify_google_maps",
                "source_record_id": newest_rec.get("source_record_id") or "pilot_default", "source_url": newest_rec.get("source_url") or "",
                "observed_at": get_collected_time(newest_rec) or now_str, "confidence": mapping_confidence
            })
        if phone:
            contacts_counter += 1
            contacts_rows.append({
                "contact_id": f"con_{contacts_counter:04d}", "canonical_id": cid, "contact_type": "phone",
                "contact_value": phone, "normalized_value": normalize_phone(phone), "source_name": "apify_google_maps",
                "source_record_id": newest_rec.get("source_record_id") or "pilot_default", "source_url": newest_rec.get("source_url") or "",
                "observed_at": get_collected_time(newest_rec) or now_str, "confidence": mapping_confidence
            })
        if source_url:
            contacts_counter += 1
            contacts_rows.append({
                "contact_id": f"con_{contacts_counter:04d}", "canonical_id": cid, "contact_type": "google_maps_url",
                "contact_value": source_url, "normalized_value": normalize_url(source_url), "source_name": "apify_google_maps",
                "source_record_id": newest_rec.get("source_record_id") or "pilot_default", "source_url": newest_rec.get("source_url") or "",
                "observed_at": get_collected_time(newest_rec) or now_str, "confidence": mapping_confidence
            })

        # Parse and save Opening Hours (Task 5)
        # We need the full details from raw places.json (as hours array is structured)
        has_hours = False
        if newest_rec:
            raw_path_json = newest_rec.get("raw_payload_path")
            raw_json_item = get_raw_json_record(raw_path_json, newest_rec.get("source_place_id"))
            
            raw_hours = None
            if raw_json_item and "openingHours" in raw_json_item:
                raw_hours = raw_json_item["openingHours"]
            elif "opening_hours" in newest_rec:
                # fall back to places.parquet parsed string hours
                try:
                    raw_hours = json.loads(newest_rec["opening_hours"])
                except Exception:
                    pass
            
            if isinstance(raw_hours, list):
                day_mapping = {
                    "senin": "monday", "selasa": "tuesday", "rabu": "wednesday",
                    "kamis": "thursday", "jumat": "friday", "sabtu": "saturday",
                    "minggu": "sunday", "monday": "monday", "tuesday": "tuesday",
                    "wednesday": "wednesday", "thursday": "thursday", "friday": "friday",
                    "saturday": "saturday", "sunday": "sunday"
                }
                
                # Check duplicates or format
                for idx, entry in enumerate(raw_hours):
                    day_raw = str(entry.get("day", "")).strip().lower()
                    hours_text = str(entry.get("hours", ""))
                    day_norm = day_mapping.get(day_raw)
                    
                    if day_norm:
                        open_t, close_t, is_24, is_closed = parse_hours_string(hours_text)
                        if open_t or close_t or is_24 or is_closed:
                            has_hours = True
                            opening_hours_counter += 1
                            opening_hours_rows.append({
                                "opening_hours_id": f"oh_{opening_hours_counter:04d}",
                                "canonical_id": cid,
                                "day_of_week": day_norm,
                                "period_index": 0,
                                "open_time": open_t,
                                "close_time": close_t,
                                "is_24_hours": is_24,
                                "is_closed": is_closed,
                                "raw_value": hours_text,
                                "source_name": "apify_google_maps",
                                "source_record_id": newest_rec.get("source_record_id") or "pilot_default",
                                "source_url": newest_rec.get("source_url") or "",
                                "observed_at": get_collected_time(newest_rec) or now_str,
                                "confidence": mapping_confidence
                            })

        # Parse and save Facilities (Task 6)
        has_facilities = False
        if newest_rec:
            raw_path_json = newest_rec.get("raw_payload_path")
            raw_json_item = get_raw_json_record(raw_path_json, newest_rec.get("source_place_id"))
            
            raw_facilities = None
            if raw_json_item and "additionalInfo" in raw_json_item:
                raw_facilities = raw_json_item["additionalInfo"]
            elif "facilities" in newest_rec:
                try:
                    raw_facilities = json.loads(newest_rec["facilities"])
                except Exception:
                    pass
                    
            if isinstance(raw_facilities, dict):
                group_map = {
                    "opsi layanan": "service_options", "service options": "service_options",
                    "aksesibilitas": "accessibility", "accessibility": "accessibility",
                    "fasilitas": "amenities", "amenities": "amenities",
                    "pembayaran": "payments", "payments": "payments",
                    "anak-anak": "children", "children": "children",
                    "hewan peliharaan": "pets", "pets": "pets",
                    "parkir": "parking", "parking": "parking"
                }
                
                for grp_key, grp_list in raw_facilities.items():
                    grp_norm = group_map.get(str(grp_key).strip().lower(), "other")
                    if isinstance(grp_list, list):
                        for item in grp_list:
                            if isinstance(item, dict):
                                for item_name, item_val in item.items():
                                    avail = "unknown"
                                    if str(item_val).lower() in ["true", "1"]:
                                        avail = "available"
                                    elif str(item_val).lower() in ["false", "0"]:
                                        avail = "unavailable"
                                        
                                    fac_grp = grp_norm
                                    item_name_lower = str(item_name).lower()
                                    if "toilet" in item_name_lower or "restroom" in item_name_lower or "kamar kecil" in item_name_lower:
                                        fac_grp = "restroom"
                                    elif any(kw in item_name_lower for kw in ["makanan", "minuman", "food", "drink", "kuliner", "restoran", "cafe"]):
                                        fac_grp = "food_and_drink"
                                    elif any(kw in item_name_lower for kw in ["luar ruangan", "outdoor", "taman"]):
                                        fac_grp = "outdoor"
                                        
                                    has_facilities = True
                                    facilities_counter += 1
                                    facilities_rows.append({
                                        "facility_id": f"fac_{facilities_counter:04d}",
                                        "canonical_id": cid,
                                        "facility_group": fac_grp,
                                        "facility_type": "standard",
                                        "facility_name": item_name,
                                        "availability": avail,
                                        "raw_value": str(item_val),
                                        "source_name": "apify_google_maps",
                                        "source_record_id": newest_rec.get("source_record_id") or "pilot_default",
                                        "source_url": newest_rec.get("source_url") or "",
                                        "observed_at": get_collected_time(newest_rec) or now_str,
                                        "confidence": mapping_confidence
                                    })

        # Save Provenance per Field (Task 9)
        provenance_fields = {
            "name": name, "region": region, "latitude": lat, "longitude": lon,
            "website": website, "phone": phone, "address": address, "street": street,
            "city": city, "postal_code": postal_code, "operational_status": op_status,
            "description": desc, "image_url": img_url
        }
        
        for f_name, f_val in provenance_fields.items():
            if f_val is not None and str(f_val).strip() != "":
                provenance_counter += 1
                metadata_provenance_rows.append({
                    "provenance_id": f"prov_{provenance_counter:04d}",
                    "canonical_id": cid,
                    "entity_type": "place_metadata",
                    "field_name": f_name,
                    "field_value": str(f_val),
                    "source_name": "apify_google_maps" if newest_rec else "pilot_default",
                    "source_record_id": newest_rec.get("source_record_id") if newest_rec else "pilot_default",
                    "source_url": newest_rec.get("source_url") if newest_rec else "",
                    "observed_at": get_collected_time(newest_rec) or now_str,
                    "collected_at": newest_rec.get("collected_at") or now_str,
                    "mapping_method": mapping_method,
                    "mapping_confidence": mapping_confidence,
                    "field_confidence": 1.0,
                    "is_selected_value": True,
                    "conflict_group_id": ""
                })

        # Calculate Completeness Score (Task 11)
        # Bobot: address=15, coordinates=15, website=10, phone=10, opening hours=15, operational status=10, facilities=15, description=5, category tags=5
        comp_score = 0
        if address:
            comp_score += 15
        if pd.notna(lat) and pd.notna(lon) and lat != 0.0 and lon != 0.0:
            comp_score += 15
        if website:
            comp_score += 10
        if phone:
            comp_score += 10
        if has_hours:
            comp_score += 15
        if op_status != "unknown":
            comp_score += 10
        if has_facilities:
            comp_score += 15
        if desc:
            comp_score += 5
        
        # Primary category or tags
        prim_cat = pilot.get("primary_category") or "other"
        cat_tags = pilot.get("category_tags")
        if isinstance(cat_tags, str):
            cat_tags = [cat_tags]
        elif hasattr(cat_tags, "tolist"):
            cat_tags = cat_tags.tolist()
            
        if cat_tags is None or len(cat_tags) == 0:
            cat_tags = ["other"]
        else:
            cat_tags = [str(t) for t in cat_tags]
            
        if len(cat_tags) > 0 and cat_tags[0] != "":
            comp_score += 5
            
        place_metadata_rows.append({
            "canonical_id": cid,
            "name": name,
            "region": region,
            "primary_category": prim_cat,
            "category_tags": json.dumps(cat_tags),
            "description": desc,
            "address": address,
            "street": street,
            "city": city,
            "postal_code": postal_code,
            "latitude": lat,
            "longitude": lon,
            "website": website,
            "phone": phone,
            "google_maps_url": source_url,
            "google_place_id": g_place_id,
            "rating": rating_val,
            "review_count": rev_count_val,
            "image_url": img_url,
            "source_count": pilot.get("source_count") or 1,
            "metadata_source_count": len(mapped_records),
            "metadata_completeness_score": comp_score,
            "mapping_method": mapping_method,
            "mapping_confidence": mapping_confidence,
            "last_observed_at": get_collected_time(newest_rec) or now_str,
            "metadata_version": metadata_version
        })

    # Save operational_status.csv / parquet
    df_op = pd.DataFrame(operational_status_rows)
    df_op.to_csv(os.path.join(output_dir, "operational_status.csv"), index=False, encoding="utf-8")
    df_op.to_parquet(os.path.join(output_dir, "operational_status.parquet"), index=False)

    # Save contacts.csv / parquet
    df_con = pd.DataFrame(contacts_rows)
    if df_con.empty:
        df_con = pd.DataFrame(columns=["contact_id", "canonical_id", "contact_type", "contact_value", "normalized_value", "source_name", "source_record_id", "source_url", "observed_at", "confidence"])
    df_con.to_csv(os.path.join(output_dir, "contacts.csv"), index=False, encoding="utf-8")
    df_con.to_parquet(os.path.join(output_dir, "contacts.parquet"), index=False)

    # Save opening_hours.csv / parquet
    df_oh = pd.DataFrame(opening_hours_rows)
    if df_oh.empty:
        df_oh = pd.DataFrame(columns=["opening_hours_id", "canonical_id", "day_of_week", "period_index", "open_time", "close_time", "is_24_hours", "is_closed", "raw_value", "source_name", "source_record_id", "source_url", "observed_at", "confidence"])
    df_oh.to_csv(os.path.join(output_dir, "opening_hours.csv"), index=False, encoding="utf-8")
    df_oh.to_parquet(os.path.join(output_dir, "opening_hours.parquet"), index=False)

    # Save facilities.csv / parquet
    df_fac = pd.DataFrame(facilities_rows)
    if df_fac.empty:
        df_fac = pd.DataFrame(columns=["facility_id", "canonical_id", "facility_group", "facility_type", "facility_name", "availability", "raw_value", "source_name", "source_record_id", "source_url", "observed_at", "confidence"])
    df_fac.to_csv(os.path.join(output_dir, "facilities.csv"), index=False, encoding="utf-8")
    df_fac.to_parquet(os.path.join(output_dir, "facilities.parquet"), index=False)

    # Save place_metadata.csv / jsonl / parquet
    df_meta = pd.DataFrame(place_metadata_rows)
    df_meta.to_csv(os.path.join(output_dir, "place_metadata.csv"), index=False, encoding="utf-8")
    df_meta.to_parquet(os.path.join(output_dir, "place_metadata.parquet"), index=False)
    with open(os.path.join(output_dir, "place_metadata.jsonl"), "w", encoding="utf-8") as f:
        for r in place_metadata_rows:
            f.write(json.dumps(r) + "\n")

    # Save metadata_provenance.csv
    df_prov = pd.DataFrame(metadata_provenance_rows)
    df_prov.to_csv(os.path.join(output_dir, "metadata_provenance.csv"), index=False, encoding="utf-8")

    # Save metadata_conflicts.csv
    df_conf = pd.DataFrame(metadata_conflicts_rows)
    if df_conf.empty:
        df_conf = pd.DataFrame(columns=["conflict_id", "canonical_id", "field_name", "candidate_value_a", "candidate_value_b", "source_a", "source_b", "observed_at_a", "observed_at_b", "resolution", "selected_value", "resolution_reason", "requires_manual_review"])
    df_conf.to_csv(os.path.join(output_dir, "metadata_conflicts.csv"), index=False, encoding="utf-8")

    # Save unmapped_source_records.jsonl
    with open(os.path.join(output_dir, "unmapped_source_records.jsonl"), "w", encoding="utf-8") as f:
        for r in unmapped_records:
            f.write(json.dumps(r) + "\n")

    # 5. Price Candidates Classification (Task 13)
    # Generate data/enrichment/price/pilot_price_candidates.csv
    price_candidates = []
    for row in place_metadata_rows:
        cid = row["canonical_id"]
        name = row["name"]
        region = row["region"]
        prim_cat = row["primary_category"]
        
        tags_str = row["category_tags"]
        try:
            tags = json.loads(tags_str)
        except Exception:
            tags = [prim_cat]
            
        status = next((r["operational_status"] for r in operational_status_rows if r["canonical_id"] == cid), "open")
        
        priority, reason = classify_price_priority(prim_cat, tags, status)
        
        suggested_queries = [
            f"harga tiket masuk {name} Lampung",
            f"entry ticket price {name} Lampung",
            f"biaya tiket {name}"
        ]
        
        # Look for potential existing price clues in description or raw record payload
        price_hint = ""
        price_raw_val = ""
        
        price_candidates.append({
            "canonical_id": cid,
            "name": name,
            "region": region,
            "primary_category": prim_cat,
            "category_tags": ";".join(tags),
            "operational_status": status,
            "website": row["website"],
            "google_maps_url": row["google_maps_url"],
            "rating": row["rating"],
            "review_count": row["review_count"],
            "likely_paid_entry": priority in ["high", "medium"],
            "price_research_priority": priority,
            "price_research_reason": reason,
            "suggested_queries": ";".join(suggested_queries),
            "existing_price_hint": price_hint,
            "existing_price_raw_value": price_raw_val,
            "requires_manual_review": priority in ["high", "medium"]
        })
        
    os.makedirs("data/enrichment/price", exist_ok=True)
    df_price = pd.DataFrame(price_candidates)
    df_price.to_csv("data/enrichment/price/pilot_price_candidates.csv", index=False, encoding="utf-8")

    # 6. Save Reports (Task 12)
    # metadata_backfill_summary.md
    total_pilot = len(pilot_places)
    mapped_places_set = set(mapped_by_canon.keys())
    successfully_mapped = len(mapped_places_set)
    no_raw_mapping = total_pilot - successfully_mapped
    exact_place_id = mapping_methods.get("google_place_id", 0)
    source_record_count = mapping_methods.get("source_record_id", 0)
    fallback_count = mapping_methods.get("coordinates_name_fallback", 0)
    normalized_url_count = mapping_methods.get("normalized_url", 0)
    
    # Coverage calculation
    website_count = sum(1 for r in place_metadata_rows if r["website"])
    phone_count = sum(1 for r in place_metadata_rows if r["phone"])
    address_count = sum(1 for r in place_metadata_rows if r["address"])
    desc_count = sum(1 for r in place_metadata_rows if r["description"])
    
    oh_covered = len(set(r["canonical_id"] for r in opening_hours_rows))
    fac_covered = len(set(r["canonical_id"] for r in facilities_rows))
    op_status_covered = len(set(r["canonical_id"] for r in operational_status_rows if r["operational_status"] != "unknown"))
    
    # Segment distributions
    complete_count = sum(1 for r in place_metadata_rows if r["metadata_completeness_score"] >= 80)
    moderate_count = sum(1 for r in place_metadata_rows if r["metadata_completeness_score"] >= 50 and r["metadata_completeness_score"] < 80)
    sparse_count = sum(1 for r in place_metadata_rows if r["metadata_completeness_score"] >= 1 and r["metadata_completeness_score"] < 50)
    empty_count_places = sum(1 for r in place_metadata_rows if r["metadata_completeness_score"] == 0)
    
    perm_closed = sum(1 for r in operational_status_rows if r["operational_status"] == "permanently_closed")
    temp_closed = sum(1 for r in operational_status_rows if r["operational_status"] == "temporarily_closed")
    unknown_op = sum(1 for r in operational_status_rows if r["operational_status"] == "unknown")
    
    # Conflict distribution
    conf_by_field = {}
    for r in metadata_conflicts_rows:
        f_n = r["field_name"]
        conf_by_field[f_n] = conf_by_field.get(f_n, 0) + 1

    # reports/metadata_backfill_summary.md
    with open(os.path.join(reports_dir, "metadata_backfill_summary.md"), "w", encoding="utf-8") as f:
        f.write("# Metadata Backfill Pilot Summary Report\n\n")
        f.write(f"Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n")
        
        f.write("## Mapping Accuracy & Quality\n")
        f.write(f"- **Total Pilot Places**: {total_pilot}\n")
        f.write(f"- **Successfully Mapped Places**: {successfully_mapped}\n")
        f.write(f"- **Places with No Raw Apify Mapping**: {no_raw_mapping}\n")
        f.write(f"- **Exact Google Place ID Mappings**: {exact_place_id}\n")
        f.write(f"- **Source-Record ID Mappings**: {source_record_count}\n")
        f.write(f"- **Normalized URL Mappings**: {normalized_url_count}\n")
        f.write(f"- **Fuzzy Coordinate Fallback Mappings**: {fallback_count}\n")
        f.write(f"- **Ambiguous/Unmapped Raw Scraped Records**: {len(unmapped_records)}\n\n")
        
        f.write("## Field Coverage Statistics\n")
        f.write(f"- **Address Coverage**: {address_count} ({address_count/total_pilot:.2%})\n")
        f.write(f"- **Website Coverage**: {website_count} ({website_count/total_pilot:.2%})\n")
        f.write(f"- **Phone Coverage**: {phone_count} ({phone_count/total_pilot:.2%})\n")
        f.write(f"- **Opening Hours Coverage**: {oh_covered} ({oh_covered/total_pilot:.2%})\n")
        f.write(f"- **Facilities Coverage**: {fac_covered} ({fac_covered/total_pilot:.2%})\n")
        f.write(f"- **Operational Status Coverage**: {op_status_covered} ({op_status_covered/total_pilot:.2%})\n")
        f.write(f"- **Description Coverage**: {desc_count} ({desc_count/total_pilot:.2%})\n\n")
        
        f.write("## Completeness Distribution\n")
        f.write(f"- **Complete (>= 80)**: {complete_count}\n")
        f.write(f"- **Moderate (50-79)**: {moderate_count}\n")
        f.write(f"- **Sparse (1-49)**: {sparse_count}\n")
        f.write(f"- **Empty (0)**: {empty_count_places}\n\n")
        
        f.write("## Conflict Resolution Metrics\n")
        f.write(f"- **Total Conflict Count**: {len(metadata_conflicts_rows)}\n")
        for fn, c_c in conf_by_field.items():
            f.write(f"  - Conflict on {fn}: {c_c}\n")
        f.write("\n")
        
        f.write("## Operational Status Summary\n")
        f.write(f"- **Permanently Closed**: {perm_closed}\n")
        f.write(f"- **Temporarily Closed**: {temp_closed}\n")
        f.write(f"- **Unknown Operational Status**: {unknown_op}\n")

    # Generate coverage files
    df_meta["has_address"] = df_meta["address"].apply(lambda x: bool(x))
    df_meta["has_website"] = df_meta["website"].apply(lambda x: bool(x))
    df_meta["has_phone"] = df_meta["phone"].apply(lambda x: bool(x))
    df_meta["has_hours"] = df_meta["canonical_id"].isin(set(r["canonical_id"] for r in opening_hours_rows))
    df_meta["has_facilities"] = df_meta["canonical_id"].isin(set(r["canonical_id"] for r in facilities_rows))
    
    df_meta.to_csv(os.path.join(reports_dir, "metadata_backfill_coverage.csv"), index=False)
    
    # Region coverage
    reg_cov = df_meta.groupby("region").agg(
        total_places=("canonical_id", "count"),
        website_cov=("has_website", "sum"),
        phone_cov=("has_phone", "sum"),
        hours_cov=("has_hours", "sum"),
        facilities_cov=("has_facilities", "sum"),
        avg_completeness=("metadata_completeness_score", "mean")
    ).reset_index()
    reg_cov.to_csv(os.path.join(reports_dir, "metadata_backfill_region_coverage.csv"), index=False)
    
    # Category coverage
    cat_cov = df_meta.groupby("primary_category").agg(
        total_places=("canonical_id", "count"),
        website_cov=("has_website", "sum"),
        phone_cov=("has_phone", "sum"),
        hours_cov=("has_hours", "sum"),
        facilities_cov=("has_facilities", "sum"),
        avg_completeness=("metadata_completeness_score", "mean")
    ).reset_index()
    cat_cov.to_csv(os.path.join(reports_dir, "metadata_backfill_category_coverage.csv"), index=False)
    
    # Missing fields
    missing_fields_rows = []
    for cid, row in df_meta.iterrows():
        missing = []
        if not row["has_address"]: missing.append("address")
        if not row["has_website"]: missing.append("website")
        if not row["has_phone"]: missing.append("phone")
        if not row["has_hours"]: missing.append("opening_hours")
        if not row["has_facilities"]: missing.append("facilities")
        if not row["description"]: missing.append("description")
        
        if missing:
            missing_fields_rows.append({
                "canonical_id": row["canonical_id"],
                "name": row["name"],
                "missing_fields": ";".join(missing),
                "completeness_score": row["metadata_completeness_score"]
            })
    pd.DataFrame(missing_fields_rows).to_csv(os.path.join(reports_dir, "metadata_backfill_missing_fields.csv"), index=False)
    
    # Conflicts report
    df_conf.to_csv(os.path.join(reports_dir, "metadata_backfill_conflicts.csv"), index=False)
    
    # Mapping quality
    mapping_quality_rows = []
    for cid, row in df_meta.iterrows():
        mapping_quality_rows.append({
            "canonical_id": row["canonical_id"],
            "name": row["name"],
            "mapping_method": row["mapping_method"],
            "mapping_confidence": row["mapping_confidence"],
            "metadata_source_count": row["metadata_source_count"]
        })
    pd.DataFrame(mapping_quality_rows).to_csv(os.path.join(reports_dir, "metadata_backfill_mapping_quality.csv"), index=False)
    
    logger.info("Metadata backfill completed successfully.")
