import os
import json
import re
import logging
from datetime import datetime, timezone
import pandas as pd
from typing import Optional, List, Dict, Tuple

logger = logging.getLogger("scraper.enrichment.pilot")

TARGET_CATEGORIES = [
    "nature", "beach", "island", "mountain", "hill", "waterfall", "lake", "river", "forest", 
    "camping", "park", "recreation", "waterpark", "culture", "history", "museum", "religious", 
    "education", "agrotourism", "family", "other"
]

def is_real_website(url: Optional[str]) -> bool:
    if not url or pd.isna(url):
        return False
    u = str(url).strip().lower()
    if not u:
        return False
    return not any(x in u for x in ["google.com/maps", "openstreetmap.org", "google.co.id/maps"])

def get_proportional_allocation(counts: Dict[str, int], total_to_allocate: int, regions_list: List[str]) -> Dict[str, int]:
    total_weight = sum(counts[r] for r in regions_list)
    if total_weight == 0:
        return {r: 0 for r in regions_list}
    
    allocations = {}
    allocated_sum = 0
    # Initial integer allocation (round down)
    for r in regions_list:
        val = int(counts[r] / total_weight * total_to_allocate)
        allocations[r] = val
        allocated_sum += val
        
    # Largest remainder method to distribute remainder
    remainder = total_to_allocate - allocated_sum
    if remainder > 0:
        fractionals = [
            (counts[r] / total_weight * total_to_allocate - allocations[r], r)
            for r in regions_list
        ]
        fractionals.sort(reverse=True, key=lambda x: x[0])
        for i in range(remainder):
            allocations[fractionals[i][1]] += 1
            
    return allocations

