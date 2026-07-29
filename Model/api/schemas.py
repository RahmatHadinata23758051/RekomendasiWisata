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
    rating: Optional[float] = 4.5
    reviews_count: Optional[int] = 120
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
    rating: Optional[float] = 4.5
    reviews_count: Optional[int] = 100
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
