import uuid
import logging
from typing import List, Dict
from src.models.schemas import ReviewRecord
from datetime import datetime, timezone

logger = logging.getLogger("scraper.pipeline.reviews")

def get_sentiment_bucket(rating: float) -> str:
    """
    Categorizes rating into sentiment buckets:
    - rating 4-5 = positive
    - rating 3 = neutral
    - rating 1-2 = negative
    """
    if rating >= 4.0:
        return "positive"
    elif rating >= 3.0:
        return "neutral"
    else:
        return "negative"

def process_place_reviews(raw_reviews: List[Dict], canonical_place_id: str, source: str, source_place_id: str) -> List[ReviewRecord]:
    """
    Filters and normalizes reviews into the targeted schema and distribution:
    - Max 5 positive (rating 4-5)
    - Max 5 negative (rating 1-2)
    - Max 3 neutral (rating 3)
    """
    processed_reviews = []
    
    pos_count = 0
    neg_count = 0
    neu_count = 0
    
    for r in raw_reviews:
        # Check rating
        rating = float(r.get("rating", 0.0))
        sentiment = get_sentiment_bucket(rating)
        
        # Enforce target distribution limits
        if sentiment == "positive" and pos_count >= 5:
            continue
        if sentiment == "negative" and neg_count >= 5:
            continue
        if sentiment == "neutral" and neu_count >= 3:
            continue
            
        # Increment counts
        if sentiment == "positive":
            pos_count += 1
        elif sentiment == "negative":
            neg_count += 1
        else:
            neu_count += 1
            
        # Clean text
        review_text = r.get("text", {}).get("text", "") if isinstance(r.get("text"), dict) else r.get("text", "")
        if not review_text:
            continue # Skip reviews with no text
            
        review_id = f"rev_{uuid.uuid4().hex[:12]}"
        
        processed_reviews.append(ReviewRecord(
            review_id=review_id,
            canonical_place_id=canonical_place_id,
            source=source,
            source_place_id=source_place_id,
            rating=rating,
            review_text=review_text.strip(),
            review_date=r.get("publishTime") or r.get("time") or datetime.now(timezone.utc).isoformat(),
            language=r.get("originalLanguageCode") or "id",
            sentiment_bucket=sentiment,
            source_url=None, # Usually maps or detail URL
            collected_at=datetime.now(timezone.utc).isoformat()
        ))
        
    return processed_reviews
