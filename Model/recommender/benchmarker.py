import os
import time
import json
import pandas as pd
import numpy as np
from Model.feature_engineering.builder import CATEGORIES_VOCAB, REGIONS_VOCAB, FACILITIES_VOCAB
from Model.recommender.algorithms import RecommenderAlgorithms

# 15 Synthetic Tourist Personas across Lampung
SYNTHETIC_PERSONAS = [
    {"name": "Beach & Watersport Lover", "category": "beach", "region": "Kabupaten Pesawaran", "facilities": ["has_parking", "has_toilet", "has_food"]},
    {"name": "Mountain & Nature Hiker", "category": "mountain", "region": "Kabupaten Lampung Barat", "facilities": ["has_parking", "has_camping"]},
    {"name": "Family Recreation Seeker", "category": "family", "region": "Kota Bandar Lampung", "facilities": ["has_parking", "has_toilet", "has_food", "has_prayer_room"]},
    {"name": "Culture & Heritage Enthusiast", "category": "culture", "region": "Kabupaten Lampung Timur", "facilities": ["has_parking", "has_guide"]},
    {"name": "Waterfall Adventurer", "category": "waterfall", "region": "Kabupaten Tanggamus", "facilities": ["has_parking"]},
    {"name": "Agrotourism Visitor", "category": "agrotourism", "region": "Kabupaten Pringsewu", "facilities": ["has_parking", "has_food"]},
    {"name": "Island Hopper", "category": "island", "region": "Kabupaten Pesisir Barat", "facilities": ["has_parking", "has_toilet"]},
    {"name": "History & Museum Scholar", "category": "history", "region": "Kota Bandar Lampung", "facilities": ["has_toilet", "has_guide"]},
    {"name": "Camping & Forest Explorer", "category": "camping", "region": "Kabupaten Lampung Tengah", "facilities": ["has_camping", "has_parking"]},
    {"name": "Religious Pilgrim", "category": "religious", "region": "Kabupaten Lampung Selatan", "facilities": ["has_prayer_room", "has_toilet"]},
    {"name": "Lake & River Sightseer", "category": "lake", "region": "Kabupaten Lampung Utara", "facilities": ["has_parking", "has_food"]},
    {"name": "Urban Park Stroller", "category": "park", "region": "Kota Metro", "facilities": ["has_parking", "has_toilet"]},
    {"name": "Waterpark Thrillseeker", "category": "waterpark", "region": "Kota Bandar Lampung", "facilities": ["has_parking", "has_toilet", "has_food"]},
    {"name": "Educational Tour Group", "category": "education", "region": "Kabupaten Tulang Bawang", "facilities": ["has_toilet", "has_guide"]},
    {"name": "General Sightseer", "category": "nature", "region": "Kabupaten Way Kanan", "facilities": ["has_parking", "has_food"]}
]

def calculate_ndcg(retrieved_categories, target_category, k=10):
    relevances = [1.0 if cat == target_category else 0.0 for cat in retrieved_categories[:k]]
    dcg = sum([r / np.log2(idx + 2) for idx, r in enumerate(relevances)])
    ideal_relevances = sorted(relevances, reverse=True)
    idcg = sum([r / np.log2(idx + 2) for idx, r in enumerate(ideal_relevances)])
    return dcg / idcg if idcg > 0 else 0.0

def run_benchmark(
    features_path="Data/consolidated/recommender_ready_features.parquet",
    output_csv="reports/benchmark_recommender_results.csv",
    top_k=10
):
    if not os.path.exists(features_path):
        features_path = "Scraping/data/enrichment/consolidated/recommender_ready_features.parquet"

    print(f"Loading feature dataset from: {features_path}")
    df_feat = pd.read_parquet(features_path)
    engine = RecommenderAlgorithms(df_feat)

    algo_names = [
        "Baseline 1: Simple Cosine",
        "Baseline 2: Weighted Multi-Metric",
        "Candidate 3: TF-IDF + Quality Penalty",
        "Candidate 4: Hybrid Multi-Objective"
    ]

    results = []

    for algo in algo_names:
        latencies = []
        precision_list = []
        ndcg_list = []
        recommended_items = set()

        for persona in SYNTHETIC_PERSONAS:
            target_cat = persona["category"]
            target_reg = persona["region"]
            target_facs = persona["facilities"]

            # Construct query vectors
            cat_vec = np.zeros(len(CATEGORIES_VOCAB), dtype=np.float32)
            if target_cat in CATEGORIES_VOCAB:
                cat_vec[CATEGORIES_VOCAB.index(target_cat)] = 1.0

            reg_vec = np.zeros(len(REGIONS_VOCAB), dtype=np.float32)
            if target_reg in REGIONS_VOCAB:
                reg_vec[REGIONS_VOCAB.index(target_reg)] = 1.0

            fac_vec = np.zeros(len(FACILITIES_VOCAB), dtype=np.float32)
            for f in target_facs:
                if f in FACILITIES_VOCAB:
                    fac_vec[FACILITIES_VOCAB.index(f)] = 1.0

            combined_q = np.hstack([cat_vec, reg_vec, fac_vec])
            query_text = f"{target_cat} {target_reg} " + " ".join([f.replace('has_', '') for f in target_facs])

            t0 = time.perf_counter()
            if "Baseline 1" in algo:
                indices, _ = engine.baseline1_simple_cosine(combined_q, top_k=top_k)
            elif "Baseline 2" in algo:
                indices, _ = engine.baseline2_weighted_multimetric(cat_vec, reg_vec, fac_vec, top_k=top_k)
            elif "Candidate 3" in algo:
                indices, _ = engine.candidate3_tfidf_quality(query_text, top_k=top_k)
            else:
                indices, _ = engine.candidate4_hybrid_multi_objective(cat_vec, reg_vec, fac_vec, top_k=top_k)
            t1 = time.perf_counter()

            latencies.append((t1 - t0) * 1000.0) # in ms

            retrieved_cats = df_feat.iloc[indices]["primary_category"].values
            relevant_count = sum([1 for c in retrieved_cats if c == target_cat])
            precision_list.append(relevant_count / float(top_k))
            ndcg_list.append(calculate_ndcg(retrieved_cats, target_cat, k=top_k))

            for idx in indices:
                recommended_items.add(df_feat.iloc[idx]["canonical_id"])

        avg_latency = float(np.mean(latencies))
        avg_precision = float(np.mean(precision_list))
        avg_ndcg = float(np.mean(ndcg_list))
        catalog_coverage = (len(recommended_items) / float(len(df_feat))) * 100.0

        results.append({
            "algorithm": algo,
            "precision_at_10": round(avg_precision, 4),
            "ndcg_at_10": round(avg_ndcg, 4),
            "catalog_coverage_pct": round(catalog_coverage, 2),
            "latency_ms": round(avg_latency, 2),
            "unique_recommended_count": len(recommended_items)
        })

    df_res = pd.DataFrame(results)
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    df_res.to_csv(output_csv, index=False, encoding="utf-8")
    print(f"\nBenchmark Execution Completed Successfully!\nSaved to: {output_csv}")
    print(df_res.to_string(index=False))
    return df_res

if __name__ == "__main__":
    run_benchmark()
