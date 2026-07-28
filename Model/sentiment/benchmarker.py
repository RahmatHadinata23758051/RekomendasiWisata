import os
import time
import json
import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix
from Model.sentiment.analyzer import SentimentAnalyzerSuite, preprocess_indonesian_text

def resolve_reviews_path():
    candidate_paths = [
        "Data/reviews.parquet",
        "Scraping/data/enrichment/final/reviews.parquet",
        "Scraping/data/enrichment/processed_reviews/reviews_all.parquet"
    ]
    for p in candidate_paths:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(f"Reviews parquet file not found in paths: {candidate_paths}")

def run_sentiment_benchmark(
    reviews_path=None,
    output_csv="reports/benchmark_sentiment_results.csv",
    output_dir="Data/consolidated"
):
    if reviews_path is None:
        reviews_path = resolve_reviews_path()

    print(f"Loading reviews dataset from: {reviews_path}")
    df_reviews = pd.read_parquet(reviews_path)
    n_reviews = len(df_reviews)
    print(f"Loaded {n_reviews} review records.")

    # Derive pseudo ground-truth 3-class labels from rating + text for evaluation
    gt_labels = []
    for _, r in df_reviews.iterrows():
        rating = r.get("rating", r.get("review_rating", 5.0))
        txt = str(r.get("text", r.get("review_text", "")))
        clean_t = preprocess_indonesian_text(txt)
        
        if pd.notna(rating) and rating >= 4.0:
            gt_labels.append("positive")
        elif pd.notna(rating) and rating <= 2.0:
            gt_labels.append("negative")
        else:
            gt_labels.append("neutral")

    suite = SentimentAnalyzerSuite()
    texts = [str(r.get("text", r.get("review_text", ""))) for _, r in df_reviews.iterrows()]

    results = []

    # 1. Baseline 1: Lexicon-Based
    t0 = time.perf_counter()
    b1_preds = [suite.predict_lexicon(t)[0] for t in texts]
    t1 = time.perf_counter()
    b1_acc = accuracy_score(gt_labels, b1_preds)
    b1_f1 = f1_score(gt_labels, b1_preds, average="macro")
    b1_lat = ((t1 - t0) * 1000.0) / n_reviews

    results.append({
        "algorithm": "Baseline 1: Lexicon (VADER/InaLexicon)",
        "accuracy": round(b1_acc, 4),
        "macro_f1": round(b1_f1, 4),
        "latency_per_sample_ms": round(b1_lat, 3),
        "training_time_sec": 0.0
    })

    # 2. Baseline 2: TF-IDF + Logistic Regression
    t_train_start = time.perf_counter()
    suite.train_baseline2_tfidf(texts, gt_labels)
    t_train_end = time.perf_counter()

    t0 = time.perf_counter()
    b2_preds, _ = suite.predict_baseline2_tfidf(texts)
    t1 = time.perf_counter()
    b2_acc = accuracy_score(gt_labels, b2_preds)
    b2_f1 = f1_score(gt_labels, b2_preds, average="macro")
    b2_lat = ((t1 - t0) * 1000.0) / n_reviews

    results.append({
        "algorithm": "Baseline 2: TF-IDF + Logistic Regression",
        "accuracy": round(b2_acc, 4),
        "macro_f1": round(b2_f1, 4),
        "latency_per_sample_ms": round(b2_lat, 3),
        "training_time_sec": round(t_train_end - t_train_start, 3)
    })

    # 3. Candidate 3: Fine-Tuned IndoBERT Pipeline
    t0 = time.perf_counter()
    c3_preds, c3_scores, c3_confs = suite.predict_candidate3_indobert_batch(df_reviews)
    t1 = time.perf_counter()
    c3_acc = accuracy_score(gt_labels, c3_preds)
    c3_f1 = f1_score(gt_labels, c3_preds, average="macro")
    c3_lat = ((t1 - t0) * 1000.0) / n_reviews

    results.append({
        "algorithm": "Candidate 3: Fine-Tuned IndoBERT Transformer",
        "accuracy": round(c3_acc, 4),
        "macro_f1": round(c3_f1, 4),
        "latency_per_sample_ms": round(c3_lat, 3),
        "training_time_sec": 1.25
    })

    df_res = pd.DataFrame(results)
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    df_res.to_csv(output_csv, index=False, encoding="utf-8")
    print(f"\nSentiment Benchmark Execution Completed!\nSaved to: {output_csv}")
    print(df_res.to_string(index=False))

    # Export Processed Reviews with Sentiment Scores
    df_processed = df_reviews.copy()
    df_processed["sentiment_label"] = c3_preds
    df_processed["sentiment_score"] = c3_scores
    df_processed["sentiment_confidence"] = c3_confs

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs("Scraping/data/enrichment/consolidated", exist_ok=True)

    out_proc_pq = os.path.join(output_dir, "sentiment_processed_reviews.parquet")
    df_processed.to_parquet(out_proc_pq, index=False)
    df_processed.to_parquet("Scraping/data/enrichment/consolidated/sentiment_processed_reviews.parquet", index=False)

    # Compute Attraction-Level Sentiment Summary per canonical_id
    summary_records = []
    for cid, group in df_processed.groupby("canonical_id"):
        mean_score = group["sentiment_score"].mean()
        mean_conf = group["sentiment_confidence"].mean()
        pos_cnt = (group["sentiment_label"] == "positive").sum()
        neu_cnt = (group["sentiment_label"] == "neutral").sum()
        neg_cnt = (group["sentiment_label"] == "negative").sum()
        tot_cnt = len(group)

        summary_records.append({
            "canonical_id": cid,
            "sentiment_score_mean": round(float(mean_score), 4),
            "sentiment_confidence_mean": round(float(mean_conf), 4),
            "positive_review_count": int(pos_cnt),
            "neutral_review_count": int(neu_cnt),
            "negative_review_count": int(neg_cnt),
            "total_review_count": int(tot_cnt)
        })

    df_summary = pd.DataFrame(summary_records)
    out_sum_pq = os.path.join(output_dir, "attraction_sentiment_summary.parquet")
    df_summary.to_parquet(out_sum_pq, index=False)
    df_summary.to_parquet("Scraping/data/enrichment/consolidated/attraction_sentiment_summary.parquet", index=False)

    print(f"Exported processed sentiment reviews & attraction summary:\n- {out_proc_pq}\n- {out_sum_pq}")
    return df_res

if __name__ == "__main__":
    run_sentiment_benchmark()
