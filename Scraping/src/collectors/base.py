import os
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
import yaml
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger("scraper.collectors")

class BaseCollector(ABC):
    def __init__(self, source_name: str, config_dir: str = "config"):
        self.source_name = source_name
        self.config_dir = config_dir
        self.settings = self._load_yaml(os.path.join(config_dir, "settings.yaml"))["settings"]
        self.regions = self._load_yaml(os.path.join(config_dir, "regions.yaml"))["regions"]
        self.keywords = self._load_yaml(os.path.join(config_dir, "keywords.yaml"))["keywords"]
        
        self.raw_dir = self.settings["storage"]["raw_dir"]
        self.logs_dir = self.settings["storage"]["logs_dir"]
        
        os.makedirs(self.logs_dir, exist_ok=True)
        os.makedirs(os.path.join(self.raw_dir, self.source_name), exist_ok=True)
        
        self.concurrency = self.settings["concurrency"]
        self.rate_limit_delay = self.settings["rate_limit_delay_seconds"]
        self.timeout = self.settings["timeout_seconds"]
        
        # Load HTTP client
        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            headers={"User-Agent": "LampungTourismScraper/0.1.0 (https://github.com/user/Recommendation-Traveller)"}
        )

    def _load_yaml(self, filepath: str) -> dict:
        with open(filepath, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def get_raw_storage_path(self, region_id: str, date_str: str = None) -> str:
        if not date_str:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        dir_path = os.path.join(self.raw_dir, self.source_name, date_str, region_id)
        os.makedirs(dir_path, exist_ok=True)
        return dir_path

    async def close(self):
        await self.client.aclose()

    @abstractmethod
    async def discover(self, region_id: str = None, keyword: str = None, limit: int = None, resume: bool = False) -> list:
        """
        Discover attraction candidates and save raw payloads.
        Returns a list of RawAttractionRecord models.
        """
        pass
