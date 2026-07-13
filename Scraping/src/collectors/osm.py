import os
import json
import logging
import asyncio
from datetime import datetime, timezone
from src.collectors.base import BaseCollector
from src.models.schemas import RawAttractionRecord
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

logger = logging.getLogger("scraper.collectors.osm")

class OSMCollector(BaseCollector):
    def __init__(self, config_dir: str = "config"):
        super().__init__(source_name="osm", config_dir=config_dir)
        self.endpoints = [
            "https://overpass.kumi.systems/api/interpreter",
            "https://overpass-api.de/api/interpreter",
            "https://lz4.overpass-api.de/api/interpreter",
            "https://z.overpass-api.de/api/interpreter",
            "https://overpass.nchc.org.tw/api/interpreter"
        ]

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=True
    )
    async def _query_overpass(self, query_str: str) -> dict:
        for idx, endpoint in enumerate(self.endpoints):
            try:
                logger.info(f"Querying Overpass API endpoint: {endpoint}...")
                response = await self.client.post(
                    endpoint,
                    data={"data": query_str},
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept-Encoding": "gzip, deflate",
                        "Accept": "*/*"
                    }
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.warning(f"Endpoint {endpoint} failed: {e}")
                if idx == len(self.endpoints) - 1:
                    raise e
                await asyncio.sleep(1)
        raise httpx.HTTPError("All Overpass endpoints failed")

    def _build_overpass_query(self, bbox: list) -> str:
        # bbox order in regions.yaml is [min_lon, min_lat, max_lon, max_lat]
        # Overpass expects: min_lat, min_lon, max_lat, max_lon
        min_lon, min_lat, max_lon, max_lat = bbox
        
        # Build query for the tags specified
        tags_clause = (
            f'node["tourism"~"attraction|museum|viewpoint|zoo|theme_park|aquarium|gallery|camp_site|picnic_site"]({min_lat},{min_lon},{max_lat},{max_lon});'
            f'way["tourism"~"attraction|museum|viewpoint|zoo|theme_park|aquarium|gallery|camp_site|picnic_site"]({min_lat},{min_lon},{max_lat},{max_lon});'
            f'relation["tourism"~"attraction|museum|viewpoint|zoo|theme_park|aquarium|gallery|camp_site|picnic_site"]({min_lat},{min_lon},{max_lat},{max_lon});'
            f'node["historic"]({min_lat},{min_lon},{max_lat},{max_lon});'
            f'way["historic"]({min_lat},{min_lon},{max_lat},{max_lon});'
            f'relation["historic"]({min_lat},{min_lon},{max_lat},{max_lon});'
            f'node["natural"~"beach|peak|volcano|cave_entrance"]({min_lat},{min_lon},{max_lat},{max_lon});'
            f'way["natural"~"beach|peak|volcano|cave_entrance"]({min_lat},{min_lon},{max_lat},{max_lon});'
            f'relation["natural"~"beach|peak|volcano|cave_entrance"]({min_lat},{min_lon},{max_lat},{max_lon});'
            f'node["waterway"="waterfall"]({min_lat},{min_lon},{max_lat},{max_lon});'
            f'way["waterway"="waterfall"]({min_lat},{min_lon},{max_lat},{max_lon});'
            f'relation["waterway"="waterfall"]({min_lat},{min_lon},{max_lat},{max_lon});'
            f'node["leisure"~"park|nature_reserve|water_park"]({min_lat},{min_lon},{max_lat},{max_lon});'
            f'way["leisure"~"park|nature_reserve|water_park"]({min_lat},{min_lon},{max_lat},{max_lon});'
            f'relation["leisure"~"park|nature_reserve|water_park"]({min_lat},{min_lon},{max_lat},{max_lon});'
            f'node["amenity"="arts_centre"]({min_lat},{min_lon},{max_lat},{max_lon});'
            f'way["amenity"="arts_centre"]({min_lat},{min_lon},{max_lat},{max_lon});'
            f'relation["amenity"="arts_centre"]({min_lat},{min_lon},{max_lat},{max_lon});'
        )
        
        query = f"""
        [out:json][timeout:90];
        (
          {tags_clause}
        );
        out center body;
        """
        return query

    async def discover(self, region_id: str = None, keyword: str = None, limit: int = None, resume: bool = False) -> list:
        results = []
        target_regions = [r for r in self.regions if r["id"] == region_id] if region_id else self.regions
        
        for region in target_regions:
            region_name = region["name"]
            region_id = region["id"]
            bbox = region["bbox"]
            
            logger.info(f"Starting discovery for OSM in {region_name}")
            
            # Check checkpoint
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            raw_path_dir = self.get_raw_storage_path(region_id, date_str)
            raw_file_path = os.path.join(raw_path_dir, "response.json")
            
            payload = None
            if resume and os.path.exists(raw_file_path):
                logger.info(f"Checkpoint found. Loading cached data from {raw_file_path}")
                try:
                    with open(raw_file_path, "r", encoding="utf-8") as f:
                        payload = json.load(f)
                except Exception as e:
                    logger.warning(f"Failed to load checkpoint file {raw_file_path}: {e}. Querying again.")
            
            if not payload:
                query_str = self._build_overpass_query(bbox)
                try:
                    payload = await self._query_overpass(query_str)
                    # Cache raw response
                    with open(raw_file_path, "w", encoding="utf-8") as f:
                        json.dump(payload, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    logger.error(f"Error querying OSM Overpass for region {region_name}: {e}")
                    continue
                
                # Rate limiting delay
                await asyncio.sleep(self.rate_limit_delay)

            # Process payload
            elements = payload.get("elements", [])
            logger.info(f"Found {len(elements)} elements in {region_name}")
            
            for elem in elements:
                # Resolve geometry
                lat = elem.get("lat")
                lon = elem.get("lon")
                if not lat or not lon:
                    center = elem.get("center")
                    if center:
                        lat = center.get("lat")
                        lon = center.get("lon")
                
                elem_type = elem.get("type")
                elem_id = elem.get("id")
                tags = elem.get("tags", {})
                
                # Skip items without names (often administrative boundaries or minor map elements)
                name = tags.get("name") or tags.get("official_name")
                if not name:
                    continue
                
                # Determine categories
                categories = []
                for cat_key in ["tourism", "historic", "natural", "waterway", "leisure", "amenity"]:
                    if cat_key in tags:
                        categories.append(f"{cat_key}={tags[cat_key]}")
                
                # Format address
                addr_parts = []
                for addr_key in ["addr:street", "addr:housenumber", "addr:city", "addr:postcode"]:
                    val = tags.get(addr_key)
                    if val:
                        addr_parts.append(val)
                address = ", ".join(addr_parts) if addr_parts else tags.get("addr:full")
                
                record = RawAttractionRecord(
                    source_record_id=f"osm_{elem_type}_{elem_id}",
                    canonical_id=None,
                    source="osm",
                    source_place_id=f"{elem_type}/{elem_id}",
                    source_url=f"https://www.openstreetmap.org/{elem_type}/{elem_id}",
                    query_region=region_name,
                    query_keyword="bulk_overpass",
                    raw_name=name,
                    raw_address=address,
                    raw_categories=categories,
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
                
        return results
