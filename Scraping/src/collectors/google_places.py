import os
import json
import logging
import asyncio
from datetime import datetime, timezone
from src.collectors.base import BaseCollector
from src.models.schemas import RawAttractionRecord
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

logger = logging.getLogger("scraper.collectors.google_places")

class GooglePlacesCollector(BaseCollector):
    def __init__(self, config_dir: str = "config"):
        super().__init__(source_name="google_places", config_dir=config_dir)
        load_dotenv()
        self.api_key = os.getenv("GOOGLE_PLACES_API_KEY")
        self.endpoint = "https://places.googleapis.com/v1/places:searchText"

    def is_configured(self) -> bool:
        if not self.api_key or self.api_key.startswith("your_") or len(self.api_key) < 10:
            return False
        return True

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=True
    )
    async def _query_text_search(self, query: str, page_token: str = None) -> dict:
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            # FieldMask defines which fields we want returned. Only ask for what is needed to control costs.
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location,places.rating,places.userRatingCount,places.types,places.websiteUri,places.internationalPhoneNumber,places.priceLevel,places.regularOpeningHours,nextPageToken"
        }
        
        body = {"textQuery": query}
        if page_token:
            body["pageToken"] = page_token
            
        logger.info(f"Sending Google Places POST request for query '{query}'")
        response = await self.client.post(
            self.endpoint,
            headers=headers,
            json=body
        )
        response.raise_for_status()
        return response.json()

    async def discover(self, region_id: str = None, keyword: str = None, limit: int = None, resume: bool = False) -> list:
        if not self.is_configured():
            logger.warning(
                "GOOGLE_PLACES_API_KEY is not configured or invalid. Skipping Google Places API collection."
                "\nPlease set a valid GOOGLE_PLACES_API_KEY in your .env file to enable this collector."
            )
            return []

        results = []
        target_regions = [r for r in self.regions if r["id"] == region_id] if region_id else self.regions
        
        # Build keyword list to search
        search_keywords = []
        if keyword:
            search_keywords = [keyword]
        else:
            # Gather all categories of keywords
            for cat, kws in self.keywords.items():
                search_keywords.extend(kws)

        for region in target_regions:
            if not self.is_configured():
                break
            region_name = region["name"]
            region_id = region["id"]
            
            for kw in search_keywords:
                if not self.is_configured():
                    break
                query_str = f"{kw} di {region_name}"
                logger.info(f"Starting Google Places search: '{query_str}'")
                
                # Check for cached results to avoid double billing / API calls
                date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                raw_path_dir = self.get_raw_storage_path(region_id, date_str)
                # Sanitize keyword for filename
                sanitized_kw = "".join([c if c.isalnum() else "_" for c in kw]).strip("_")
                raw_file_path = os.path.join(raw_path_dir, f"google_places_{sanitized_kw}.json")
                
                payloads = []
                if resume and os.path.exists(raw_file_path):
                    logger.info(f"Loading cached response from {raw_file_path}")
                    try:
                        with open(raw_file_path, "r", encoding="utf-8") as f:
                            payloads = json.load(f)
                    except Exception as e:
                        logger.warning(f"Error loading cached Google Places results: {e}. Re-querying.")
                
                if not payloads:
                    payloads = []
                    page_token = None
                    # Google Places search supports up to 3 pages (each page has up to 20 results)
                    for page in range(3):
                        try:
                            data = await self._query_text_search(query_str, page_token)
                            payloads.append(data)
                            page_token = data.get("nextPageToken")
                            if not page_token:
                                break
                            # Google recommends a small delay between pages
                            await asyncio.sleep(self.rate_limit_delay)
                        except Exception as e:
                            logger.error(f"Error calling Google Places API for '{query_str}' (page {page}): {e}")
                            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code in [401, 403]:
                                logger.critical("Invalid/Unauthorized Google Places API Key. Disabling Google Places collector for this session.")
                                self.api_key = None
                            break
                    
                    if payloads:
                        # Write raw payloads
                        with open(raw_file_path, "w", encoding="utf-8") as f:
                            json.dump(payloads, f, ensure_ascii=False, indent=2)
                
                # Process cached or newly fetched payloads
                for payload in payloads:
                    places = payload.get("places", [])
                    for place in places:
                        place_id = place.get("id")
                        if not place_id:
                            continue
                            
                        # Coordinates
                        loc = place.get("location", {})
                        lat = loc.get("latitude")
                        lon = loc.get("longitude")
                        
                        # Display Name
                        display_name = place.get("displayName", {})
                        name = display_name.get("text", "Unnamed Google Place")
                        
                        # Phone and Website
                        phone = place.get("internationalPhoneNumber")
                        website = place.get("websiteUri")
                        
                        # Categories/Types
                        types = place.get("types", [])
                        
                        # Build record
                        record = RawAttractionRecord(
                            source_record_id=f"google_places_{place_id}",
                            canonical_id=None,
                            source="google_places",
                            source_place_id=place_id,
                            source_url=f"https://www.google.com/maps/place/?q=place_id:{place_id}",
                            query_region=region_name,
                            query_keyword=kw,
                            raw_name=name,
                            raw_address=place.get("formattedAddress"),
                            raw_categories=types,
                            raw_payload_path=raw_file_path,
                            latitude=lat,
                            longitude=lon,
                            collected_at=datetime.now(timezone.utc).isoformat()
                        )
                        results.append(record)
                        
                        if limit and len(results) >= limit:
                            break
                    if limit and len(results) >= limit:
                        break
                
                if limit and len(results) >= limit:
                    break
            if limit and len(results) >= limit:
                break
                
        return results
