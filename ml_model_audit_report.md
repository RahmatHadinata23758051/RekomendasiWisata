# ML Model Audit Report — Recommendation Traveller Lampung

**Generated:** 2026-10-08  
**Scope:** Full ML pipeline — datasets, feature engineering, recommender algorithms, sentiment analysis, benchmarking, validation, API serving, tests.  
**Source commit:** Current working tree (no edits made).

---

## 1. Exact Model Inventory

| Model / Component | Type | Status | Implementation File(s) | Key Parameters |
|---|---|---|---|---|
| **Recommender — Baseline 1** | Simple Cosine Similarity | Implemented & Benchmarked | `Model/recommender/algorithms.py:48` | Full combined matrix (cat+reg+fac), top-k |
| **Recommender — Baseline 2** | Weighted Multi-Metric (Cosine Cat + Exact Reg + Jaccard Fac) | Implemented & Benchmarked | `Model/recommender/algorithms.py:55` | w_cat=0.5, w_reg=0.3, w_fac=0.2 |
| **Recommender — Candidate 3** | TF-IDF Text Similarity + Quality Penalty | Implemented & Benchmarked | `Model/recommender/algorithms.py:71` | TF-IDF on "cat region facility" text, penalty weight=0.5 |
| **Recommender — Candidate 4** | Hybrid Multi-Objective Scoring | **Production Default** | `Model/recommender/algorithms.py:80` | w_cat=0.4, w_reg=0.25, w_fac=0.15, w_dist=0.10, w_qual=0.10; geodesic decay λ=0.015 |
| **Sentiment — Baseline 1** | Indonesian Lexicon (VADER/InaLexicon) | Implemented & Benchmarked | `Model/sentiment/analyzer.py:44` | 21 pos / 22 neg keywords, rule-based |
| **Sentiment — Baseline 2** | TF-IDF (1-2 gram, 2500 feats) + Logistic Regression | Implemented & Benchmarked | `Model/sentiment/analyzer.py:57` | max_iter=1000, random_state=42 |
| **Sentiment — Candidate 3** | Fine-Tuned IndoBERT (simulated hybrid rating+text logic) | Implemented & Benchmarked | `Model/sentiment/analyzer.py:70` | Rating-weighted heuristic; not a real transformer fine-tune |
| **Feature Engineering** | Hybrid vectorization (structured lists + flattened columns) | Production | `Model/feature_engineering/builder.py` | 21 cat, 15 reg, 10 fac → 67 total columns, 3130 rows |
| **API Serving** | FastAPI (Candidate 4 recommender + Candidate 3 sentiment) | Production | `Model/api/app.py` | SLA <200ms, Pydantic contracts, CORS, pagination |

---

## 2. Dataset Evidence

| Dataset | Path | Rows × Cols | Key Stats |
|---|---|---|---|
| **Master Enrichment** | `Data/consolidated/attractions_enrichment_master_full.parquet` | 3130 × 99 | 4 permanently_closed, 138 unknown, 2965 open; 172 with reviews |
| **Recommender Features** | `Data/consolidated/recommender_ready_features.parquet` | 3130 × 67 | 3126 eligible, 172 with sentiment scores, 2958 null rating/sentiment |
| **Sentiment Reviews** | `Data/consolidated/sentiment_processed_reviews.parquet` | 924 reviews | 172 attractions, 5.37 reviews/attr; labels: pos 651, neg 233, neu 40 |
| **Sentiment Summary** | `Data/consolidated/attraction_sentiment_summary.parquet` | 172 × 7 | Per-attraction aggregated scores (mean 0.55, std 0.33) |

**Critical Data Quality Observations:**
- 94.5% of attractions (2958/3130) have **no review coverage** → sentiment_score_mean & rating_normalized are NaN for almost all items.
- Price columns (`price_min_idr`, `price_max_idr`) are 100% null in master and features.
- External verification status: 3119/3130 "not_verified", only 10 "completed_no_price".
- Category imbalance: "other" dominates (1012/3130), "culture" only 4 samples.

---

## 3. Metric Tables with Evidence

### 3.1 Recommender Benchmark (15 synthetic personas, top-10)

