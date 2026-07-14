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
    
    # 1. Load pilot places mapping & batch info
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
            "source_url": s_url,
            "pilot_batch": row.get("pilot_batch") or "batch_001"
        }
        if pd.notna(g_id) and str(g_id).strip() != "":
            place_id_to_canon[str(g_id).strip()] = cid
        if pd.notna(s_url) and str(s_url).strip() != "":
            url_to_canon[str(s_url).strip()] = cid
            
    # Load extra pilot details from pilot_google_places_input.csv (for review count & eligibility)
    pilot_input_path = "data/enrichment/pilot/pilot_google_places_input.csv"
    review_counts = {}
    eligible_status = {}
    if os.path.exists(pilot_input_path):
        try:
            df_in = pd.read_csv(pilot_input_path)
            for _, r in df_in.iterrows():
                cid = r["canonical_id"]
                review_counts[cid] = r.get("review_count", 0)
                eligible_str = str(r.get("review_scrape_eligible", "true")).lower()
                eligible_status[cid] = eligible_str in ["true", "1", "1.0"]
        except Exception as e:
            logger.warning(f"Failed to read pilot input file: {e}")

    # 2. Load manifest for statuses & targets
    batch_to_canon_map = {} # (batch_id, mode) -> list of cids
    batch_statuses = {}
    batch_targets_map = {}
    canon_to_batch = {}
    
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as mf:
                m_data = json.load(mf)
                for b in m_data.get("batches", []):
                    bid = b["batch_id"]
                    batch_to_canon_map[(bid, b["mode"])] = b.get("canonical_ids", [])
                    batch_statuses[bid] = b.get("status", "pending")
                    batch_targets_map[bid] = {
                        "positive": b.get("representative_target_positive", 5),
                        "negative": b.get("representative_target_negative", 3 if bid != "batch_001" else 5),
                        "neutral": b.get("representative_target_neutral", 2 if bid != "batch_001" else 3)
                    }
                    for cid in b.get("canonical_ids", []):
                        canon_to_batch[cid] = bid
        except Exception as e:
            logger.warning(f"Failed to read manifest file: {e}")

    def get_batch_targets(bid: str) -> Dict[str, int]:
        if bid in batch_targets_map:
            return batch_targets_map[bid]
        if bid == "batch_001":
            return {"positive": 5, "negative": 5, "neutral": 3}
        return {"positive": 5, "negative": 3, "neutral": 2}

    # 3. Read raw reviews
    raw_reviews_list = []
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
        pid = r.get("placeId") or r.get("googlePlaceId")
        p_url = r.get("placeUrl") or r.get("url")
        
        cid = None
        if pid and str(pid).strip() in place_id_to_canon:
            cid = place_id_to_canon[str(pid).strip()]
        elif p_url and str(p_url).strip() in url_to_canon:
            cid = url_to_canon[str(p_url).strip()]
        else:
            cids_in_batch = batch_to_canon_map.get((batch_id, mode), [])
            if len(cids_in_batch) == 1:
                cid = cids_in_batch[0]
                
        if not cid:
            unmapped_reviews.append({
                "raw_payload": r,
                "scrape_mode": mode,
                "batch_id": batch_id,
                "reason": f"Could not map placeId '{pid}' or url '{p_url}' to any canonical_id"
            })
            continue
            
        review_id = r.get("id") or r.get("reviewId")
        if not review_id:
            raw_text = r.get("text") or ""
            author = r.get("authorName") or ""
            review_id = "gen_" + hashlib.md5(f"{raw_text}_{author}".encode("utf-8")).hexdigest()
            
        text = r.get("text") or r.get("reviewText") or ""
        rating_val = r.get("stars") or r.get("rating")
        
        try:
            rating = int(float(rating_val))
        except Exception:
            rating = 5
            
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
    seen_ids = set()
    seen_hashes = {}
    seen_norms = {}
    
    unique_reviews = []
    duplicate_reviews = []
    
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
        pd.DataFrame(columns=[
            "review_id", "canonical_id", "source", "source_place_id", "rating", "review_text", 
            "review_date", "language", "sentiment_bucket", "sentiment_method", "review_url", 
            "collected_at", "is_duplicate", "content_hash", "scrape_mode", "batch_id"
        ]).to_csv(os.path.join(processed_dir, "reviews_all.csv"), index=False)

    df_dup = pd.DataFrame(duplicate_reviews)
    df_dup.to_csv(os.path.join(processed_dir, "reviews_duplicates.csv"), index=False, encoding="utf-8")

    # 6. Final Review Selection
    final_selected = []
    coverage_stats = []
    
    reviews_by_place = {}
    for r in unique_reviews:
        cid = r["canonical_id"]
        if cid not in reviews_by_place:
            reviews_by_place[cid] = []
        reviews_by_place[cid].append(r)
        
    for cid, info in pilot_info.items():
        place_revs = reviews_by_place.get(cid, [])
        
        # Determine targets dynamically based on batch
        bid = canon_to_batch.get(cid) or "batch_001"
        targets = get_batch_targets(bid)
        p_target = targets["positive"]
        n_target = targets["negative"]
        u_target = targets["neutral"]
        
        # Categorize collected
        pos_revs = [r for r in place_revs if r["sentiment_bucket"] == "positive" and r["review_text"].strip() != ""]
        neg_revs = [r for r in place_revs if r["sentiment_bucket"] == "negative" and r["review_text"].strip() != ""]
        neu_revs = [r for r in place_revs if r["sentiment_bucket"] == "neutral" and r["review_text"].strip() != ""]
        
        def get_sort_key(rev):
            d = parse_date(rev["review_date"])
            return (d, len(rev["review_text"]))
            
        pos_revs.sort(key=get_sort_key, reverse=True)
        neg_revs.sort(key=get_sort_key, reverse=True)
        neu_revs.sort(key=get_sort_key, reverse=True)
        
        selected_pos = pos_revs[:p_target]
        selected_neg = neg_revs[:n_target]
        selected_neu = neu_revs[:u_target]
        
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
        
        # Resolve dynamic coverage status (Task 4)
        is_eligible = eligible_status.get(cid, True)
        if not is_eligible:
            status = "ineligible"
        else:
            b_status = batch_statuses.get(bid, "pending")
            if b_status != "completed":
                status = "not_scheduled"
            else:
                if total_collected == 0:
                    r_count = review_counts.get(cid, 0)
                    if pd.isna(r_count) or r_count == 0:
                        status = "no_google_reviews"
                    else:
                        status = "failed_scrape"
                else:
                    if p_sel + n_sel + u_sel == 0:
                        status = "reviews_without_text"
                    elif p_sel == p_target and n_sel == n_target and u_sel == u_target:
                        status = "complete_bucket_coverage"
                    else:
                        status = "partial_bucket_coverage"
            
        coverage_stats.append({
            "canonical_id": cid,
            "name": info["name"],
            "region": info["region"],
            "pilot_batch": bid,
            "total_reviews_collected": total_collected,
            "positive_collected": p_collected,
            "negative_collected": n_collected,
            "neutral_collected": u_collected,
            "positive_selected": p_sel,
            "negative_selected": n_sel,
            "neutral_selected": u_sel,
            "coverage_status": status,
            "target_positive": p_target,
            "target_negative": n_target,
            "target_neutral": u_target
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
        pd.DataFrame(columns=[
            "review_id", "canonical_id", "source", "source_place_id", "rating", "review_text", 
            "review_date", "language", "sentiment_bucket", "sentiment_method", "review_url", 
            "collected_at", "is_duplicate", "content_hash", "scrape_mode", "batch_id",
            "selection_rank", "selection_reason", "is_representative"
        ]).to_csv(os.path.join(final_dir, "reviews.csv"), index=False)

    df_cov = pd.DataFrame(coverage_stats)
    df_cov.to_csv(os.path.join(final_dir, "review_coverage.csv"), index=False, encoding="utf-8")

    # 7. Reporting & Performance Metrics (Task 5)
    total_pilot_places = len(df_pilot)
    eligible_places = sum(df_cov["coverage_status"] != "ineligible")
    ineligible_places = sum(df_cov["coverage_status"] == "ineligible")
    
    pending_places = sum(df_cov["coverage_status"] == "not_scheduled")
    
    df_attempted = df_cov[~df_cov["coverage_status"].isin(["ineligible", "not_scheduled"])]
    attempted_place_count = len(df_attempted)
    
    attempted_with_reviews = sum(df_attempted["total_reviews_collected"] > 0)
    attempted_without_reviews = attempted_place_count - attempted_with_reviews
    
    raw_pos = sum(1 for r, m, _ in raw_reviews_list if m == "positive")
    raw_neg = sum(1 for r, m, _ in raw_reviews_list if m == "negative")
    raw_neu = sum(1 for r, m, _ in raw_reviews_list if m == "neutral")
    total_raw_reviews = len(raw_reviews_list)
    
    dup_count = len(duplicate_reviews)
    empty_count = len(empty_text_reviews)
    unmapped_count = len(unmapped_reviews)
    
    pos_selected_total = sum(df_cov["positive_selected"])
    neg_selected_total = sum(df_cov["negative_selected"])
    neu_selected_total = sum(df_cov["neutral_selected"])
    total_selected_reviews = len(final_selected)
    
    attempted_review_coverage_rate = attempted_with_reviews / attempted_place_count if attempted_place_count > 0 else 0.0
    duplicate_rate = dup_count / total_raw_reviews if total_raw_reviews > 0 else 0.0
    empty_text_rate = empty_count / total_raw_reviews if total_raw_reviews > 0 else 0.0
    representative_yield_rate = total_selected_reviews / total_raw_reviews if total_raw_reviews > 0 else 0.0
    
    sum_pos_targets = sum(df_attempted["target_positive"])
    sum_neg_targets = sum(df_attempted["target_negative"])
    sum_neu_targets = sum(df_attempted["target_neutral"])
    
    bucket_fill_rate_positive = pos_selected_total / sum_pos_targets if sum_pos_targets > 0 else 0.0
    bucket_fill_rate_negative = neg_selected_total / sum_neg_targets if sum_neg_targets > 0 else 0.0
    bucket_fill_rate_neutral = neu_selected_total / sum_neu_targets if sum_neu_targets > 0 else 0.0
    
    average_selected_reviews = total_selected_reviews / attempted_with_reviews if attempted_with_reviews > 0 else 0.0
    
    complete_target_places = sum(df_cov["coverage_status"] == "complete_bucket_coverage")
    no_neg_places = sum(df_cov["negative_selected"] == 0)
    no_neu_places = sum(df_cov["neutral_selected"] == 0)

    # Cost calculation (Task 6)
    actor_run_cost = 0.0
    recovery_download_cost = 0.0
    total_platform_cost = 0.0
    cost_status = "unavailable"
    
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as mf:
                m_data = json.load(mf)
                completed_runs_count = 0
                total_reviews_in_runs = 0
                for b in m_data.get("batches", []):
                    if b.get("status") == "completed":
                        run_id = b.get("apify_run_id")
                        if run_id and run_id != "imported_offline":
                            completed_runs_count += 1
                            total_reviews_in_runs += b.get("raw_review_count", 0)
                            
                if completed_runs_count > 0:
                    actor_run_cost = completed_runs_count * 0.50 + total_reviews_in_runs * 0.003
                    recovery_download_cost = 0.0
                    total_platform_cost = actor_run_cost
                    cost_status = "available"
        except Exception as e:
            logger.warning(f"Failed to calculate platform costs: {e}")

    # Write review_pilot_summary.md
    with open(os.path.join(reports_dir, "review_pilot_summary.md"), "w", encoding="utf-8") as f:
        f.write("# Lampung Tourism Review Pilot Summary Report (Optimized)\n\n")
        f.write(f"Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n")
        
        f.write("## Overview Metrics\n")
        f.write(f"- **Total Pilot Places**: {total_pilot_places}\n")
        f.write(f"- **Eligible Places (with Google Place ID)**: {eligible_places}\n")
        f.write(f"- **Ineligible Places**: {ineligible_places}\n")
        f.write(f"- **Pending / Not Scheduled Places**: {pending_places}\n")
        f.write(f"- **Attempted Places**: {attempted_place_count}\n")
        f.write(f"  - Attempted with Reviews: {attempted_with_reviews}\n")
        f.write(f"  - Attempted without Reviews: {attempted_without_reviews}\n\n")
        
        f.write("## Raw Scraper Results\n")
        f.write(f"- **Positive Mode Reviews Collected**: {raw_pos}\n")
        f.write(f"- **Negative Mode Reviews Collected**: {raw_neg}\n")
        f.write(f"- **Neutral Mode Reviews Collected**: {raw_neu}\n")
        f.write(f"- **Total Raw Reviews**: {total_raw_reviews}\n\n")
        
        f.write("## Processing & Quality Metrics\n")
        f.write(f"- **Unmapped Reviews (dropped)**: {unmapped_count}\n")
        f.write(f"- **Duplicate Reviews Filtered**: {dup_count} (Duplicate Rate: {duplicate_rate:.2%})\n")
        f.write(f"- **Empty Text Reviews**: {empty_count} (Empty Text Rate: {empty_text_rate:.2%})\n")
        f.write(f"- **Clean Unique Mapped Reviews**: {len(unique_reviews)}\n\n")
        
        f.write("## Representative Selection (5/3/2 Strategy v2, 5/5/3 v1)\n")
        f.write(f"- **Positive Selected**: {pos_selected_total} (Fill Rate: {bucket_fill_rate_positive:.2%})\n")
        f.write(f"- **Negative Selected**: {neg_selected_total} (Fill Rate: {bucket_fill_rate_negative:.2%})\n")
        f.write(f"- **Neutral Selected**: {neu_selected_total} (Fill Rate: {bucket_fill_rate_neutral:.2%})\n")
        f.write(f"- **Total Selected Reviews**: {total_selected_reviews} (Yield Rate: {representative_yield_rate:.2%})\n")
        f.write(f"- **Average Selected Reviews per Covered Place**: {average_selected_reviews:.2f}\n\n")
        
        f.write("## Target Coverage Benchmarks (Attempted Places)\n")
        f.write(f"- **Places with Complete Bucket Coverage**: {complete_target_places}\n")
        f.write(f"- **Places lacking Negative Reviews**: {no_neg_places}\n")
        f.write(f"- **Places lacking Neutral Reviews**: {no_neu_places}\n\n")

        f.write("## Cost & Platform Charges (USD)\n")
        f.write(f"- **Actor Run Cost**: ${actor_run_cost:.2f}\n")
        f.write(f"- **Recovery Download Cost**: ${recovery_download_cost:.2f}\n")
        f.write(f"- **Total Platform Cost**: ${total_platform_cost:.2f}\n")
        f.write(f"- **Cost Status**: {cost_status}\n")
        f.write("  *(Note: Recovery offline does not incur new fees, but original platform execution costs are detailed above)*\n")
        
    df_cov.to_csv(os.path.join(reports_dir, "review_pilot_place_coverage.csv"), index=False, encoding="utf-8")
    
    bucket_rows = [
        {"sentiment_bucket": "positive", "collected": sum(df_cov["positive_collected"]), "selected": pos_selected_total},
        {"sentiment_bucket": "negative", "collected": sum(df_cov["negative_collected"]), "selected": neg_selected_total},
        {"sentiment_bucket": "neutral", "collected": sum(df_cov["neutral_collected"]), "selected": neu_selected_total}
    ]
    pd.DataFrame(bucket_rows).to_csv(os.path.join(reports_dir, "review_pilot_bucket_coverage.csv"), index=False, encoding="utf-8")
    
    df_failed = df_cov[df_cov["coverage_status"].isin(["failed_scrape", "no_google_reviews"])]
    df_failed.to_csv(os.path.join(reports_dir, "review_pilot_failed_places.csv"), index=False, encoding="utf-8")
    
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
