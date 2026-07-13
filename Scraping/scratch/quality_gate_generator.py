import os
import json
import random
import pandas as pd
from datetime import datetime, timezone
from typing import List, Dict, Any

def run_quality_gate():
    # Set seed for reproducibility
    random.seed(42)
    
    # 1. Load Mappings
    mappings_path = "data/canonical/attraction_sources.parquet"
    df_maps = pd.DataFrame()
    if os.path.exists(mappings_path):
        df_maps = pd.read_parquet(mappings_path)
    
    # Create cluster maps
    canonical_to_sources = {}
    source_to_canonical = {}
    if not df_maps.empty:
        for _, row in df_maps.iterrows():
            cid = row["canonical_id"]
            sid = row["source_record_id"]
            if cid not in canonical_to_sources:
                canonical_to_sources[cid] = []
            canonical_to_sources[cid].append(sid)
            source_to_canonical[sid] = cid
        
    # 2. Load Normalized source urls and place IDs lookup
    source_url_lookup = {}
    google_place_ids = set()
    all_normalized_path = "data/normalized/all_normalized.jsonl"
    if os.path.exists(all_normalized_path):
        with open(all_normalized_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    sid = item.get("source_record_id")
                    url = item.get("source_url") or item.get("website")
                    if sid:
                        source_url_lookup[sid] = url
                    if item.get("source") == "apify_google_maps" and item.get("source_place_id"):
                        google_place_ids.add(item.get("source_place_id"))
                        
    # Helper to get source url for a canonical id
    def get_source_url(cid: str, fallback_website: str) -> str:
        sids = canonical_to_sources.get(cid, [])
        for sid in sids:
            url = source_url_lookup.get(sid)
            if url:
                return url
        return fallback_website or ""

    # 3. Load Canonical Places (Verified + Candidates)
    verified = []
    verified_path = "data/canonical/attractions_master_verified.jsonl"
    if os.path.exists(verified_path):
        with open(verified_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    verified.append(json.loads(line))
                    
    candidates = []
    candidates_path = "data/canonical/attractions_candidates.jsonl"
    if os.path.exists(candidates_path):
        with open(candidates_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    candidates.append(json.loads(line))
                    
    all_canonical = verified + candidates
    
    # 4. Implement Selection Rules
    selected_ids = set()
    
    # Rule 1: 50 attractions_master_verified with lowest confidence
    verified_sorted = sorted(verified, key=lambda x: (x.get("classification_confidence", 1.0), x.get("canonical_id")))
    rule1_ids = [x["canonical_id"] for x in verified_sorted[:50]]
    selected_ids.update(rule1_ids)
    
    # Rule 2: 30 random samples from each region (Bandar Lampung, Pesawaran, Tanggamus)
    regions = {
        "bandar_lampung": ["Kota Bandar Lampung", "bandar_lampung"],
        "pesawaran": ["Kabupaten Pesawaran", "pesawaran"],
        "tanggamus": ["Kabupaten Tanggamus", "tanggamus"]
    }
    
    rule2_breakdown = {}
    for key, names in regions.items():
        reg_places = []
        for x in verified:
            city = x.get("city_regency") or ""
            q_reg = x.get("query_region") or ""
            if any(name.lower() in city.lower() or name.lower() in q_reg.lower() for name in names):
                reg_places.append(x)
                
        sample_size = min(30, len(reg_places))
        sampled = random.sample(reg_places, sample_size) if reg_places else []
        rule2_ids = [x["canonical_id"] for x in sampled]
        selected_ids.update(rule2_ids)
        rule2_breakdown[key] = len(rule2_ids)
        
    # Rule 3: Max 30 records from categories: Taman, Rumah wisata, Area Mendaki, Tujuan Wisata
    category_rules = {
        "Taman": lambda x: x.get("normalized_category") == "park" or "taman" in (x.get("name") or "").lower() or "park" in (x.get("name") or "").lower(),
        "Rumah wisata": lambda x: "rumah wisata" in (x.get("name") or "").lower() or any("rumah wisata" in str(tag).lower() for tag in x.get("category_tags", [])),
        "Area Mendaki": lambda x: x.get("normalized_category") in ["mountain", "hill"] or any(tag in x.get("category_tags", []) for tag in ["mountain", "hill", "hiking"]) or any(w in (x.get("name") or "").lower() for w in ["gunung", "bukit", "mendaki", "hiking", "peak"]),
        "Tujuan Wisata": lambda x: x.get("normalized_category") in ["recreation", "nature"] or any(tag in x.get("category_tags", []) for tag in ["recreation", "nature"]) or "wisata" in (x.get("name") or "").lower()
    }
    
    rule3_breakdown = {}
    for cat_name, cond in category_rules.items():
        matched = [x for x in all_canonical if cond(x)]
        sample_size = min(30, len(matched))
        sampled = random.sample(matched, sample_size) if matched else []
        rule3_ids = [x["canonical_id"] for x in sampled]
        selected_ids.update(rule3_ids)
        rule3_breakdown[cat_name] = len(rule3_ids)
        
    # Rule 4: All cross-source matches (OSM and Apify)
    cross_source_ids = []
    for cid, sources in canonical_to_sources.items():
        has_osm = any("osm_" in s for s in sources)
        has_apify = any("apify_google_maps_" in s for s in sources)
        if has_osm and has_apify:
            cross_source_ids.append(cid)
    selected_ids.update(cross_source_ids)
    
    # Rule 5: All parent-child candidates
    parent_child_ids = [x["canonical_id"] for x in all_canonical if x.get("parent_canonical_id") is not None]
    selected_ids.update(parent_child_ids)
    
    # Rule 6: All clusters with size > 3
    large_cluster_ids = []
    for cid, sources in canonical_to_sources.items():
        if len(sources) > 3:
            large_cluster_ids.append(cid)
    selected_ids.update(large_cluster_ids)
    
    # 5. Build Quality Gate Sample List
    sample_rows = []
    for x in all_canonical:
        cid = x["canonical_id"]
        if cid in selected_ids:
            url = get_source_url(cid, x.get("website"))
            sample_rows.append({
                "canonical_id": cid,
                "name": x.get("name"),
                "region": x.get("city_regency") or x.get("query_region") or "Unknown",
                "primary_category": x.get("normalized_category"),
                "source_count": x.get("source_count", 1),
                "rating": x.get("rating"),
                "review_count": x.get("review_count"),
                "classification_confidence": x.get("classification_confidence", 1.0),
                "classification_reason": x.get("classification_reason"),
                "source_url": url,
                "audit_status": "PENDING",
                "audit_notes": "Pending manual validation"
            })
            
    # Save reports/quality_gate_sample.csv
    reports_dir = "reports"
    os.makedirs(reports_dir, exist_ok=True)
    df_sample = pd.DataFrame(sample_rows)
    if not df_sample.empty:
        df_sample = df_sample.sort_values(by=["classification_confidence", "name"], ascending=[True, True])
    df_sample.to_csv(os.path.join(reports_dir, "quality_gate_sample.csv"), index=False, encoding="utf-8")
    
    # 6. Calculate new requested metrics
    unique_source_count = len(source_to_canonical)
    unique_google_place_id_count = len(google_place_ids)
    
    normalized_count = 0
    if os.path.exists("data/normalized/normalized_attractions.jsonl"):
        with open("data/normalized/normalized_attractions.jsonl", "r", encoding="utf-8") as f:
            normalized_count = sum(1 for line in f if line.strip())
    duplicate_source_record_count = max(0, normalized_count - unique_source_count)
    
    # 7. Generate reports/quality_gate_summary.md
    summary_md = f"""# Manual Quality Gate Audit Summary (Strict Deduplication & Relationship Constraints)
 
Generated on: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}
 
## 1. Quality Gate Sampling Statistics
 
We extracted a manual validation sample size of **{len(sample_rows)}** canonical attractions from the total canonical dataset of **{len(all_canonical)}** records (**{len(verified)}** verified, **{len(candidates)}** candidates).
 
### Sampling Breakdown by Rule:
* **Rule 1 (Lowest Confidence Master Verified)**: Selected **{len(rule1_ids)}** records
* **Rule 2 (Regional Samples - Max 30/region)**:
  - *Bandar Lampung*: {rule2_breakdown.get('bandar_lampung', 0)}
  - *Pesawaran*: {rule2_breakdown.get('pesawaran', 0)}
  - *Tanggamus*: {rule2_breakdown.get('tanggamus', 0)}
* **Rule 3 (Category Samples - Max 30/category)**:
  - *Taman*: {rule3_breakdown.get('Taman', 0)}
  - *Rumah wisata*: {rule3_breakdown.get('Rumah wisata', 0)}
  - *Area Mendaki*: {rule3_breakdown.get('Area Mendaki', 0)}
  - *Tujuan Wisata*: {rule3_breakdown.get('Tujuan Wisata', 0)}
* **Rule 4 (Cross-Source Matches)**: Selected **{len(cross_source_ids)}** records
* **Rule 5 (Parent-Child Candidates)**: Selected **{len(parent_child_ids)}** records
* **Rule 6 (Large Clusters > 3 members)**: Selected **{len(large_cluster_ids)}** records
 
---
 
## 2. Comparison Dashboard: Before vs. After Strict Dedup & Relationships
 
Below is a comparison of clustering metrics before and after the strict matching and deduplication fixes:
 
| Metric | Before Fix (Initial Phase 3) | After Fix (Strict Rules) | Explanation / Status |
| :--- | :---: | :---: | :--- |
| **Total Raw Records** | 2012 | 2012 | Unchanged raw inputs |
| **Unique Normalized Source Records** | - | {unique_source_count} | Unique `source_record_id`s processed |
| **Duplicate Source Records** | 0 | {duplicate_source_record_count} | Duplicate raw entries removed before clustering |
| **Unique Google Place IDs** | - | {unique_google_place_id_count} | Valid Google place IDs |
| **Verified Master Canonical** | 1016 | {len(verified)} | Restructured master verified list |
| **Candidates (Manual Review)** | 240 | {len(candidates)} | Restructured candidate review list |
| **Total Canonical Attractions** | 1256 | {len(all_canonical)} | Clean places count (false-merges resolved) |
| **Large Clusters (> 3 members)** | 35 | {len(large_cluster_ids)} | Overlap resolved by separating Google place IDs |
| **Parent-Child Candidates** | 32 | {len(parent_child_ids)} | Forbidden categories & administrative bounds excluded |

---

## 3. Cross-Source Match Verification

A total of **{len(cross_source_ids)}** cross-source matches were mapped between OSM and Apify Google Maps:

| Canonical ID | Attraction Name | Region | Source Count | Conf. | Reason |
| :--- | :--- | :--- | :---: | :---: | :--- |
"""
    for x in all_canonical:
        cid = x["canonical_id"]
        if cid in cross_source_ids:
            summary_md += f"| `{cid}` | {x['name']} | {x.get('city_regency') or 'Unknown'} | {x.get('source_count')} | {x.get('classification_confidence')} | {x.get('classification_reason')} |\n"
            
    summary_md += f"""
---

## 4. Parent-Child Relationship Validation

A total of **{len(parent_child_ids)}** parent-child hierarchical relations were discovered (e.g. sub-areas inside tourist hubs):

| Child ID | Child Name | Parent ID | Parent Name | Relationship | Region |
| :--- | :--- | :--- | :--- | :--- | :--- |
"""
    for x in all_canonical:
        if x.get("parent_canonical_id") is not None:
            parent_name = next((p["name"] for p in all_canonical if p["canonical_id"] == x["parent_canonical_id"]), "Unknown")
            summary_md += f"| `{x['canonical_id']}` | {x['name']} | `{x['parent_canonical_id']}` | {parent_name} | {x.get('place_relationship')} | {x.get('city_regency') or 'Unknown'} |\n"

    summary_md += f"""
---

## 5. Large Clusters (> 3 Members)

Below are the canonical attraction profiles created from combining more than 3 raw records:

| Canonical ID | Attraction Name | Region | Source Count | Mapped Sources |
| :--- | :--- | :--- | :---: | :--- |
"""
    for x in all_canonical:
        cid = x["canonical_id"]
        if cid in large_cluster_ids:
            sids = canonical_to_sources.get(cid, [])
            summary_md += f"| `{cid}` | {x['name']} | {x.get('city_regency') or 'Unknown'} | {len(sids)} | {', '.join(sids)} |\n"

    # Write summary report
    with open("reports/quality_gate_summary.md", "w", encoding="utf-8") as f:
        f.write(summary_md)
        
    print(f"Successfully generated quality gate sample size: {len(sample_rows)}")

if __name__ == "__main__":
    run_quality_gate()
