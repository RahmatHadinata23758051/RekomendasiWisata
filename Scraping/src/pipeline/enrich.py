import re
import logging
from typing import List, Optional
from src.models.schemas import CanonicalAttractionRecord, PriceRecord
from datetime import datetime, timezone

logger = logging.getLogger("scraper.pipeline.enrich")

def extract_prices_from_text(text: str, source_url: Optional[str] = None) -> List[PriceRecord]:
    """
    Parses a string of text (description, notes, or reviews) to detect ticket prices or fees.
    Returns a list of PriceRecord objects with provenance.
    """
    price_records = []
    if not text:
        return price_records
        
    text_lower = text.lower()
    
    # Common price matches in Indonesian:
    # "tiket masuk rp 15.000", "harga tiket: 20.000", "htm: Rp10k"
    patterns = [
        r"(?:tiket masuk|htm|harga tiket|tiket|masuk|parkir|retribusi)\s*(?:rp\.?\s*)?(\d+(?:\.\d+)?)\s*(?:ribu|k)?\b",
        r"(?:rp\.?\s*)?(\d+(?:\.\d+)?)\s*(?:ribu|k)?\s*(?:per orang|/orang|orang|dewasa|anak)"
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, text_lower)
        for m in matches:
            val_str = m.group(1)
            # Standardize numeric value
            val = float(val_str.replace(".", "")) if "." in val_str else float(val_str)
            
            # If followed by 'ribu' or 'k', multiply by 1000
            match_full = m.group(0)
            if "ribu" in match_full or "k" in match_full:
                if val < 1000:
                    val *= 1000
                    
            # Basic heuristics for applies_to / price_type
            price_type = "entrance_fee"
            if "parkir" in match_full:
                price_type = "parking_fee"
                
            applies_to = "general"
            if "dewasa" in match_full:
                applies_to = "adult"
            elif "anak" in match_full:
                applies_to = "child"
                
            price_records.append(PriceRecord(
                price_type=price_type,
                amount=val,
                currency="IDR",
                applies_to=applies_to,
                source_url=source_url,
                observed_at=datetime.now(timezone.utc).isoformat(),
                confidence=0.8,
                notes=f"Extracted from match: '{match_full}'"
            ))
            
    return price_records

def enrich_canonical_place(canonical: CanonicalAttractionRecord, price_records: List[PriceRecord]) -> CanonicalAttractionRecord:
    """
    Enriches the canonical place with min/max prices calculated from price records.
    """
    if not price_records:
        return canonical
        
    # Filter for entrance fees only
    entrance_fees = [p.amount for p in price_records if p.price_type == "entrance_fee"]
    
    if entrance_fees:
        canonical.price_min = min(entrance_fees)
        canonical.price_max = max(entrance_fees)
        canonical.currency = "IDR"
        canonical.price_notes = f"Auto-enriched from {len(entrance_fees)} observed prices."
        
    # Aggregate facilities from raw tags or descriptions if available
    # For now, let's keep it clean
    return canonical
