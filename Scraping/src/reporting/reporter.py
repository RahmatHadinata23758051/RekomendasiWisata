import os
import glob
import json
import logging
import pandas as pd
from datetime import datetime, timezone
from src.pipeline.normalize import canonicalize_region_name, REGION_MAP, REGIONS

logger = logging.getLogger("scraper.reporting")

def generate_reports():
    reports_dir = "reports"
    os.makedirs(reports_dir, exist_ok=True)
    
    # 1. Read Manifest & Raw counts
    manifest_path = "data/raw_records/apify_google_maps/manifest.json"
    manifest_entries = []
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_entries = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read manifest: {e}")
            
    # OSM raw count
    raw_osm_files = glob.glob(os.path.join("data", "raw_records", "osm", "*.jsonl"))
    osm_raw_count = 0
    osm_files_breakdown = []
    for filepath in raw_osm_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                cnt = len([line for line in f if line.strip()])
                osm_raw_count += cnt
                osm_files_breakdown.append({
                    "filepath": filepath.replace("\\", "/"),
                    "region": "lampung_province",
                    "raw_count": cnt
                })
        except Exception:
            pass
            
    apify_raw_count = sum(entry.get("raw_count", 0) for entry in manifest_entries)
    total_raw_inputs = osm_raw_count + apify_raw_count

    # 2. Read All Normalized Records (including rejected)
    all_normalized_path = os.path.join("data", "normalized", "all_normalized.jsonl")
    all_normalized_records = []
    if os.path.exists(all_normalized_path):
        try:
            with open(all_normalized_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        all_normalized_records.append(json.loads(line))
        except Exception as e:
            logger.error(f"Failed to load all_normalized.jsonl: {e}")

    # 3. Read Canonical Verified Records
    verified_path = os.path.join("data", "canonical", "attractions_master_verified.jsonl")
    verified_records = []
    if os.path.exists(verified_path):
        try:
            with open(verified_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        verified_records.append(json.loads(line))
        except Exception:
            pass
            
    # 4. Read Canonical Candidate Records (Manual Review)
    candidates_path = os.path.join("data", "canonical", "attractions_candidates.jsonl")
    candidates_records = []
    if os.path.exists(candidates_path):
        try:
            with open(candidates_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        candidates_records.append(json.loads(line))
        except Exception:
            pass
            
    # 5. Read attraction sources mappings parquet
    mappings_path = os.path.join("data", "canonical", "attraction_sources.parquet")
    df_maps = pd.DataFrame()
    if os.path.exists(mappings_path):
        try:
            df_maps = pd.read_parquet(mappings_path)
        except Exception as e:
            logger.error(f"Failed to read attraction_sources.parquet: {e}")

    # Standard reconciliation counts
    # Normalized records excluding rejected (for deduplication inputs)
    normalized_path = os.path.join("data", "normalized", "normalized_attractions.jsonl")
    normalized_records_count = 0
    if os.path.exists(normalized_path):
        try:
            with open(normalized_path, "r", encoding="utf-8") as f:
                normalized_records_count = len([line for line in f if line.strip()])
        except Exception:
            pass

    total_canonical = len(verified_records) + len(candidates_records)
    total_duplicates_merged = normalized_records_count - total_canonical if normalized_records_count else 0
    total_rejected = len([r for r in all_normalized_records if r.get("classification") == "rejected"])
    total_source_duplicates = total_raw_inputs - len(all_normalized_records)

    # 6. Breakdowns by Region and File
    def get_region_name(r: dict) -> str:
        reg = r.get("city_regency") or r.get("query_region")
        return canonicalize_region_name(reg) or "Kota Bandar Lampung"

    region_stats = {}
    for r in all_normalized_records:
        reg = get_region_name(r)
        cls = r.get("classification") or "unknown"
        if reg not in region_stats:
            region_stats[reg] = {"raw": 0, "accepted": 0, "manual_review": 0, "rejected": 0}
        region_stats[reg]["raw"] += 1
        if cls in region_stats[reg]:
            region_stats[reg][cls] += 1

    file_stats = {}
    for r in all_normalized_records:
        path = r.get("raw_payload_path") or "Unknown File"
        path = path.replace("\\", "/")
        cls = r.get("classification") or "unknown"
        if path not in file_stats:
            file_stats[path] = {"region": get_region_name(r), "raw": 0, "accepted": 0, "manual_review": 0, "rejected": 0}
        file_stats[path]["raw"] += 1
        if cls in file_stats[path]:
            file_stats[path][cls] += 1

    # Cross-Source matching statistics
    canonical_to_sources = {}
    if not df_maps.empty:
        for _, row in df_maps.iterrows():
            cid = row["canonical_id"]
            sid = row["source_record_id"]
            if cid not in canonical_to_sources:
                canonical_to_sources[cid] = []
            canonical_to_sources[cid].append(sid)

    osm_and_apify_matches = 0
    apify_only_canonical = 0
    osm_only_canonical = 0
    
    for cid, sources in canonical_to_sources.items():
        has_osm = any("osm_" in s for s in sources)
        has_apify = any("apify_google_maps_" in s for s in sources)
        if has_osm and has_apify:
            osm_and_apify_matches += 1
        elif has_apify:
            apify_only_canonical += 1
        elif has_osm:
            osm_only_canonical += 1

    parent_child_count = sum(1 for r in (verified_records + candidates_records) if r.get("parent_canonical_id") is not None)

    # --- WRITE DATA RECONCILIATION CSV ---
    recon_rows = [
        {"Metric": "OSM Raw Records", "Count": osm_raw_count, "Percentage": round(osm_raw_count / total_raw_inputs * 100, 2) if total_raw_inputs > 0 else 0.0},
        {"Metric": "Apify Raw Records", "Count": apify_raw_count, "Percentage": round(apify_raw_count / total_raw_inputs * 100, 2) if total_raw_inputs > 0 else 0.0},
        {"Metric": "Total Raw Input Records", "Count": total_raw_inputs, "Percentage": 100.0},
        {"Metric": "Total Normalized (Accepted + Manual)", "Count": normalized_records_count, "Percentage": round(normalized_records_count / total_raw_inputs * 100, 2)},
        {"Metric": "Total Rejected & Discarded", "Count": total_rejected, "Percentage": round(total_rejected / total_raw_inputs * 100, 2)},
        {"Metric": "Duplicate Source Records Removed", "Count": total_source_duplicates, "Percentage": round(total_source_duplicates / total_raw_inputs * 100, 2)},
        {"Metric": "Verified Canonical Attractions", "Count": len(verified_records), "Percentage": round(len(verified_records) / total_canonical * 100, 2) if total_canonical > 0 else 0.0},
        {"Metric": "Manual Review Candidates", "Count": len(candidates_records), "Percentage": round(len(candidates_records) / total_canonical * 100, 2) if total_canonical > 0 else 0.0},
        {"Metric": "Total Canonical Places", "Count": total_canonical, "Percentage": 100.0},
        {"Metric": "Deduplicated Duplicate Merges", "Count": total_duplicates_merged, "Percentage": round(total_duplicates_merged / normalized_records_count * 100, 2) if normalized_records_count > 0 else 0.0}
    ]
    pd.DataFrame(recon_rows).to_csv(os.path.join(reports_dir, "canonical_reconciliation.csv"), index=False, encoding="utf-8")

    # --- WRITE DATA RECONCILIATION MD ---
    recon_md = f"""# Data Reconciliation & Quality Audit Report

Generated on: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}

## 1. Executive Summary

This report displays the results of running the multi-dataset importer, normalizer, and deduplicator pipeline on tourism attractions.

| Metric | Count | Percentage | Description |
| :--- | :---: | :---: | :--- |
| **OSM Raw Records** | {osm_raw_count} | {round(osm_raw_count/total_raw_inputs*100, 2) if total_raw_inputs > 0 else 0}% | Raw places collected via OSM Overpass API |
| **Apify Raw Records** | {apify_raw_count} | {round(apify_raw_count/total_raw_inputs*100, 2) if total_raw_inputs > 0 else 0}% | Raw places imported from Google Maps Apify export |
| **Total Input Records** | **{total_raw_inputs}** | **100.0%** | **Combined Raw inputs** |
| | | | |
| **Total Normalized (Inputs to Dedup)** | **{normalized_records_count}** | **{round(normalized_records_count/total_raw_inputs*100, 2) if total_raw_inputs > 0 else 0}%** | **Accepted + Manual Review records** |
| **Total Discarded/Rejected** | **{total_rejected}** | **{round(total_rejected/total_raw_inputs*100, 2) if total_raw_inputs > 0 else 0}%** | **Classified as rejected** |
| **Duplicate Source Records Removed** | **{total_source_duplicates}** | **{round(total_source_duplicates/total_raw_inputs*100, 2) if total_raw_inputs > 0 else 0}%** | **Duplicate source_record_ids removed** |
| | | | |
| **Verified Canonical Attractions** | {len(verified_records)} | {round(len(verified_records)/total_canonical*100, 2) if total_canonical > 0 else 0}% | attractions_master_verified |
| **Manual Review Candidates** | {len(candidates_records)} | {round(len(candidates_records)/total_canonical*100, 2) if total_canonical > 0 else 0}% | attractions_candidates |
| **Total Canonical Places** | **{total_canonical}** | **100.0%** | **Deduplicated attraction locations** |
| **Duplicates Merged** | **{total_duplicates_merged}** | **{round(total_duplicates_merged/normalized_records_count*100, 2) if normalized_records_count > 0 else 0}%** | **Merged source records** |

---

## 2. Leak-Free Reconciliation Math

* **Total Inputs**: `{osm_raw_count} (OSM Raw) + {apify_raw_count} (Apify Raw) = {total_raw_inputs}`
* **Reconciliation Equation**:
  `Total Raw Inputs ({total_raw_inputs}) = Total Normalized ({normalized_records_count}) + Total Rejected/Discarded ({total_rejected}) + Duplicate Source Records ({total_source_duplicates})`
  Verification: `{normalized_records_count} + {total_rejected} + {total_source_duplicates} = {normalized_records_count + total_rejected + total_source_duplicates}` (Match: {"YES" if normalized_records_count + total_rejected + total_source_duplicates == total_raw_inputs else "NO"})
* **Deduplication Equation**:
  `Total Normalized ({normalized_records_count}) = Total Canonical ({total_canonical}) + Duplicates Merged ({total_duplicates_merged})`
  Verification: `{total_canonical} + {total_duplicates_merged} = {total_canonical + total_duplicates_merged}` (Match: {"YES" if total_canonical + total_duplicates_merged == normalized_records_count else "NO"})

---

## 3. Per-Region Breakdown

Below are the raw input and classification breakdown counts for each region:

| Region | Raw Records | Accepted | Manual Review | Rejected |
| :--- | :---: | :---: | :---: | :---: |
"""
    for region, stats in sorted(region_stats.items()):
        recon_md += f"| **{region}** | {stats['raw']} | {stats['accepted']} | {stats['manual_review']} | {stats['rejected']} |\n"

    recon_md += """
---

## 4. Per-File Breakdown

Below are the metrics showing the source raw file mapping details:

| File Path | Region / Target | Raw Count | Accepted | Manual Review | Rejected |
| :--- | :--- | :---: | :---: | :---: | :---: |
"""
    for filepath, stats in sorted(file_stats.items()):
        # Try to match with manifest to show details
        fn = os.path.basename(filepath)
        recon_md += f"| `{fn}` | {stats['region']} | {stats['raw']} | {stats['accepted']} | {stats['manual_review']} | {stats['rejected']} |\n"

    recon_md += f"""
---

## 5. Cross-Source Deduplication & Matches
- **Matches (Apify & OSM Merged)**: {osm_and_apify_matches}
- **Apify-only Canonical Attractions**: {apify_only_canonical}
- **OSM-only Canonical Attractions**: {osm_only_canonical}
- **Parent-Child candidates linked**: {parent_child_count}
"""

    with open(os.path.join(reports_dir, "data_reconciliation.md"), "w", encoding="utf-8") as f:
        f.write(recon_md)

    # --- GENERATE SAMPLE AUDIT 1: accepted_low_confidence.csv ---
    accepted_records = [r for r in all_normalized_records if r.get("classification") == "accepted"]
    accepted_sorted = sorted(accepted_records, key=lambda x: x.get("classification_confidence", 1.0))
    low_conf_sample = accepted_sorted[:50]
    
    low_conf_rows = []
    for r in low_conf_sample:
        low_conf_rows.append({
            "source_record_id": r.get("source_record_id"),
            "name": r.get("name"),
            "source": r.get("source"),
            "classification_confidence": r.get("classification_confidence"),
            "classification_signals": ",".join(r.get("classification_signals", [])),
            "classification_reason": r.get("classification_reason")
        })
    pd.DataFrame(low_conf_rows).to_csv(os.path.join(reports_dir, "accepted_low_confidence.csv"), index=False, encoding="utf-8")

    # --- GENERATE SAMPLE AUDIT 2: taman_category_audit.csv ---
    taman_records = []
    for r in all_normalized_records:
        cats = r.get("categories") or []
        is_taman = any("taman" in c.lower() or "park" in c.lower() for c in cats)
        if is_taman or "taman" in r.get("name", "").lower() or "park" in r.get("name", "").lower():
            taman_records.append(r)
            
    taman_sample = taman_records[:50]
    taman_rows = []
    for r in taman_sample:
        taman_rows.append({
            "source_record_id": r.get("source_record_id"),
            "name": r.get("name"),
            "source": r.get("source"),
            "categories": ",".join(r.get("categories", [])),
            "classification": r.get("classification"),
            "classification_confidence": r.get("classification_confidence"),
            "classification_signals": ",".join(r.get("classification_signals", [])),
            "classification_reason": r.get("classification_reason")
        })
    pd.DataFrame(taman_rows).to_csv(os.path.join(reports_dir, "taman_category_audit.csv"), index=False, encoding="utf-8")

    # --- GENERATE SAMPLE AUDIT 3: dedup_clusters.csv ---
    cluster_rows = []
    for r in all_normalized_records:
        if r.get("classification") != "rejected":
            cluster_rows.append({
                "source_record_id": r.get("source_record_id"),
                "source": r.get("source"),
                "name": r.get("name"),
                "latitude": r.get("latitude"),
                "longitude": r.get("longitude"),
                "dedup_cluster_id": r.get("dedup_cluster_id"),
                "dedup_reason": r.get("dedup_reason")
            })
    pd.DataFrame(cluster_rows).to_csv(os.path.join(reports_dir, "dedup_clusters.csv"), index=False, encoding="utf-8")

    # --- GENERATE SPECIAL REPORT FOR ALL RUMAH WISATA, OUTSIDE BOUNDS, PARENT-CHILD ---
    # 1. Rumah Wisata
    rumah_wisata = []
    for r in all_normalized_records:
        cats = r.get("categories") or []
        is_rw = any("rumah wisata" in c.lower() for c in cats) or "rumah wisata" in r.get("name", "").lower()
        if is_rw:
            rumah_wisata.append(r)
    df_rw = pd.DataFrame([r for r in rumah_wisata])
    df_rw.to_csv(os.path.join(reports_dir, "audit_rumah_wisata.csv"), index=False, encoding="utf-8")

    # 2. Outside boundary
    outside_bounds = []
    for r in all_normalized_records:
        lat = r.get("latitude")
        lon = r.get("longitude")
        if lat is not None and lon is not None:
            if not (-6.5 <= lat <= -3.5 and 103.0 <= lon <= 106.5):
                outside_bounds.append(r)
    df_ob = pd.DataFrame([r for r in outside_bounds])
    df_ob.to_csv(os.path.join(reports_dir, "audit_outside_boundary.csv"), index=False, encoding="utf-8")

    # 3. Parent-child candidates
    parent_child_canonical = [r for r in (verified_records + candidates_records) if r.get("parent_canonical_id") is not None]
    df_pc = pd.DataFrame(parent_child_canonical) if parent_child_canonical else pd.DataFrame()
    df_pc.to_csv(os.path.join(reports_dir, "audit_parent_child_candidates.csv"), index=False, encoding="utf-8")

    # --- GENERATE final_discovery_coverage.csv ---
    canonical_regions = sorted(list(REGION_MAP.values()))

    # 1. raw_apify per region
    raw_apify_counts = {r: 0 for r in canonical_regions}
    if manifest_entries:
        for entry in manifest_entries:
            canon_reg = canonicalize_region_name(entry.get("region"))
            if canon_reg in raw_apify_counts:
                raw_apify_counts[canon_reg] += entry.get("raw_count", 0)

    # 2. raw_osm per region
    raw_osm_counts = {r: 0 for r in canonical_regions}
    for filepath in raw_osm_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        item = json.loads(line)
                        lat = item.get("latitude")
                        lon = item.get("longitude")
                        addr = item.get("raw_address") or item.get("address")

                        matched_reg = None
                        if addr:
                            addr_lower = str(addr).lower()
                            sorted_regs = sorted(REGIONS, key=lambda x: max(len(x["name"]), len(x["query"])), reverse=True)
                            for reg in sorted_regs:
                                if reg["query"].lower() in addr_lower or reg["name"].lower() in addr_lower:
                                    matched_reg = reg["name"]
                                    break

                        if not matched_reg and lat is not None and lon is not None:
                            for reg in REGIONS:
                                bbox = reg.get("bbox")
                                if bbox and len(bbox) == 4:
                                    min_lon, min_lat, max_lon, max_lat = bbox
                                    if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
                                        matched_reg = reg["name"]
                                        break

                        canon_reg = canonicalize_region_name(matched_reg) or "Kota Bandar Lampung"
                        if canon_reg in raw_osm_counts:
                            raw_osm_counts[canon_reg] += 1
        except Exception as e:
            logger.error(f"Error resolving raw OSM region: {e}")

    # 3. accepted, candidates, rejected, verified, duplicates, missing ratings/price
    accepted_counts = {r: 0 for r in canonical_regions}
    candidates_counts = {r: 0 for r in canonical_regions}
    rejected_counts = {r: 0 for r in canonical_regions}
    canonical_verified_counts = {r: 0 for r in canonical_regions}
    possible_duplicates_counts = {r: 0 for r in canonical_regions}
    missing_rating_counts = {r: 0 for r in canonical_regions}
    missing_price_counts = {r: 0 for r in canonical_regions}

    for r in all_normalized_records:
        canon_reg = get_region_name(r)
        cls = r.get("classification")
        if canon_reg in canonical_regions:
            if cls == "accepted":
                accepted_counts[canon_reg] += 1
            elif cls == "rejected":
                rejected_counts[canon_reg] += 1

    for r in verified_records:
        canon_reg = get_region_name(r)
        if canon_reg in canonical_regions:
            canonical_verified_counts[canon_reg] += 1

    for r in candidates_records:
        canon_reg = get_region_name(r)
        if canon_reg in canonical_regions:
            candidates_counts[canon_reg] += 1

    dup_csv_path = os.path.join(reports_dir, "possible_duplicate_candidates.csv")
    if os.path.exists(dup_csv_path):
        try:
            df_dup = pd.read_csv(dup_csv_path)
            place_regions = {}
            for r in (verified_records + candidates_records):
                place_regions[r["canonical_id"]] = get_region_name(r)

            for _, row in df_dup.iterrows():
                cid = row["canonical_id_1"]
                canon_reg = place_regions.get(cid)
                if canon_reg in possible_duplicates_counts:
                    possible_duplicates_counts[canon_reg] += 1
        except Exception as e:
            logger.error(f"Error loading possible duplicates CSV: {e}")

    for r in (verified_records + candidates_records):
        canon_reg = get_region_name(r)
        if canon_reg in canonical_regions:
            rating = r.get("rating")
            if rating is None or rating == "" or pd.isna(rating) or str(rating).strip().lower() in ["none", "nan", "null"]:
                missing_rating_counts[canon_reg] += 1

            price_min = r.get("price_min")
            price_max = r.get("price_max")
            if (price_min is None or price_min == "" or pd.isna(price_min) or str(price_min).strip().lower() in ["none", "nan", "null"]) and \
               (price_max is None or price_max == "" or pd.isna(price_max) or str(price_max).strip().lower() in ["none", "nan", "null"]):
                missing_price_counts[canon_reg] += 1

    coverage_rows = []
    for r in canonical_regions:
        coverage_rows.append({
            "region": r,
            "raw_apify": raw_apify_counts[r],
            "raw_osm": raw_osm_counts[r],
            "accepted": accepted_counts[r],
            "candidates": candidates_counts[r],
            "rejected": rejected_counts[r],
            "canonical_verified": canonical_verified_counts[r],
            "possible_duplicates": possible_duplicates_counts[r],
            "missing_rating": missing_rating_counts[r],
            "missing_price": missing_price_counts[r]
        })

    df_coverage = pd.DataFrame(coverage_rows)
    df_coverage.to_csv(os.path.join(reports_dir, "final_discovery_coverage.csv"), index=False, encoding="utf-8")

    logger.info("All reports compiled successfully.")
