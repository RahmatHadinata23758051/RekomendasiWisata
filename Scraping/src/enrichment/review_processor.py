import os
import json
import re
import hashlib
import logging
from datetime import datetime, timezone
import pandas as pd
from typing import List, Dict, Any, Tuple

logger = logging.getLogger("scraper.enrichment.processor")

def compute_content_hash(text: str) -> str:
    cleaned = (text or "").strip()
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()

def normalize_text_for_similarity(text: str) -> str:
    if not text:
        return ""
    # Lowercase, remove non-alphanumeric characters, strip whitespace
    return re.sub(r"[^\w]", "", text.lower().strip())

def parse_date(date_str: Any) -> datetime:
    if not date_str or pd.isna(date_str):
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        # Standard ISO format parsing
        return pd.to_datetime(date_str).to_pydatetime().replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)

def process_and_select_reviews(
    raw_dir: str = "data/enrichment/raw_reviews",
    pilot_csv_path: str = "data/enrichment/pilot/pilot_places.csv",
    manifest_path: str = "data/enrichment/apify_review_inputs/review_batch_manifest.json",
    processed_dir: str = "data/enrichment/processed_reviews",
    final_dir: str = "data/enrichment/final",
    reports_dir: str = "reports"
):
    os.makedirs(processed_dir, exist_ok=True)
    os.makedirs(final_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)
    
    # 1. Load pilot places mapping
    if not os.path.exists(pilot_csv_path):
        raise FileNotFoundError(f"Pilot places not found: {pilot_csv_path}")
    df_pilot = pd.read_csv(pilot_csv_path)
    
    place_id_to_canon = {}
    url_to_canon = {}
    pilot_info = {} # canonical_id -> dict
    
    for _, row in df_pilot.iterrows():
        cid = row["canonical_id"]
        g_id = row["google_place_id"]
        s_url = row["source_url"]
        pilot_info[cid] = {
            "name": row["name"],
            "region": row["region"],
            "google_place_id": g_id,
            "source_url": s_url
        }
        if pd.notna(g_id) and str(g_id).strip() != "":
            place_id_to_canon[str(g_id).strip()] = cid
        if pd.notna(s_url) and str(s_url).strip() != "":
            url_to_canon[str(s_url).strip()] = cid
            
    # 2. Load manifest for fallbacks
    batch_to_canon_map = {} # (batch_id, mode) -> list of cids
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as mf:
            m_data = json.load(mf)
            for b in m_data.get("batches", []):
                batch_to_canon_map[(b["batch_id"], b["mode"])] = b.get("canonical_ids", [])

    # 3. Read raw reviews
    raw_reviews_list = []
    
    # Scan raw_reviews directory recursively or per folder
    for mode in ["positive", "negative", "neutral"]:
        mode_dir = os.path.join(raw_dir, mode)
        if not os.path.exists(mode_dir):
            continue
        for filename in os.listdir(mode_dir):
            if filename.endswith(".json"):
                batch_id = filename.replace(".json", "")
                filepath = os.path.join(mode_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            for r in data:
                                raw_reviews_list.append((r, mode, batch_id))
                        elif isinstance(data, dict):
                            raw_reviews_list.append((data, mode, batch_id))
                except Exception as e:
                    logger.error(f"Failed to load raw review file {filepath}: {e}")
                    
    logger.info(f"Loaded {len(raw_reviews_list)} raw review payloads from disk.")
    
    processed_reviews = []
    unmapped_reviews = []
    empty_text_reviews = []
    
    # 4. Map & Normalize
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    for r, mode, batch_id in raw_reviews_list:
        # Resolve canonical_id
        pid = r.get("placeId") or r.get("googlePlaceId")
        p_url = r.get("placeUrl") or r.get("url")
        
        cid = None
        if pid and str(pid).strip() in place_id_to_canon:
            cid = place_id_to_canon[str(pid).strip()]
        elif p_url and str(p_url).strip() in url_to_canon:
            cid = url_to_canon[str(p_url).strip()]
        else:
            # Fallback to manifest
            cids_in_batch = batch_to_canon_map.get((batch_id, mode), [])
            if len(cids_in_batch) == 1:
                # If only one place in batch, map to it
                cid = cids_in_batch[0]
                
        if not cid:
            unmapped_reviews.append({
                "raw_payload": r,
                "scrape_mode": mode,
                "batch_id": batch_id,
                "reason": f"Could not map placeId '{pid}' or url '{p_url}' to any canonical_id"
            })
            continue
            
        # Normalization
        review_id = r.get("id") or r.get("reviewId")
        if not review_id:
            # Generate unique ID based on hash of text & author
            raw_text = r.get("text") or ""
            author = r.get("authorName") or ""
            review_id = "gen_" + hashlib.md5(f"{raw_text}_{author}".encode("utf-8")).hexdigest()
            
        text = r.get("text") or r.get("reviewText") or ""
        rating_val = r.get("stars") or r.get("rating")
        
        # Rating is float or int, default to 5
        try:
            rating = int(float(rating_val))
        except Exception:
            rating = 5
            
        # Sentiment mapping
        if rating >= 4:
            sentiment = "positive"
        elif rating == 3:
            sentiment = "neutral"
        else:
            sentiment = "negative"
            
        c_hash = compute_content_hash(text)
        
        review_record = {
            "review_id": review_id,
            "canonical_id": cid,
            "source": "google",
            "source_place_id": pid or "",
            "rating": rating,
            "review_text": text,
            "review_date": r.get("publishAt") or r.get("date") or r.get("publishAtDate") or "",
            "language": r.get("language") or "id",
            "sentiment_bucket": sentiment,
            "sentiment_method": "rating_based",
            "review_url": r.get("reviewUrl") or "",
            "collected_at": r.get("collectedAt") or now_str,
            "is_duplicate": False,
            "content_hash": c_hash,
            "scrape_mode": mode,
            "batch_id": batch_id
        }
        
        # Check empty text
        if not text.strip():
            empty_text_reviews.append(review_record)
            
        processed_reviews.append(review_record)

    # Write unmapped reviews
    with open(os.path.join(processed_dir, "reviews_unmapped.jsonl"), "w", encoding="utf-8") as f:
        for r in unmapped_reviews:
            f.write(json.dumps(r) + "\n")
            
    # Write empty text reviews
    df_empty = pd.DataFrame(empty_text_reviews)
    df_empty.to_csv(os.path.join(processed_dir, "reviews_empty_text.csv"), index=False, encoding="utf-8")

    # 5. Deduplication
    # Rules:
    # 1. review_id same
    # 2. canonical_id + content_hash same
    # 3. canonical_id + normalized text very similar (normalized text identical)
    # 4. Rating and text same across different modes
    seen_ids = set()
    seen_hashes = {} # canonical_id -> set of hashes
    seen_norms = {} # canonical_id -> set of normalized texts
    
    unique_reviews = []
    duplicate_reviews = []
    
    # Sort reviews by scrape_mode so deterministic duplicates are identified
    processed_reviews.sort(key=lambda x: (x["canonical_id"], x["review_id"]))
    
    for r in processed_reviews:
        cid = r["canonical_id"]
        rid = r["review_id"]
        c_hash = r["content_hash"]
        norm_txt = normalize_text_for_similarity(r["review_text"])
        
        is_dup = False
        
        if rid in seen_ids:
            is_dup = True
        elif cid in seen_hashes and c_hash in seen_hashes[cid]:
            is_dup = True
        elif cid in seen_norms and norm_txt != "" and norm_txt in seen_norms[cid]:
            is_dup = True
            
        if is_dup:
            r["is_duplicate"] = True
            duplicate_reviews.append(r)
        else:
            seen_ids.add(rid)
            if cid not in seen_hashes:
                seen_hashes[cid] = set()
            seen_hashes[cid].add(c_hash)
            if cid not in seen_norms:
                seen_norms[cid] = set()
            seen_norms[cid].add(norm_txt)
            unique_reviews.append(r)

    # Save processed results
    df_all = pd.DataFrame(unique_reviews)
    if not df_all.empty:
        df_all.to_csv(os.path.join(processed_dir, "reviews_all.csv"), index=False, encoding="utf-8")
        df_all.to_parquet(os.path.join(processed_dir, "reviews_all.parquet"), index=False)
        with open(os.path.join(processed_dir, "reviews_all.jsonl"), "w", encoding="utf-8") as f:
            for r in unique_reviews:
                f.write(json.dumps(r) + "\n")
    else:
        # Write empty templates
        pd.DataFrame(columns=[
            "review_id", "canonical_id", "source", "source_place_id", "rating", "review_text", 
            "review_date", "language", "sentiment_bucket", "sentiment_method", "review_url", 
            "collected_at", "is_duplicate", "content_hash", "scrape_mode", "batch_id"
        ]).to_csv(os.path.join(processed_dir, "reviews_all.csv"), index=False)

    df_dup = pd.DataFrame(duplicate_reviews)
    df_dup.to_csv(os.path.join(processed_dir, "reviews_duplicates.csv"), index=False, encoding="utf-8")

    # 6. Final Review Selection
    # Max 5 positive, 5 negative, 3 neutral per place
    final_selected = []
    
    # Calculate statistics for coverage report
    coverage_stats = []
    
    # Group unique reviews by canonical_id
    reviews_by_place = {}
    for r in unique_reviews:
        cid = r["canonical_id"]
        if cid not in reviews_by_place:
            reviews_by_place[cid] = []
        reviews_by_place[cid].append(r)
        
    for cid, info in pilot_info.items():
        place_revs = reviews_by_place.get(cid, [])
        
        # Categorize collected
        pos_revs = [r for r in place_revs if r["sentiment_bucket"] == "positive" and r["review_text"].strip() != ""]
        neg_revs = [r for r in place_revs if r["sentiment_bucket"] == "negative" and r["review_text"].strip() != ""]
        neu_revs = [r for r in place_revs if r["sentiment_bucket"] == "neutral" and r["review_text"].strip() != ""]
        
        # Select positive (up to 5)
        # Sort rule: newer date, then longer text
        # To do this in python: parse dates
        def get_sort_key(rev):
            d = parse_date(rev["review_date"])
            return (d, len(rev["review_text"]))
            
        pos_revs.sort(key=get_sort_key, reverse=True)
        neg_revs.sort(key=get_sort_key, reverse=True)
        neu_revs.sort(key=get_sort_key, reverse=True)
        
        selected_pos = pos_revs[:5]
        selected_neg = neg_revs[:5]
        selected_neu = neu_revs[:3]
        
        # Assign ranks
        for idx, r in enumerate(selected_pos):
            r["selection_rank"] = idx + 1
            r["selection_reason"] = f"top_representative_positive_rank_{idx+1}"
            r["is_representative"] = True
            final_selected.append(r)
            
        for idx, r in enumerate(selected_neg):
            r["selection_rank"] = idx + 1
            r["selection_reason"] = f"top_representative_negative_rank_{idx+1}"
            r["is_representative"] = True
            final_selected.append(r)
            
        for idx, r in enumerate(selected_neu):
            r["selection_rank"] = idx + 1
            r["selection_reason"] = f"top_representative_neutral_rank_{idx+1}"
            r["is_representative"] = True
            final_selected.append(r)
            
        total_collected = len(place_revs)
        p_collected = len([r for r in place_revs if r["sentiment_bucket"] == "positive"])
        n_collected = len([r for r in place_revs if r["sentiment_bucket"] == "negative"])
        u_collected = len([r for r in place_revs if r["sentiment_bucket"] == "neutral"])
        
        p_sel = len(selected_pos)
        n_sel = len(selected_neg)
        u_sel = len(selected_neu)
        
        # Coverage status
        if p_sel == 5 and n_sel == 5 and u_sel == 3:
            status = "complete"
        elif p_sel == 0 and n_sel == 0 and u_sel == 0:
            status = "none"
        else:
            status = "partial"
            
        coverage_stats.append({
            "canonical_id": cid,
            "name": info["name"],
            "region": info["region"],
            "total_reviews_collected": total_collected,
            "positive_collected": p_collected,
            "negative_collected": n_collected,
            "neutral_collected": u_collected,
            "positive_selected": p_sel,
            "negative_selected": n_sel,
            "neutral_selected": u_sel,
            "coverage_status": status
        })

    # Save final selections
    df_final = pd.DataFrame(final_selected)
    if not df_final.empty:
        df_final.to_csv(os.path.join(final_dir, "reviews.csv"), index=False, encoding="utf-8")
        df_final.to_parquet(os.path.join(final_dir, "reviews.parquet"), index=False)
        with open(os.path.join(final_dir, "reviews.jsonl"), "w", encoding="utf-8") as f:
            for r in final_selected:
                f.write(json.dumps(r) + "\n")
    else:
        # Write empty templates
        pd.DataFrame(columns=[
            "review_id", "canonical_id", "source", "source_place_id", "rating", "review_text", 
            "review_date", "language", "sentiment_bucket", "sentiment_method", "review_url", 
            "collected_at", "is_duplicate", "content_hash", "scrape_mode", "batch_id",
            "selection_rank", "selection_reason", "is_representative"
        ]).to_csv(os.path.join(final_dir, "reviews.csv"), index=False)

    df_cov = pd.DataFrame(coverage_stats)
    df_cov.to_csv(os.path.join(final_dir, "review_coverage.csv"), index=False, encoding="utf-8")

    # 7. Reporting & Summary
    total_pilot_places = len(df_pilot)
    eligible_places = sum(df_pilot["has_google_place_id"] == True)
    ineligible_places = total_pilot_places - eligible_places
    
    places_with_reviews = sum(df_cov["total_reviews_collected"] > 0)
    places_without_reviews = total_pilot_places - places_with_reviews
    
    raw_pos = sum(1 for r, m, _ in raw_reviews_list if m == "positive")
    raw_neg = sum(1 for r, m, _ in raw_reviews_list if m == "negative")
    raw_neu = sum(1 for r, m, _ in raw_reviews_list if m == "neutral")
    
    dup_count = len(duplicate_reviews)
    empty_count = len(empty_text_reviews)
    unmapped_count = len(unmapped_reviews)
    
    pos_selected_total = sum(df_cov["positive_selected"])
    neg_selected_total = sum(df_cov["negative_selected"])
    neu_selected_total = sum(df_cov["neutral_selected"])
    
    complete_target_places = sum(df_cov["coverage_status"] == "complete")
    no_neg_places = sum(df_cov["negative_selected"] == 0)
    no_neu_places = sum(df_cov["neutral_selected"] == 0)

    # Write review_pilot_summary.md
    with open(os.path.join(reports_dir, "review_pilot_summary.md"), "w", encoding="utf-8") as f:
        f.write("# Lampung Tourism Review Pilot Summary Report\n\n")
        f.write(f"Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n")
        
        f.write("## Overview Metrics\n")
        f.write(f"- **Total Pilot Places**: {total_pilot_places}\n")
        f.write(f"- **Eligible Places (with Google Place ID)**: {eligible_places}\n")
        f.write(f"- **Ineligible Places**: {ineligible_places}\n")
        f.write(f"- **Places with Reviews Collected**: {places_with_reviews}\n")
        f.write(f"- **Places without Reviews**: {places_without_reviews}\n\n")
        
        f.write("## Raw Scraper Results\n")
        f.write(f"- **Positive Mode Reviews Collected**: {raw_pos}\n")
        f.write(f"- **Negative Mode Reviews Collected**: {raw_neg}\n")
        f.write(f"- **Neutral Mode Reviews Collected**: {raw_neu}\n")
        f.write(f"- **Total Raw Reviews**: {len(raw_reviews_list)}\n\n")
        
        f.write("## Processing & Quality Metrics\n")
        f.write(f"- **Unmapped Reviews (dropped)**: {unmapped_count}\n")
        f.write(f"- **Duplicate Reviews Filtered**: {dup_count}\n")
        f.write(f"- **Empty Text Reviews**: {empty_count}\n")
        f.write(f"- **Clean Unique Mapped Reviews**: {len(unique_reviews)}\n\n")
        
        f.write("## Representative Selection (Max 5/5/3)\n")
        f.write(f"- **Positive Selected**: {pos_selected_total}\n")
        f.write(f"- **Negative Selected**: {neg_selected_total}\n")
        f.write(f"- **Neutral Selected**: {neu_selected_total}\n")
        f.write(f"- **Total Representative Reviews**: {len(final_selected)}\n\n")
        
        f.write("## Target Coverage Benchmarks\n")
        f.write(f"- **Places with Complete Target (5 Positive, 5 Negative, 3 Neutral)**: {complete_target_places}\n")
        f.write(f"- **Places lacking Negative Reviews**: {no_neg_places}\n")
        f.write(f"- **Places lacking Neutral Reviews**: {no_neu_places}\n\n")
        
    # Write region / place coverage
    df_cov.to_csv(os.path.join(reports_dir, "review_pilot_place_coverage.csv"), index=False, encoding="utf-8")
    
    # Write bucket coverage
    bucket_rows = [
        {"sentiment_bucket": "positive", "collected": sum(df_cov["positive_collected"]), "selected": pos_selected_total},
        {"sentiment_bucket": "negative", "collected": sum(df_cov["negative_collected"]), "selected": neg_selected_total},
        {"sentiment_bucket": "neutral", "collected": sum(df_cov["neutral_collected"]), "selected": neu_selected_total}
    ]
    pd.DataFrame(bucket_rows).to_csv(os.path.join(reports_dir, "review_pilot_bucket_coverage.csv"), index=False, encoding="utf-8")
    
    # Write failed places
    df_failed = df_cov[df_cov["total_reviews_collected"] == 0]
    df_failed.to_csv(os.path.join(reports_dir, "review_pilot_failed_places.csv"), index=False, encoding="utf-8")
    
    # Write batch status from manifest
    batch_status_rows = []
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as mf:
            m_data = json.load(mf)
            for b in m_data.get("batches", []):
                batch_status_rows.append({
                    "batch_id": b["batch_id"],
                    "mode": b["mode"],
                    "status": b["status"],
                    "apify_run_id": b["apify_run_id"],
                    "dataset_id": b["dataset_id"],
                    "place_count": b["place_count"]
                })
    df_bs = pd.DataFrame(batch_status_rows)
    df_bs.to_csv(os.path.join(reports_dir, "review_pilot_batch_status.csv"), index=False, encoding="utf-8")
    
    logger.info("Review processing and final selection complete.")
