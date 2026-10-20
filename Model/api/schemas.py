from typing import List, Optional
from pydantic import BaseModel, Field

class RecommendationRequest(BaseModel):
    category: Optional[str] = Field(None, json_schema_extra={"example": "beach"}, description="Target tourist category")
    city_or_regency: Optional[str] = Field(None, json_schema_extra={"example": "Kabupaten Pesawaran"}, description="Target Lampung regency/city")
    facilities: Optional[List[str]] = Field(default_factory=list, json_schema_extra={"example": ["has_parking", "has_toilet", "has_food"]}, description="Desired facility flags")
    latitude: Optional[float] = Field(None, json_schema_extra={"example": -5.4292}, description="User current latitude for geodesic proximity")
    longitude: Optional[float] = Field(None, json_schema_extra={"example": 105.2611}, description="User current longitude for geodesic proximity")
    budget_max_idr: Optional[float] = Field(None, json_schema_extra={"example": 50000.0}, description="User max budget constraint in IDR")
    top_k: int = Field(10, ge=1, le=100, description="Number of recommendations to return")

class ScoreBreakdown(BaseModel):
    similarity_category: float
    similarity_region: float
    similarity_facility: float
    similarity_distance: float
    quality_bonus: float
    final_score: float

class RecommendedAttractionItem(BaseModel):
    rank: int
    canonical_id: str
    name: str
    primary_category: str
    city_or_regency: str
    address: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    rating: Optional[float] = None
    rating_weighted: Optional[float] = None
    reviews_count: Optional[int] = 0
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    operational_status: str
    final_score: float
    reason_codes: List[str]
    score_breakdown: ScoreBreakdown
    price_status: str
    price_min_idr: Optional[float] = None
    price_max_idr: Optional[float] = None

class RecommendationResponse(BaseModel):
    status: str = "success"
    total_returned: int
    execution_latency_ms: float
    recommendations: List[RecommendedAttractionItem]

class AttractionItem(BaseModel):
    canonical_id: str
    name: str
    primary_category: str
    city_or_regency: str
    address: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    rating: Optional[float] = None
    rating_weighted: Optional[float] = None
    reviews_count: Optional[int] = 0
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    operational_status: str = "open"
    price_status: str = "free"
    price_min_idr: Optional[float] = None
    price_max_idr: Optional[float] = None
    facilities: List[str] = Field(default_factory=list)

class PaginatedDestinationsResponse(BaseModel):
    status: str = "success"
    page: int
    limit: int
    total_items: int
    total_pages: int
    destinations: List[AttractionItem]


class CatalogSubmission(BaseModel):
    """An already-approved destination from the crowdsourcing workflow."""
    canonical_id: str = Field(..., min_length=1)
    name: str
    primary_category: str
    category_tags: List[str] = Field(default_factory=list)
    city_or_regency: str
    address: Optional[str] = None
    district: Optional[str] = None
    village: Optional[str] = None
    latitude: float
    longitude: float
    description: Optional[str] = None
    image_url: Optional[str] = None
    facilities: List[str] = Field(default_factory=list)
    opening_hours: Optional[object] = None
    price_min_idr: Optional[float] = None
    price_max_idr: Optional[float] = None
    price_status: str = "unknown"
    operational_status: str = "open"
    review_count: int = 0
    review_rating_mean: Optional[float] = None


class CatalogSubmissionResponse(BaseModel):
    status: str = "success"
    canonical_id: str
    total_attractions_loaded: int
    persisted: bool = True
    created: bool = False


class SentimentRequest(BaseModel):
    text: str = Field(..., json_schema_extra={"example": "Pantai Sari Ringgung tempatnya sangat bagus, indah, dan bersih!"})

class SentimentResponse(BaseModel):
    status: str = "success"
    sentiment_label: str
    sentiment_score: float
    confidence: float
    execution_latency_ms: float

class HealthCheckResponse(BaseModel):
    status: str = "healthy"
    model_version: str = "v1.0"
    total_attractions_loaded: int
    service_uptime: str = "operational"

# ==========================================
# AI PLANNER SCHEMAS (FASE 11)
# ==========================================

class PlannerRequest(BaseModel):
    city_or_regency: str = Field(..., json_schema_extra={"example": "Kabupaten Pesawaran"}, description="Target regency or city in Lampung")
    categories: Optional[List[str]] = Field(default_factory=list, description="Multiple preferred categories")
    primary_category: Optional[str] = Field("Semua", json_schema_extra={"example": "Pantai"}, description="Primary preferred category or comma-separated categories")
    budget_level: Optional[str] = Field("Standar", json_schema_extra={"example": "Ekonomis"}, description="Budget constraint: Ekonomis, Standar, Mewah")
    pace_style: Optional[str] = Field("Santai", json_schema_extra={"example": "Santai"}, description="Pace style: Santai (3 slots/day) or Padat (4-5 slots/day)")
    duration_days: int = Field(1, ge=1, le=7, description="Number of itinerary days")

class PlannerSlotItem(BaseModel):
    canonical_id: Optional[str] = None
    time: str
    activityTitle: str
    category: str
    location: str
    estimatedCost: str
    numericCost: float
    coords: List[float]
    image: str
    aiTip: Optional[str] = None
    travelTime: Optional[str] = None

class PlannerDayItem(BaseModel):
    dayNumber: int
    title: str
    slots: List[PlannerSlotItem]

class PlannerGenerateResponse(BaseModel):
    status: str = "success"
    regency: str
    duration_days: int
    total_cost_estimate_idr: float
    execution_latency_ms: float
    itinerary: List[PlannerDayItem]

class PlannerSwapRequest(BaseModel):
    city_or_regency: str = Field(..., json_schema_extra={"example": "Kabupaten Pesawaran"})
    category: Optional[str] = Field(None, json_schema_extra={"example": "Pantai"})
    exclude_ids: List[str] = Field(default_factory=list, description="IDs already included in itinerary")

class PlannerSwapResponse(BaseModel):
    status: str = "success"
    total_returned: int
    alternatives: List[PlannerSlotItem]