| Algorithm | Precision@10 | nDCG@10 | Catalog Coverage % | Latency (ms) | Unique Recommended |
|---|---:|---:|---:|---:|---:|
| Baseline 1: Simple Cosine | 0.5733 | 0.8139 | 4.19 | 0.90 | 131 |
| Baseline 2: Weighted Multi-Metric | **0.9600** | **1.0000** | 4.79 | 0.77 | 150 |
| Candidate 3: TF-IDF + Penalty | 0.6267 | 0.8043 | 4.19 | 1.43 | 131 |
| **Candidate 4: Hybrid Multi-Objective** | **0.9600** | **1.0000** | 4.76 | 0.94 | 149 |

**Source:** `reports/benchmark_recommender_results.csv`

**Interpretation:** Baselines 2 and Candidate 4 tie on Precision@10 and nDCG@10. Candidate 4 adds distance decay and quality bonus without degrading ranking quality. Catalog coverage is extremely low (~4.8%) — only ~150 of 3130 items ever appear in top-10 across 15 personas.

### 3.2 Sentiment Benchmark (924 reviews, 3-class labels derived from star ratings)

| Algorithm | Accuracy | Macro F1 | Latency/sample (ms) | Train Time (s) |
|---|---:|---:|---:|---:|
| Baseline 1: Lexicon | 0.5087 | 0.4089 | 0.021 | 0.0 |
| Baseline 2: TF-IDF + Logistic Regression | 0.8333 | 0.6002 | 0.058 | 0.137 |
| **Candidate 3: IndoBERT (simulated)** | **0.9567** | **0.8789** | 0.126 | 1.25 |

**Source:** `reports/benchmark_sentiment_results.csv`

**Interpretation:** Candidate 3's "IndoBERT" is a **rating-heuristic simulator**, not a real fine-tuned transformer. It achieves 95.7% accuracy by heavily leveraging the star rating (4-5★→positive, 1-2★→negative) which is the same signal used to create pseudo-labels. This inflates metrics and does not prove NLP capability.

### 3.3 Cross-Validation Overfitting Audit (5-fold stratified, TF-IDF + LR)

| Metric | Value | Threshold | Verdict |
|---|---:|---:|---|
| Mean Train Macro F1 | (run required) | — | — |
| Mean Val Macro F1 | (run required) | — | — |
| Delta F1 (Overfitting Gap) | (run required) | ≤ 0.08 | — |

**Note:** The cross-validator exists but was not executed in this session. The report template claims "NO OVERFITTING (PASS)" but actual numbers need verification.

---

## 4. Defects & Risks (Prioritized)

### 🔴 P0 — Critical / Blocking

| ID | Defect | Evidence | Impact |
|---|---|---|---|
| **D1** | **Candidate 3 "IndoBERT" is a heuristic simulator, not a real model** | `analyzer.py:70-113` uses rating thresholds (4★/2★) + keyword counts; no transformer weights loaded. | Misleading benchmark; production sentiment will fail on unrated text. |
| **D2** | **Sentiment integrated into recommender for only 5.5% of items (172/3130)** | Manifest: `sentiment_integrated_attractions_count=172`; 2958 NaN sentiment scores. | Hybrid score `w_qual * qual_score` ignores sentiment for 94.5% of catalog; distance/quality dominate. |
| **D3** | **Pseudo-labels for sentiment evaluation derived from the same ratings used by Candidate 3** | `benchmarker.py:34-45` creates GT from rating; `analyzer.py:88-97` uses rating to decide label. | **Circular evaluation** — Candidate 3 "cheats" by seeing the label source. Metrics invalid. |
| **D4** | **Catalog coverage ~4.8% — recommender ignores >95% of attractions** | Benchmark CSV: all algos 4.19–4.79% coverage. | Long-tail destinations never recommended; poor diversity, cold-start failure. |
| **D5** | **Price features 100% null — budget filtering non-functional** | Master & features: `price_min_idr`, `price_max_idr` all NaN. | API `budget_max_idr` filter (app.py:247-250) always passes; no price-aware ranking. |
| **D6** | **No train/val/test split for recommender — synthetic personas only** | Benchmark uses 15 hard-coded personas; no real user interaction data. | Cannot measure real-world precision/recall; synthetic cases may overfit to vocab. |

### 🟠 P1 — High

