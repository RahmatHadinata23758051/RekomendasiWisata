from pydantic import BaseModel, Field
from typing import List, Optional

class RawAttractionRecord(BaseModel):
    source_record_id: str = Field(..., description="Unique ID for the source record")
    canonical_id: Optional[str] = Field(None, description="Linked canonical place ID")
    source: str = Field(..., description="Source identifier (e.g., osm, google_places, official_sites)")
    source_place_id: str = Field(..., description="Raw ID from the source")
    source_url: Optional[str] = None
    query_region: Optional[str] = None
    query_keyword: Optional[str] = None
    raw_name: str
    raw_address: Optional[str] = None
    raw_categories: Optional[List[str]] = None
    raw_payload_path: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    collected_at: str
    rating: Optional[float] = None
    review_count: Optional[int] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    opening_hours: Optional[List[dict]] = None
    facilities: Optional[dict] = None
    permanently_closed: Optional[bool] = None
    temporarily_closed: Optional[bool] = None
    description: Optional[str] = None
    district: Optional[str] = None
    postal_code: Optional[str] = None
    image_url: Optional[str] = None

class NormalizedAttractionRecord(BaseModel):
    source_record_id: str
    source: str
    source_place_id: str
    name: str
    normalized_name: str
    address: Optional[str] = None
    city_regency: Optional[str] = None
    district: Optional[str] = None
    village: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    categories: List[str] = []
    rating: Optional[float] = None
    review_count: Optional[int] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    currency: Optional[str] = None
    price_notes: Optional[str] = None
    opening_hours: Optional[str] = None
    business_status: Optional[str] = None
    facilities: List[str] = []
    source_url: Optional[str] = None
    collected_at: str
    classification: Optional[str] = None
    classification_confidence: float = 1.0
    classification_signals: List[str] = []
    classification_reason: Optional[str] = None
    dedup_cluster_id: Optional[str] = None
    dedup_reason: Optional[str] = None
    raw_payload_path: Optional[str] = None
    query_region: Optional[str] = None


class PriceRecord(BaseModel):
    price_type: str = Field(..., description="e.g. entrance_fee, parking_fee")
    amount: float
    currency: str = "IDR"
    applies_to: str = Field("general", description="e.g. adult, child, local, foreigner")
    source_url: Optional[str] = None
    observed_at: str
    confidence: float = 1.0
    notes: Optional[str] = None

class ReviewRecord(BaseModel):
    review_id: str
    canonical_place_id: str
    source: str
    source_place_id: str
    rating: float
    review_text: str
    review_date: str
    language: str = "id"
    sentiment_bucket: str = Field(..., description="positive, neutral, negative")
    source_url: Optional[str] = None
    collected_at: str

class CanonicalAttractionRecord(BaseModel):
    canonical_id: str
    name: str
    normalized_name: str
    description: Optional[str] = None
    normalized_category: str
    category_tags: List[str] = []
    address: Optional[str] = None
    city_regency: Optional[str] = None
    district: Optional[str] = None
    village: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    currency: Optional[str] = None
    price_notes: Optional[str] = None
    opening_hours: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    business_status: Optional[str] = None
    facilities: List[str] = []
    primary_source: str
    source_count: int = 1
    first_collected_at: str
    last_collected_at: str
    last_verified_at: str
    dedup_confidence: float = 1.0
    needs_manual_review: bool = False
    classification: Optional[str] = None
    classification_confidence: float = 1.0
    classification_signals: List[str] = []
    classification_reason: Optional[str] = None
    parent_canonical_id: Optional[str] = None
    place_relationship: Optional[str] = None
    dedup_cluster_id: Optional[str] = None
    dedup_reason: Optional[str] = None


