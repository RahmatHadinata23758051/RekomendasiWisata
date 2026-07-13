import os
import json
import logging
import hashlib
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional
from src.models.schemas import RawAttractionRecord
from src.storage.writer import save_dataset

logger = logging.getLogger("scraper.collectors.apify_google_maps")

class ApifyGoogleMapsImporter:
    def __init__(self, config_dir: str = "config"):
        # Load settings
        config_path = os.path.join(config_dir, "settings.yaml")
        if os.path.exists(config_path):
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                self.settings = yaml.safe_load(f)["settings"]
        else:
            self.settings = {
                "storage": {
                    "raw_dir": "data/raw",
                    "reports_dir": "reports"
                }
            }
        self.raw_dir = self.settings["storage"]["raw_dir"]

    def _generate_deterministic_id(self, item: Dict[str, Any]) -> str:
        title = item.get("title", "")
        loc = item.get("location") or {}
        lat = loc.get("lat", 0.0)
        lng = loc.get("lng", 0.0)
        hash_input = f"{title}_{lat}_{lng}".encode("utf-8")
        return hashlib.sha256(hash_input).hexdigest()[:16]

    def _validate_record(self, item: Any) -> Tuple[bool, str]:
        if not isinstance(item, dict):
            return False, "Record is not a JSON object"
        if not item.get("title"):
            return False, "Missing title field"
        return True, ""

    def _extract_region_and_date(self, file_path: str) -> Tuple[str, str]:
        path_parts = os.path.normpath(file_path).replace("\\", "/").split("/")
        region = "unknown_region"
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        # Look for date pattern in path parts (e.g. YYYY-MM-DD)
        date_pat = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        for i, part in enumerate(path_parts):
            if date_pat.match(part):
                date_str = part
                if i > 0:
                    region = path_parts[i - 1].lower().replace("-", "_").replace(" ", "_")
                break
                
        return region, date_str

    def _calculate_file_checksum(self, file_path: str) -> str:
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _read_manifest(self, manifest_dir: str) -> List[Dict[str, Any]]:
        path = os.path.join(manifest_dir, "manifest.json")
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load manifest.json: {e}")
            return []

    def _save_manifest(self, manifest: List[Dict[str, Any]], manifest_dir: str):
        os.makedirs(manifest_dir, exist_ok=True)
        path = os.path.join(manifest_dir, "manifest.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save manifest.json: {e}")

    def load_raw_dataset(self, file_path: str, region: Optional[str] = None) -> Tuple[List[RawAttractionRecord], List[Dict[str, Any]]]:
        """
        Loads and validates raw JSON array from Apify.
        Returns:
            - Valid RawAttractionRecord objects
            - List of failed/invalid raw records with reasons
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Apify export file not found at {file_path}")
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format: {e}")
            return [], [{"error": f"JSON Decode Error: {str(e)}", "path": file_path}]
            
        if not isinstance(data, list):
            logger.error("Apify dataset is not a JSON array")
            return [], [{"error": "Root element is not a JSON list/array", "path": file_path}]

        valid_records: List[RawAttractionRecord] = []
        failed_records: List[Dict[str, Any]] = []

        for idx, item in enumerate(data):
            is_valid, reason = self._validate_record(item)
            if not is_valid:
                failed_records.append({
                    "index": idx,
                    "reason": reason,
                    "raw_payload": item
                })
                continue
                
            # Determine source place id
            place_id = item.get("placeId")
            if not place_id:
                place_id = item.get("cid")
            if not place_id:
                place_id = self._generate_deterministic_id(item)
                
            # Get location coordinates
            loc = item.get("location") or {}
            lat = loc.get("lat")
            lng = loc.get("lng")
            
            # Categories
            cats = item.get("categories") or []
            cat_name = item.get("categoryName")
            if cat_name and cat_name not in cats:
                cats.insert(0, cat_name)
                
            # Date collected
            collected_at = item.get("scrapedAt")
            if not collected_at:
                collected_at = datetime.now(timezone.utc).isoformat()
                
            try:
                # Wrap item in RawAttractionRecord structure.
                # Store full raw payload path for reference.
                record = RawAttractionRecord(
                    source_record_id=f"apify_google_maps_{place_id}",
                    canonical_id=None,
                    source="apify_google_maps",
                    source_place_id=str(place_id),
                    source_url=item.get("url"),
                    query_region=region or item.get("city") or "unknown_region",
                    query_keyword=item.get("searchString") or "N/A",
                    raw_name=item["title"],
                    raw_address=item.get("address"),
                    raw_categories=cats,
                    raw_payload_path=file_path,
                    latitude=lat,
                    longitude=lng,
                    collected_at=collected_at,
                    rating=item.get("totalScore"),
                    review_count=item.get("reviewsCount"),
                    phone=item.get("phoneUnformatted") or item.get("phone"),
                    website=item.get("website"),
                    opening_hours=item.get("openingHours"),
                    facilities=item.get("additionalInfo"),
                    permanently_closed=item.get("permanentlyClosed"),
                    temporarily_closed=item.get("temporarilyClosed"),
                    description=item.get("description"),
                    district=item.get("neighborhood"),
                    postal_code=item.get("postalCode"),
                    image_url=item.get("imageUrl")
                )
                valid_records.append(record)
            except Exception as e:
                failed_records.append({
                    "index": idx,
                    "reason": f"Pydantic Validation Error: {str(e)}",
                    "raw_payload": item
                })

        return valid_records, failed_records
        
    def import_dataset(self, file_path: str) -> dict:
        """
        Loads the file and saves structured records into data/raw_records and data/processed/apify/.
        """
        region, date_str = self._extract_region_and_date(file_path)
        logger.info(f"Importing dataset from {file_path} for region: {region}, date: {date_str}")
        
        # Calculate checksum
        checksum = self._calculate_file_checksum(file_path)
        
        # Check manifest
        manifest_dir = os.path.join("data", "raw_records", "apify_google_maps")
        manifest = self._read_manifest(manifest_dir)
        
        for entry in manifest:
            if entry.get("checksum") == checksum:
                logger.info(f"File {file_path} (checksum: {checksum}) is already imported. Skipping.")
                return {
                    "valid_count": entry.get("valid_count", 0),
                    "failed_count": entry.get("failed_count", 0),
                    "region": region,
                    "is_skipped": True
                }
                
        valid, failed = self.load_raw_dataset(file_path, region)
        
        # Save valid raw records to region/date subdirectory
        region_dir = os.path.join("data", "raw_records", "apify_google_maps", region, date_str)
        res_raw = {}
        if valid:
            res_raw = save_dataset(valid, region_dir, "places")
            
        # Append/update failed records in data/processed/apify/failed_records.jsonl in append-safe way
        processed_dir = os.path.join("data", "processed", "apify")
        os.makedirs(processed_dir, exist_ok=True)
        
        failed_path = os.path.join(processed_dir, "failed_records.jsonl")
        if failed:
            with open(failed_path, "a", encoding="utf-8") as f:
                for item in failed:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
                    
        # Update source_records.parquet in append-safe and idempotent way
        if valid:
            try:
                import pandas as pd
                flat_data = [r.model_dump() for r in valid]
                new_df = pd.DataFrame(flat_data)
                
                parquet_path = os.path.join(processed_dir, "source_records.parquet")
                if os.path.exists(parquet_path):
                    old_df = pd.read_parquet(parquet_path)
                    combined_df = pd.concat([old_df, new_df], ignore_index=True)
                    combined_df = combined_df.drop_duplicates(subset=["source_record_id"], keep="last")
                else:
                    combined_df = new_df
                combined_df.to_parquet(parquet_path, index=False, engine="pyarrow")
            except Exception as e:
                logger.error(f"Failed to write source_records.parquet: {e}")
                
        # Save manifest entry
        new_entry = {
            "filepath": file_path,
            "region": region,
            "raw_count": len(valid) + len(failed),
            "valid_count": len(valid),
            "failed_count": len(failed),
            "imported_at": datetime.now(timezone.utc).isoformat(),
            "checksum": checksum
        }
        # Update manifest list (remove existing entry for same filepath if any)
        manifest = [e for e in manifest if e.get("filepath") != file_path]
        manifest.append(new_entry)
        self._save_manifest(manifest, manifest_dir)
        
        logger.info(f"Import completed. Valid: {len(valid)}, Failed: {len(failed)}")
        return {
            "valid_count": len(valid),
            "failed_count": len(failed),
            "region": region,
            "is_skipped": False,
            "raw_records_result": res_raw
        }