| ID | Defect | Evidence | Impact |
|---|---|---|---|
| **D7** | **Category "other" = 32% of catalog; no sub-typing** | Master: `primary_category` value_counts shows 1012 "other". | Low discriminative power for category similarity; many items indistinguishable. |
| **D8** | **Candidate 4 weights hard-coded, not learned/tuned** | `algorithms.py:80` defaults w_cat=0.4, w_reg=0.25, w_fac=0.15, w_dist=0.10, w_qual=0.10. | Suboptimal weighting; no evidence these are optimal for Lampung tourism. |
| **D9** | **Distance decay λ=0.015 and 5km offset arbitrary** | `algorithms.py:100` `exp(-0.015 * max(0, d_km - 5.0))`. | No validation that this decay matches user behavior in Lampung geography. |
| **D10** | **TF-IDF vectorizer fit on full corpus (no holdout) in Candidate 3 recommender** | `algorithms.py:38-46` fits on all 3130 items at init. | Data leakage if TF-IDF used in production with new items; vocabulary frozen at build time. |
| **D11** | **Sentiment confidence is mostly 0 (mean 0.052, median 0)** | Feature stats: `sentiment_confidence` 75th percentile = 0. | Confidence-weighted sentiment fusion ineffective; downstream code treats all NaN as 0. |
| **D12** | **No A/B testing or shadow deployment infrastructure** | API serves single model version; no experiment framework. | Cannot safely roll out Candidate 4 vs Baseline 2 in production. |

### 🟡 P2 — Medium

| ID | Defect | Evidence |
|---|---|---|
| **D13** | Cross-validation report not executed; overfitting claim unverified. | `cross_validator.py` exists but no output artifact found. |
| **D14** | Feature vocabularies (cat/reg/fac) are fixed constants — cannot handle new categories/regions/facilities without rebuild. | `builder.py:8-25` hard-coded lists. |
| **D15** | API loads all 3130 rows into global memory at startup; no incremental reload or hot-swap. | `app.py:47-48` global `df_features`. |
| **D16** | No monitoring/observability: no latency histograms, error rates, drift detection. | `app.py` has no logging/metrics middleware. |
| **D17** | Test assertions weak: `test_api_endpoints.py` only checks `latency_ms < 200` and `precision > 0.50`. | No regression tests for ranking quality, diversity, fairness. |
| **D18** | Sentiment label distribution highly skewed (pos 70%, neg 25%, neu 4%); macro F1 masks per-class performance. | `sentiment_processed_reviews.parquet` label counts. |
| **D19** | No explainability beyond static reason codes; no feature attribution (SHAP/LIME) or counterfactuals. | `generate_reason_codes` uses fixed thresholds. |

---

## 5. Cold-Start Behavior Analysis

| Scenario | Current Handling | Gap |
|---|---|---|
| **New attraction (no reviews, no sentiment)** | Eligible if open + coords; quality penalty from completeness; sentiment=0, rating=NaN. | Relies solely on category/region/facility match + distance. No content-based fallback (description, images). |
| **New user (no history)** | Synthetic persona vectors only; API requires explicit category/region/facility. | No collaborative filtering, no session-based inference, no popular/fallback ranking. |
| **New region/category not in vocab** | Fixed vocabularies → new values mapped to zero vector (no match). | Requires full dataset rebuild (`builder.py`) to expand vocab. |
| **Sparse facilities** | Multi-hot encoding; Jaccard similarity in Baseline 2 & Candidate 4. | Items with no facility flags get sim_fac=0; no partial credit for related facilities. |

---

## 6. Explainability Assessment

| Aspect | Implementation | Gap |
|---|---|---|
| **Reason codes** | 6 static rules (category_match, region_match, facility_match, nearby_location, positive_sentiment, verified_open) | Thresholds arbitrary (e.g., sim_cat ≥ 0.8, sim_dist ≥ 0.7); no per-user personalization. |
| **Score breakdown** | Returns 5 component scores + final | Components not normalized to same scale; weights hidden from user. |
| **Counterfactual / what-if** | None | Cannot answer "why not this item?" or "what would change the rank?". |
| **Feature importance** | None | No global or local feature attribution. |

---

## 7. Production Readiness Checklist

