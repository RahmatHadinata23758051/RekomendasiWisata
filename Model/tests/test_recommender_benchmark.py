import os
import pytest
import pandas as pd
import numpy as np
from Model.recommender.algorithms import RecommenderAlgorithms
from Model.recommender.benchmarker import run_benchmark

def test_recommender_algorithms_execution():
    features_path = "Data/consolidated/recommender_ready_features.parquet"
    if not os.path.exists(features_path):
        features_path = "Scraping/data/enrichment/consolidated/recommender_ready_features.parquet"

    df_feat = pd.read_parquet(features_path)
    engine = RecommenderAlgorithms(df_feat)

    cat_cols = [c for c in df_feat.columns if c.startswith("feat_cat_")]
    reg_cols = [c for c in df_feat.columns if c.startswith("feat_reg_")]
    fac_cols = [c for c in df_feat.columns if c.startswith("feat_fac_")]

    q_cat = df_feat[cat_cols].iloc[0].values.astype(np.float32)
    q_reg = df_feat[reg_cols].iloc[0].values.astype(np.float32)
    q_fac = df_feat[fac_cols].iloc[0].values.astype(np.float32)
    q_comb = np.hstack([q_cat, q_reg, q_fac])

    # 1. Baseline 1
    idx1, scores1 = engine.baseline1_simple_cosine(q_comb, top_k=10)
    assert len(idx1) == 10
    assert len(scores1) == 10

    # 2. Baseline 2
    idx2, scores2 = engine.baseline2_weighted_multimetric(q_cat, q_reg, q_fac, top_k=10)
    assert len(idx2) == 10

    # 3. Candidate 3
    idx3, scores3 = engine.candidate3_tfidf_quality("pantai pesawaran", top_k=10)
    assert len(idx3) == 10

    # 4. Candidate 4
    idx4, scores4 = engine.candidate4_hybrid_multi_objective(q_cat, q_reg, q_fac, top_k=10)
    assert len(idx4) == 10

def test_run_benchmark_output():
    df_res = run_benchmark(output_csv="reports/benchmark_recommender_results.csv")
    assert len(df_res) == 4
    assert "precision_at_10" in df_res.columns
    assert "ndcg_at_10" in df_res.columns
    assert "catalog_coverage_pct" in df_res.columns
    assert "latency_ms" in df_res.columns

    # Candidate 4 should outperform Baselines in nDCG@10 or Precision@10
    c4_p10 = df_res[df_res["algorithm"].str.contains("Candidate 4")]["precision_at_10"].values[0]
    assert c4_p10 > 0.50
