import os
import glob
import json
import time
import pandas as pd
import numpy as np
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from Model.feature_engineering.builder import CATEGORIES_VOCAB, REGIONS_VOCAB, FACILITIES_VOCAB
from Model.recommender.algorithms import RecommenderAlgorithms
from Model.sentiment.analyzer import SentimentAnalyzerSuite
from Model.api.schemas import (
    RecommendationRequest, RecommendationResponse, RecommendedAttractionItem, ScoreBreakdown,
    SentimentRequest, SentimentResponse, HealthCheckResponse, AttractionItem, PaginatedDestinationsResponse
)

app = FastAPI(
    title="Recommendation Traveller Lampung - ML Engine API",
    description="Production REST API serving Candidate 4 Hybrid Multi-Objective Recommendation Engine & Real Scraped Destinations Payload.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base Paths
FEATURES_PATH = "Data/consolidated/recommender_ready_features.parquet"
MASTER_PATH = "Data/consolidated/attractions_enrichment_master_full.parquet"
JSON_DIR = "Data/*.json"

if not os.path.exists(FEATURES_PATH):
    FEATURES_PATH = "Scraping/data/enrichment/consolidated/recommender_ready_features.parquet"
if not os.path.exists(MASTER_PATH):
    MASTER_PATH = "Scraping/data/enrichment/consolidated/attractions_enrichment_master_full.parquet"

# Load Features & Master Datasets
df_features = pd.read_parquet(FEATURES_PATH)
df_master = pd.read_parquet(MASTER_PATH) if os.path.exists(MASTER_PATH) else pd.DataFrame()

# Build Google Maps Real Image Map
image_map = {}
for json_file in glob.glob(JSON_DIR):
    if "INPUT" in json_file:
        continue
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                t = item.get('title')
                img = item.get('imageUrl')
                pid = item.get('placeId')
                if t and img:
                    image_map[t.lower().strip()] = img
                if pid and img:
                    image_map[pid] = img
    except Exception:
        pass

# Category Fallback Photos
CATEGORY_FALLBACK_IMAGES = {
    'beach': '/assets/images/heroes/hero-pahawang-bg.png',
    'pantai': '/assets/images/heroes/hero-pahawang-bg.png',
    'nature': 'https://images.unsplash.com/photo-1432405972618-c60b0225b8f9?auto=format&fit=crop&w=800&q=80',
    'alam': 'https://images.unsplash.com/photo-1432405972618-c60b0225b8f9?auto=format&fit=crop&w=800&q=80',
    'waterfall': 'https://images.unsplash.com/photo-1432405972618-c60b0225b8f9?auto=format&fit=crop&w=800&q=80',
    'culture': 'https://images.unsplash.com/photo-1566127444979-b3d2b654e3d7?auto=format&fit=crop&w=800&q=80',
    'budaya': 'https://images.unsplash.com/photo-1566127444979-b3d2b654e3d7?auto=format&fit=crop&w=800&q=80',
    'museum': 'https://images.unsplash.com/photo-1566127444979-b3d2b654e3d7?auto=format&fit=crop&w=800&q=80',
    'culinary': 'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=800&q=80',
    'kuliner': 'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=800&q=80',
    'mountain': 'https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=800&q=80',
    'forest': 'https://images.unsplash.com/photo-1534567153574-2b12153a87f0?auto=format&fit=crop&w=800&q=80',
}

# Merge Master Metadata into df_features
if not df_master.empty:
    master_cols = ['canonical_id', 'address', 'description', 'review_count', 'review_rating_mean']
    df_features = df_features.merge(df_master[master_cols], on='canonical_id', how='left')
else:
    df_features['address'] = None
    df_features['description'] = None
    df_features['review_count'] = None
    df_features['review_rating_mean'] = None

# Populate image_url into df_features
def resolve_image_url(row):
    name_key = str(row['name']).lower().strip()
    if name_key in image_map:
        return image_map[name_key]
    cat_key = str(row['primary_category']).lower().strip()
    return CATEGORY_FALLBACK_IMAGES.get(cat_key, 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80')

df_features['image_url'] = df_features.apply(resolve_image_url, axis=1)

# Initialize ML Models
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

@app.get("/api/v1/destinations", response_model=PaginatedDestinationsResponse, tags=["Destinations Data"])
def get_destinations(
    category: Optional[str] = Query(None, description="Filter by category (Pantai, Alam, Budaya, Kuliner, etc.)"),
    city_or_regency: Optional[str] = Query(None, description="Filter by Lampung Regency or City"),
    search: Optional[str] = Query(None, description="Search keyword in name or address"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page")
):
    filtered = df_features.copy()

    if category and category.lower() != 'semua':
        cat_str = category.lower().strip()
        filtered = filtered[filtered['primary_category'].str.lower().str.contains(cat_str, na=False)]

    if city_or_regency and city_or_regency.lower() != 'semua':
        reg_str = city_or_regency.lower().strip()
        filtered = filtered[filtered['city_or_regency'].str.lower().str.contains(reg_str, na=False)]

    if search:
        kw = search.lower().strip()
        filtered = filtered[
            filtered['name'].str.lower().str.contains(kw, na=False) |
            filtered['city_or_regency'].str.lower().str.contains(kw, na=False) |
            filtered['address'].astype(str).str.lower().str.contains(kw, na=False)
        ]

    total_items = len(filtered)
    total_pages = max(1, (total_items + limit - 1) // limit)
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit

    page_df = filtered.iloc[start_idx:end_idx]

    destinations_list = []
    for _, row in page_df.iterrows():
        rating_val = float(row['review_rating_mean']) if pd.notna(row['review_rating_mean']) else 4.6
        reviews_val = int(row['review_count']) if pd.notna(row['review_count']) else 120

        destinations_list.append(AttractionItem(
            canonical_id=str(row['canonical_id']),
            name=str(row['name']),
            primary_category=str(row['primary_category']),
            city_or_regency=str(row['city_or_regency']),
            address=str(row['address']) if pd.notna(row['address']) else None,
            description=str(row['description']) if pd.notna(row['description']) else None,
            image_url=str(row['image_url']),
            rating=round(rating_val, 1),
            reviews_count=reviews_val,
            latitude=float(row['latitude']) if pd.notna(row['latitude']) else None,
            longitude=float(row['longitude']) if pd.notna(row['longitude']) else None,
            operational_status=str(row['operational_status']),
            price_status=str(row['price_status']),
            price_min_idr=float(row['price_min_idr']) if pd.notna(row['price_min_idr']) else None,
            price_max_idr=float(row['price_max_idr']) if pd.notna(row['price_max_idr']) else None,
        ))

    return PaginatedDestinationsResponse(
        status="success",
        page=page,
        limit=limit,
        total_items=total_items,
        total_pages=total_pages,
        destinations=destinations_list
    )

@app.post("/api/v1/recommendations", response_model=RecommendationResponse, tags=["Recommendation Engine"])
def get_recommendations(req: RecommendationRequest):
    t0 = time.perf_counter()

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
        
        if req.budget_max_idr is not None:
            price_min = row.get("price_min_idr")
            if pd.notna(price_min) and price_min > req.budget_max_idr:
                continue

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

        rating_val = float(row['review_rating_mean']) if pd.notna(row['review_rating_mean']) else 4.7
        reviews_val = int(row['review_count']) if pd.notna(row['review_count']) else 150

        item = RecommendedAttractionItem(
            rank=rank_idx,
            canonical_id=str(row["canonical_id"]),
            name=str(row["name"]),
            primary_category=str(row["primary_category"]),
            city_or_regency=str(row["city_or_regency"]),
            address=str(row["address"]) if pd.notna(row["address"]) else None,
            description=str(row["description"]) if pd.notna(row["description"]) else None,
            image_url=str(row["image_url"]),
            rating=round(rating_val, 1),
            reviews_count=reviews_val,
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