| Criterion | Status | Notes |
|---|---|---|
| **Reproducible builds (frozen dataset + seed)** | ✅ | Manifest with SHA256, fixed vocab, seed=42 in CV. |
| **Data contracts / schema validation** | ⚠️ Partial | Pydantic schemas for API; no validation on parquet load. |
| **Model versioning & rollback** | ❌ | Single `model_version="v1.0"`; no artifact registry. |
| **CI/CD pipeline** | ❌ | No GitHub Actions / pipeline visible in Model/. |
| **Load testing / SLA verification** | ⚠️ | Test asserts <200ms; no k6 / Locust suite. |
| **Monitoring (latency, errors, drift)** | ❌ | No Prometheus/OpenTelemetry; no log structure. |
| **Secrets / config management** | ⚠️ | Paths hardcoded with fallbacks; no env-based config. |
| **Security (auth, rate limit, input validation)** | ❌ | No auth, no rate limiting, CORS="*". |
| **Documentation (API specs, runbooks)** | ✅ | OpenAPI via FastAPI; ARCHITECTURE.md detailed. |
| **Disaster recovery / backup** | ❌ | No backup strategy for parquet artifacts. |

---

## 8. Prioritized ML Improvement Plan

| Phase | Priority | Action | Owner Est. Effort | Success Metric |
|---|---|---|---|---|
| **1** | P0 | **Replace Candidate 3 sentiment simulator with real IndoBERT fine-tune** (or at minimum a supervised TF-IDF/SVM trained on human-labeled data). Separate label generation from model input. | 2–3 weeks | Macro F1 ≥ 0.80 on held-out human labels; no rating leakage. |
| **2** | P0 | **Collect / generate sentiment for remaining 2958 attractions** (review scraping, synthetic augmentation, or zero-shot classifier). | 2–4 weeks | sentiment_integrated_attractions_count ≥ 2500 (80%). |
| **3** | P0 | **Fix circular evaluation**: create human-annotated test set (min 200 reviews) for sentiment; use rating-only split for recommender eval. | 1–2 weeks | Honest benchmark numbers; Candidate 3 ≤ Baseline 2 on fair test. |
| **4** | P0 | **Improve catalog coverage**: add popularity/recency boosting, diversity-aware re-ranking (MMR), or collaborative signals. | 2–3 weeks | Coverage ≥ 20% in offline benchmark; long-tail items appear in top-10. |
| **5** | P1 | **Learn/tune Candidate 4 weights** via Bayesian optimization or grid search on held-out user interaction proxy (e.g., click logs, synthetic utility). | 1–2 weeks | Precision@10 improvement ≥ 5% over hard-coded weights. |
| **6** | P1 | **Add price data**: integrate external price APIs, scrape ticket prices, or use proxy (category/region heuristics). | 2–3 weeks | price_min_idr null rate < 50%; budget filter functional. |
| **7** | P1 | **Sub-type "other" category**: use description embeddings or clustering to split into 5–10 meaningful sub-categories. | 1–2 weeks | Category entropy ↑; Precision@10 on "other" items improves. |
| **8** | P1 | **Distance decay calibration**: fit λ and offset on real user geo-data or stated preference surveys. | 1 week | Offline nDCG@10 improves with geo-aware sessions. |
| **9** | P2 | **Implement model registry + versioning** (MLflow or DVC); CI pipeline for benchmark regression. | 1–2 weeks | Every PR runs benchmarks; fails if Precision@10 drops >2%. |
| **10** | P2 | **Add observability**: structured JSON logs, Prometheus metrics (latency, error rate, prediction drift), Grafana dashboard. | 1 week | p99 latency < 200ms; drift alerts on feature distributions. |
| **11** | P2 | **Real explainability**: integrate SHAP for Candidate 4 linear components; generate natural-language explanations. | 2 weeks | User study: ≥ 80% find explanations helpful. |
| **12** | P2 | **Cold-start module**: content-based fallback using description embeddings (SBERT) + image features (CLIP) for new items. | 2–3 weeks | New items ranked meaningfully within 24h of ingest. |

---

## 9. Appendix: Test Execution Log

```
8 passed, 1 warning in 17.26s
- test_recommender_benchmark.py: 2 passed
- test_sentiment_benchmark.py: 2 passed
- test_feature_builder.py: 1 passed
- test_api_endpoints.py: 3 passed
```

All tests pass but are **smoke tests only** — they verify execution and minimal shape, not metric quality or regression detection.

---

**End of Audit Report**