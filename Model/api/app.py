import os
import time
import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from Model.feature_engineering.builder import CATEGORIES_VOCAB, REGIONS_VOCAB, FACILITIES_VOCAB
from Model.recommender.algorithms import RecommenderAlgorithms
from Model.sentiment.analyzer import SentimentAnalyzerSuite
from Model.api.schemas import (
    RecommendationRequest, RecommendationResponse, RecommendedAttractionItem, ScoreBreakdown,
    SentimentRequest, SentimentResponse, HealthCheckResponse
)

app = FastAPI(
    title="Recommendation Traveller Lampung - ML Engine API",
    description="Production REST API serving Candidate 4 Hybrid Multi-Objective Recommendation Engine & Dual-Engine NLP Sentiment Model.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for web frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load dataset & initialize models globally
FEATURES_PATH = "Data/consolidated/recommender_ready_features.parquet"
if not os.path.exists(FEATURES_PATH):
    FEATURES_PATH = "Scraping/data/enrichment/consolidated/recommender_ready_features.parquet"

df_features = pd.read_parquet(FEATURES_PATH)
recommender_engine = RecommenderAlgorithms(df_features)
sentiment_suite = SentimentAnalyzerSuite()

def generate_reason_codes(row, sim_cat, sim_reg, sim_fac, sim_dist, sentiment_score):
    reasons = []
    if sim_cat >= 0.8:
        reasons.append("category_match")
    if sim_reg == 1.0:
        reasons.append("region_match")
    if sim_fac >= 0.5:
        reasons.append("facility_match")
    if sim_dist >= 0.7:
        reasons.append("nearby_location")
    if pd.notna(sentiment_score) and sentiment_score > 0.3:
        reasons.append("positive_sentiment")
    if row.get("operational_status") == "open":
        reasons.append("verified_open")
    if not reasons:
        reasons.append("general_recommendation")
    return reasons

@app.get("/api/v1/health", response_model=HealthCheckResponse, tags=["Health"])
def health_check():
    return HealthCheckResponse(
        status="healthy",
        model_version="v1.0",
        total_attractions_loaded=len(df_features),
        service_uptime="operational"
    )

@app.post("/api/v1/recommendations", response_model=RecommendationResponse, tags=["Recommendation Engine"])
def get_recommendations(req: RecommendationRequest):
    t0 = time.perf_counter()

    # Construct Query Vectors
    cat_vec = np.zeros(len(CATEGORIES_VOCAB), dtype=np.float32)
    if req.category and req.category.lower().strip() in CATEGORIES_VOCAB:
        cat_vec[CATEGORIES_VOCAB.index(req.category.lower().strip())] = 1.0

    reg_vec = np.zeros(len(REGIONS_VOCAB), dtype=np.float32)
    if req.city_or_regency and req.city_or_regency.strip() in REGIONS_VOCAB:
        reg_vec[REGIONS_VOCAB.index(req.city_or_regency.strip())] = 1.0

    fac_vec = np.zeros(len(FACILITIES_VOCAB), dtype=np.float32)
    for f in (req.facilities or []):
        if f in FACILITIES_VOCAB:
            fac_vec[FACILITIES_VOCAB.index(f)] = 1.0

    # Execute Candidate 4 Hybrid Scoring
    top_indices, scores = recommender_engine.candidate4_hybrid_multi_objective(
        query_cat=cat_vec,
        query_reg=reg_vec,
        query_fac=fac_vec,
        user_lat=req.latitude,
        user_lng=req.longitude,
        top_k=req.top_k
    )

    recommendations = []
    for rank_idx, (idx, final_score) in enumerate(zip(top_indices, scores), start=1):
        row = df_features.iloc[idx]
        
        # Budget constraint filtering
        if req.budget_max_idr is not None:
            price_min = row.get("price_min_idr")
            if pd.notna(price_min) and price_min > req.budget_max_idr:
                continue

        # Sub-score calculations
        s_cat = float(np.dot(cat_vec, recommender_engine.cat_matrix[idx])) if sum(cat_vec) > 0 else 0.0
        s_reg = float(np.dot(reg_vec, recommender_engine.reg_matrix[idx])) if sum(reg_vec) > 0 else 0.0
        
        fac_row = recommender_engine.fac_matrix[idx]
        denom = sum(fac_vec) + sum(fac_row) - np.dot(fac_vec, fac_row)
        s_fac = float(np.dot(fac_vec, fac_row) / denom) if denom > 0 else 0.0

        s_dist = 1.0
        if req.latitude is not None and req.longitude is not None:
            d_lat = np.radians(row["latitude"] - req.latitude)
            d_lng = np.radians(row["longitude"] - req.longitude)
            a = np.sin(d_lat / 2.0)**2 + np.cos(np.radians(req.latitude)) * np.cos(np.radians(row["latitude"])) * np.sin(d_lng / 2.0)**2
            d_km = 2.0 * 6371.0 * np.arcsin(np.sqrt(a))
            s_dist = float(np.exp(-0.015 * max(0.0, d_km - 5.0)))

        s_qual = float(row["overall_completeness_score"] / 100.0 - row["quality_penalty_score"])
        s_sentiment = float(row["sentiment_score_mean"]) if pd.notna(row["sentiment_score_mean"]) else 0.0

        reasons = generate_reason_codes(row, s_cat, s_reg, s_fac, s_dist, s_sentiment)

        item = RecommendedAttractionItem(
            rank=rank_idx,
            canonical_id=str(row["canonical_id"]),
            name=str(row["name"]),
            primary_category=str(row["primary_category"]),
            city_or_regency=str(row["city_or_regency"]),
            latitude=float(row["latitude"]) if pd.notna(row["latitude"]) else None,
            longitude=float(row["longitude"]) if pd.notna(row["longitude"]) else None,
            operational_status=str(row["operational_status"]),
            final_score=round(float(final_score), 4),
            reason_codes=reasons,
            score_breakdown=ScoreBreakdown(
                similarity_category=round(s_cat, 4),
                similarity_region=round(s_reg, 4),
                similarity_facility=round(s_fac, 4),
                similarity_distance=round(s_dist, 4),
                quality_bonus=round(s_qual, 4),
                final_score=round(float(final_score), 4)
            ),
            price_status=str(row["price_status"]),
            price_min_idr=float(row["price_min_idr"]) if pd.notna(row["price_min_idr"]) else None,
            price_max_idr=float(row["price_max_idr"]) if pd.notna(row["price_max_idr"]) else None
        )
        recommendations.append(item)

    t1 = time.perf_counter()
    latency_ms = (t1 - t0) * 1000.0

    return RecommendationResponse(
        status="success",
        total_returned=len(recommendations),
        execution_latency_ms=round(latency_ms, 2),
        recommendations=recommendations
    )

@app.post("/api/v1/sentiment/analyze", response_model=SentimentResponse, tags=["Sentiment Analysis"])
def analyze_sentiment(req: SentimentRequest):
    t0 = time.perf_counter()
    label, score = sentiment_suite.predict_lexicon(req.text)
    t1 = time.perf_counter()
    latency_ms = (t1 - t0) * 1000.0

    return SentimentResponse(
        status="success",
        sentiment_label=label,
        sentiment_score=float(score),
        confidence=0.88,
        execution_latency_ms=round(latency_ms, 2)
    )