def select_pilot_places(
    input_path: str = "data/canonical/attractions_master_verified.jsonl",
    sources_path: str = "data/canonical/attraction_sources.parquet",
    normalized_path: str = "data/normalized/all_normalized.jsonl",
    possible_dup_path: str = "reports/possible_duplicate_candidates.csv",
    size: int = 300,
    seed: int = 42,
    min_per_region: int = 10,
    max_region_share: float = 0.15,
    include_special: bool = True
) -> pd.DataFrame:
    # 1. Load data
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if not os.path.exists(sources_path):
        raise FileNotFoundError(f"Sources mapping not found: {sources_path}")
    if not os.path.exists(normalized_path):
        raise FileNotFoundError(f"Normalized source records not found: {normalized_path}")

    # Read verified attractions
    if input_path.endswith(".parquet"):
        df_verified = pd.read_parquet(input_path)
    else:
        # Read JSONL
        records = []
        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        df_verified = pd.DataFrame(records)

    if len(df_verified) < size:
        raise ValueError(f"Requested size {size} is larger than verified dataset count {len(df_verified)}")

    # Read sources map
    df_src = pd.read_parquet(sources_path)

    # Read normalized source details
    norm_records = {}
    with open(normalized_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                norm_records[item["source_record_id"]] = item

    # 2. Resolve source-level details (preferred Apify source)
    google_place_ids = []
    source_place_ids = []
    source_urls = []
    
    for _, row in df_verified.iterrows():
        cid = row["canonical_id"]
        mapped_srcs = df_src[df_src["canonical_id"] == cid]["source_record_id"].tolist()
        
        # Look for Apify record
        apify_rec = None
        osm_rec = None
        for s in mapped_srcs:
            if s in norm_records:
                r_details = norm_records[s]
                if r_details.get("source") == "apify_google_maps":
                    apify_rec = r_details
                    break
                elif r_details.get("source") == "osm":
                    osm_rec = r_details
                    
        if apify_rec:
            google_place_ids.append(apify_rec["source_place_id"])
            source_place_ids.append(apify_rec["source_place_id"])
            source_urls.append(apify_rec.get("source_url") or "")
        elif osm_rec:
            google_place_ids.append(None)
            source_place_ids.append(osm_rec["source_place_id"])
            source_urls.append(osm_rec.get("source_url") or "")
        else:
            google_place_ids.append(None)
            source_place_ids.append(None)
            source_urls.append(None)

    df_verified["google_place_id"] = google_place_ids
    df_verified["source_place_id"] = source_place_ids
    df_verified["source_url"] = source_urls

    # 3. Add segmentations and flags
    # rating_segment
    def get_rating_seg(r):
        if pd.isna(r) or r is None or str(r).strip().lower() in ["none", "nan", "null"]:
            return "empty"
        val = float(r)
        if val >= 4.5: return "high"
        if val >= 4.0: return "medium"
        return "low"
        
    # review_count_segment
    def get_review_seg(c):
        if pd.isna(c) or c is None or str(c).strip().lower() in ["none", "nan", "null"]:
            return "no_review"
        val = int(c)
        if val >= 1000: return "popular"
        if val >= 100: return "medium"
        if val >= 1: return "low"
        return "no_review"

    df_verified["rating_segment"] = df_verified["rating"].apply(get_rating_seg)
    df_verified["review_count_segment"] = df_verified["review_count"].apply(get_review_seg)
    df_verified["has_website"] = df_verified["website"].apply(is_real_website)
    df_verified["has_google_place_id"] = df_verified["google_place_id"].notna() & (df_verified["google_place_id"] != "")

    # 4. Calculate region allocations using Hamilton method
    regions_counts = df_verified["city_regency"].value_counts().to_dict()
    all_regions = sorted(list(regions_counts.keys()))
    
    # Cap Bandar Lampung at max_region_share (e.g. 15% of 300 = 45)
    max_bl_quota = int(size * max_region_share) # 45
    
    # Calculate allocations
    alloc = {r: min_per_region for r in all_regions}
    remaining_size = size - len(all_regions) * min_per_region # 300 - 150 = 150
    
    # Check Bandar Lampung share
    bl_region = "Kota Bandar Lampung"
    bl_proportional_pool = remaining_size
    other_regions = [r for r in all_regions if r != bl_region]
    
    # Determine Bandar Lampung's initial proportional share
    bl_share_raw = int(regions_counts.get(bl_region, 0) / sum(regions_counts.values()) * remaining_size)
    if min_per_region + bl_share_raw > max_bl_quota:
        # Cap Bandar Lampung
        alloc[bl_region] = max_bl_quota
        allocated_bl = max_bl_quota - min_per_region
        remaining_for_others = remaining_size - allocated_bl
        
        # Distribute remaining to other 14 regions
        other_allocations = get_proportional_allocation(regions_counts, remaining_for_others, other_regions)
        for r in other_regions:
            alloc[r] += other_allocations[r]
    else:
        # standard allocation to all 15 regions
        allocations = get_proportional_allocation(regions_counts, remaining_size, all_regions)
        for r in all_regions:
            alloc[r] += allocations[r]
            
    # Verify sum of allocations is exactly 'size'
    assert sum(alloc.values()) == size, f"Sum of allocations {sum(alloc.values())} does not match target {size}"

    # 5. Build special pools
    dup_pool = []
    if include_special and os.path.exists(possible_dup_path):
        df_dup = pd.read_csv(possible_dup_path)
        dup_cids = []
        for _, row in df_dup.iterrows():
            c1 = row.get("canonical_id_1")
            c2 = row.get("canonical_id_2")
            if c1: dup_cids.append(str(c1))
            if c2: dup_cids.append(str(c2))
        dup_pool = sorted(list(set(dup_cids)))
        dup_pool = [c for c in dup_pool if c in df_verified["canonical_id"].values][:20]

    pc_pool = []
    if include_special:
        pc_df = df_verified[df_verified["parent_canonical_id"].notna() & (df_verified["parent_canonical_id"] != "")].sort_values(by="canonical_id")
        pc_pool = pc_df["canonical_id"].head(20).tolist()

    low_conf_pool = []
    if include_special:
        lc_df = df_verified.sort_values(by=["classification_confidence", "canonical_id"], ascending=[True, True])
        low_conf_pool = lc_df["canonical_id"].head(20).tolist()

    pop_pool = []
    if include_special:
        pop_df = df_verified.sort_values(by=["review_count", "canonical_id"], ascending=[False, True])
        pop_pool = pop_df["canonical_id"].head(20).tolist()

    no_rating_pool = []
    if include_special:
        nr_df = df_verified[df_verified["rating"].isna() | (df_verified["rating"] == "")].sort_values(by="canonical_id")
        no_rating_pool = nr_df["canonical_id"].head(20).tolist()

    no_web_pool = []
    if include_special:
        nw_df = df_verified[~df_verified["website"].apply(is_real_website)].sort_values(by="canonical_id")
        no_web_pool = nw_df["canonical_id"].head(20).tolist()

    # Priority sort & unique special candidates
    special_candidates = []
    special_reasons = {}
    
    # List of pools with their descriptions
    pools = [
        (dup_pool, "possible_duplicate"),
        (pc_pool, "parent_child"),
        (low_conf_pool, "low_confidence"),
        (pop_pool, "popular"),
        (no_rating_pool, "no_rating"),
        (no_web_pool, "no_website")
    ]
    
    for pool, reason in pools:
        for cid in pool:
            if cid not in special_reasons:
                special_reasons[cid] = reason
                special_candidates.append(cid)

    # 6. Perform selection
    pilot_cids = set()
    pilot_reasons = {}
    region_selected_counts = {r: 0 for r in all_regions}

    # Pass A: Add special candidates respecting region quotas
    for cid in special_candidates:
        row = df_verified[df_verified["canonical_id"] == cid].iloc[0]
        reg = row["city_regency"]
        if region_selected_counts[reg] < alloc[reg]:
            pilot_cids.add(cid)
            pilot_reasons[cid] = special_reasons[cid]
            region_selected_counts[reg] += 1

    # Pass B: Cover rare categories
    represented_categories = {df_verified[df_verified["canonical_id"] == cid].iloc[0]["normalized_category"] for cid in pilot_cids}
    unrepresented_cats = [c for c in TARGET_CATEGORIES if c not in represented_categories]
    
    remaining_pool = df_verified[~df_verified["canonical_id"].isin(pilot_cids)].sort_values(by="canonical_id")
    for cat in unrepresented_cats:
        cat_records = remaining_pool[remaining_pool["normalized_category"] == cat]
        if not cat_records.empty:
            for _, row in cat_records.iterrows():
                reg = row["city_regency"]
                cid = row["canonical_id"]
                if region_selected_counts[reg] < alloc[reg]:
                    pilot_cids.add(cid)
                    pilot_reasons[cid] = f"rare_category_{cat}"
                    region_selected_counts[reg] += 1
                    represented_categories.add(cat)
                    break

    # Pass C: Fill remaining quotas using deterministic random sampling per region
    remaining_pool = df_verified[~df_verified["canonical_id"].isin(pilot_cids)].sort_values(by="canonical_id")
    for reg in all_regions:
        quota_left = alloc[reg] - region_selected_counts[reg]
        if quota_left > 0:
            reg_pool = remaining_pool[remaining_pool["city_regency"] == reg]
            if len(reg_pool) < quota_left:
                raise ValueError(f"Not enough records left in region {reg} to fill quota: needed {quota_left}, available {len(reg_pool)}")
            
            # Sample deterministically
            reg_sampled = reg_pool.sample(n=quota_left, random_state=seed)
            for _, row in reg_sampled.iterrows():
                cid = row["canonical_id"]
                pilot_cids.add(cid)
                pilot_reasons[cid] = "random_geographic_representation"
                region_selected_counts[reg] += 1

    # Verify total count is exactly size
    assert len(pilot_cids) == size, f"Final pilot size {len(pilot_cids)} does not match requested size {size}"

    # Build final DataFrame
    df_pilot = df_verified[df_verified["canonical_id"].isin(pilot_cids)].copy()
    # Map back original region and category column names to requested output names
    df_pilot["region"] = df_pilot["city_regency"]
    df_pilot["primary_category"] = df_pilot["normalized_category"]
    df_pilot["selection_reason"] = df_pilot["canonical_id"].map(pilot_reasons)
    
    # Metadata fields
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    df_pilot["selected_at"] = now_str
    df_pilot["pilot_batch"] = "enrichment_pilot_300_v1"
    df_pilot["pilot_version"] = "v1"

    # Select and order required columns
    ordered_cols = [
        "canonical_id", "name", "region", "primary_category", "category_tags", "latitude", "longitude",
        "rating", "review_count", "website", "source_url", "google_place_id", "source_place_id",
        "source_count", "classification_confidence", "rating_segment", "review_count_segment",
        "has_website", "has_google_place_id", "selection_reason", "selected_at", "pilot_batch", "pilot_version"
    ]
    df_pilot = df_pilot[ordered_cols]
    return df_pilot

def write_enrichment_schemas(schema_dir: str = "data/enrichment/schema"):
    os.makedirs(schema_dir, exist_ok=True)
    
    # 1. prices.csv
    prices_cols = [
        "price_id", "canonical_id", "price_type", "amount_min", "amount_max", "currency", 
        "applies_to", "unit", "valid_day_type", "source_name", "source_url", "observed_at", 
        "effective_date", "confidence", "verification_status", "notes"
    ]
    pd.DataFrame(columns=prices_cols).to_csv(os.path.join(schema_dir, "prices.csv"), index=False)
    
    # 2. reviews.csv
    reviews_cols = [
        "review_id", "canonical_id", "source", "source_place_id", "rating", "review_text", 
        "review_date", "language", "sentiment_bucket", "sentiment_method", "review_url", 
        "collected_at", "is_duplicate", "content_hash"
    ]
    pd.DataFrame(columns=reviews_cols).to_csv(os.path.join(schema_dir, "reviews.csv"), index=False)
    
    # 3. facilities.csv
    facilities_cols = [
        "facility_id", "canonical_id", "facility_type", "facility_name", "availability", 
        "source_name", "source_url", "observed_at", "confidence", "notes"
    ]
    pd.DataFrame(columns=facilities_cols).to_csv(os.path.join(schema_dir, "facilities.csv"), index=False)
    
    # 4. opening_hours.csv
    oh_cols = [
        "opening_hours_id", "canonical_id", "day_of_week", "open_time", "close_time", 
        "is_24_hours", "is_closed", "source_name", "source_url", "observed_at", "notes"
    ]
    pd.DataFrame(columns=oh_cols).to_csv(os.path.join(schema_dir, "opening_hours.csv"), index=False)
    
    # 5. source_provenance.csv
    prov_cols = [
        "provenance_id", "canonical_id", "field_name", "field_value", "source_name", 
        "source_url", "collected_at", "observed_at", "confidence", "verification_status"
    ]
    pd.DataFrame(columns=prov_cols).to_csv(os.path.join(schema_dir, "source_provenance.csv"), index=False)
    
    # 6. failed_enrichment.csv
    failed_cols = [
        "canonical_id", "enrichment_type", "source", "error_type", "error_message", 
        "attempted_at", "retryable", "retry_count", "next_action"
    ]
    pd.DataFrame(columns=failed_cols).to_csv(os.path.join(schema_dir, "failed_enrichment.csv"), index=False)
    
    logger.info("Enrichment schema templates written successfully.")

def write_reports(
    df_pilot: pd.DataFrame,
    df_verified: pd.DataFrame,
    reports_dir: str = "reports"
):
    os.makedirs(reports_dir, exist_ok=True)
    
    total_verified = len(df_verified)
    total_pilot = len(df_pilot)
    
    # 1. Region coverage
    reg_verified = df_verified["city_regency"].value_counts().to_dict()
    reg_pilot = df_pilot["region"].value_counts().to_dict()
    regions = sorted(list(reg_verified.keys()))
    
    reg_rows = []
    for r in regions:
        reg_rows.append({
            "region": r,
            "pilot_count": reg_pilot.get(r, 0),
            "verified_count": reg_verified.get(r, 0)
        })
    df_reg = pd.DataFrame(reg_rows)
    df_reg.to_csv(os.path.join(reports_dir, "enrichment_pilot_region_coverage.csv"), index=False, encoding="utf-8")
    
    # 2. Category coverage
    cat_verified = df_verified["normalized_category"].value_counts().to_dict()
    cat_pilot = df_pilot["primary_category"].value_counts().to_dict()
    cats = sorted(list(set(TARGET_CATEGORIES).union(cat_verified.keys())))
    
    cat_rows = []
    for c in cats:
        cat_rows.append({
            "category": c,
            "pilot_count": cat_pilot.get(c, 0),
            "verified_count": cat_verified.get(c, 0)
        })
    df_cat = pd.DataFrame(cat_rows)
    df_cat.to_csv(os.path.join(reports_dir, "enrichment_pilot_category_coverage.csv"), index=False, encoding="utf-8")
    
    # 3. Distribution statistics
    dist_rows = []
    
    # Rating segments
    for seg in ["high", "medium", "low", "empty"]:
        cnt = sum(df_pilot["rating_segment"] == seg)
        dist_rows.append({
            "dimension": "rating",
            "segment": seg,
            "count": cnt,
            "percentage": cnt / total_pilot * 100
        })
        
    # Review count segments
    for seg in ["popular", "medium", "low", "no_review"]:
        cnt = sum(df_pilot["review_count_segment"] == seg)
        dist_rows.append({
            "dimension": "review_count",
            "segment": seg,
            "count": cnt,
            "percentage": cnt / total_pilot * 100
        })
        
    # Website presence
    for seg, has_web in [("has_website", True), ("no_website", False)]:
        cnt = sum(df_pilot["has_website"] == has_web)
        dist_rows.append({
            "dimension": "website",
            "segment": seg,
            "count": cnt,
            "percentage": cnt / total_pilot * 100
        })
        
    # Google Place ID presence
    for seg, has_g in [("has_google_place_id", True), ("no_google_place_id", False)]:
        cnt = sum(df_pilot["has_google_place_id"] == has_g)
        dist_rows.append({
            "dimension": "google_place_id",
            "segment": seg,
            "count": cnt,
            "percentage": cnt / total_pilot * 100
        })
        
    df_dist = pd.DataFrame(dist_rows)
    df_dist.to_csv(os.path.join(reports_dir, "enrichment_pilot_distribution.csv"), index=False, encoding="utf-8")
    
    # 4. Missing fields analysis
    missing_fields = ["website", "google_place_id", "rating", "review_count", "latitude", "longitude"]
    missing_rows = []
    for f in missing_fields:
        if f == "google_place_id":
            missing_cnt = sum(df_pilot["google_place_id"].isna() | (df_pilot["google_place_id"] == ""))
        elif f == "website":
            # Check real website missingness
            missing_cnt = sum(~df_pilot["has_website"])
        else:
            missing_cnt = sum(df_pilot[f].isna() | (df_pilot[f] == ""))
            
        missing_rows.append({
            "field_name": f,
            "missing_count_in_pilot": missing_cnt,
            "missing_percentage_in_pilot": missing_cnt / total_pilot * 100
        })
    df_missing = pd.DataFrame(missing_rows)
    df_missing.to_csv(os.path.join(reports_dir, "enrichment_pilot_missing_fields.csv"), index=False, encoding="utf-8")
    
    # 5. Summary Markdown report
    with open(os.path.join(reports_dir, "enrichment_pilot_summary.md"), "w", encoding="utf-8") as f:
        f.write("# Lampung Tourism Enrichment Pilot Summary Report\n\n")
        f.write(f"Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n")
        
        f.write("## Overview Metrics\n")
        f.write(f"- **Total Verified Attractions**: {total_verified}\n")
        f.write(f"- **Selected Pilot Attractions**: {total_pilot}\n")
        f.write(f"- **Target Pilot Size Met**: {'YES' if total_pilot == 300 else 'NO'}\n")
        f.write(f"- **All 15 Regions Represented**: {'YES' if len(df_pilot['region'].unique()) == 15 else 'NO'}\n\n")
        
        f.write("## Special Samples Included\n")
        f.write(f"- **Possible Duplicate Candidates**: {sum(df_pilot['selection_reason'] == 'possible_duplicate')}\n")
        f.write(f"- **Parent-Child Candidates**: {sum(df_pilot['selection_reason'] == 'parent_child')}\n")
        f.write(f"- **Low Classification Confidence**: {sum(df_pilot['selection_reason'] == 'low_confidence')}\n")
        f.write(f"- **Popular Places**: {sum(df_pilot['selection_reason'] == 'popular')}\n")
        f.write(f"- **No Rating Places**: {sum(df_pilot['selection_reason'] == 'no_rating')}\n")
        f.write(f"- **No Website Places**: {sum(df_pilot['selection_reason'] == 'no_website')}\n\n")
        
        f.write("## Region Distribution Table\n\n")
        f.write("| Region | Pilot Count | Verified Count | Pilot Share (%)\n")
        f.write("|---|---|---|---|\n")
        for _, row in df_reg.iterrows():
            f.write(f"| {row['region']} | {row['pilot_count']} | {row['verified_count']} | {row['pilot_count']/total_pilot*100:.2f}% |\n")
        f.write("\n")
        
        f.write("## Category Distribution Table\n\n")
        f.write("| Category | Pilot Count | Verified Count | Pilot Share (%)\n")
        f.write("|---|---|---|---|\n")
        for _, row in df_cat.iterrows():
            f.write(f"| {row['category']} | {row['pilot_count']} | {row['verified_count']} | {row['pilot_count']/total_pilot*100:.2f}% |\n")
        f.write("\n")
        
        f.write("## Dimension Segmentations\n\n")
        f.write("| Dimension | Segment | Pilot Count | Percentage (%)\n")
        f.write("|---|---|---|---|\n")
        for _, row in df_dist.iterrows():
            f.write(f"| {row['dimension']} | {row['segment']} | {row['count']} | {row['percentage']:.2f}% |\n")
        f.write("\n")
        
        f.write("## Missing Fields in Pilot\n\n")
        f.write("| Field Name | Missing Count | Missing Percentage (%)\n")
        f.write("|---|---|---|\n")
        for _, row in df_missing.iterrows():
            f.write(f"| {row['field_name']} | {row['missing_count_in_pilot']} | {row['missing_percentage_in_pilot']:.2f}% |\n")
        f.write("\n")

    logger.info("Validation reports compiled successfully.")
