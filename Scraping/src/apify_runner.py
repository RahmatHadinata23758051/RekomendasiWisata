"""Safe execution of versioned Apify Google Maps batch inputs.

The batch JSON files are deliberately kept as raw actor inputs.  This module owns
all network access, credentials, immutable raw output handling, and importer
invocation so operators never need to paste a token into an input file.
"""
from __future__ import annotations

import csv
import getpass
import hashlib
import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional
from urllib.parse import quote

import httpx


APIFY_API_URL = "https://api.apify.com/v2"
ACTOR_ID = "compass/crawler-google-places"
TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}
_SECRET_KEYS = {"token", "apitoken", "apikey", "api_key", "password", "secret", "authorization"}


class ApifyRunnerError(RuntimeError):
    """Raised for invalid batches, API failures, or incomplete runs."""


@dataclass(frozen=True)
class BatchSpec:
    version: str
    batch: str
    file: str
    kind: str
    region_id: str
    location_or_ids: str = ""


class ApifyBatchRunner:
    """Run checked-in batches without exposing the API token in output or URLs."""

    def __init__(
        self,
        batches_root: str | Path = "config/apify_batches",
        output_root: str | Path = "data/raw/apify/google_maps",
        *,
        api_url: str = APIFY_API_URL,
        actor_id: str = ACTOR_ID,
        http_client: Any | None = None,
        importer_factory: Callable[[], Any] | None = None,
        poll_interval: float = 5.0,
        poll_timeout: float = 3600.0,
    ) -> None:
        self.batches_root = Path(batches_root)
        self.output_root = Path(output_root)
        self.api_url = api_url.rstrip("/")
        self.actor_id = actor_id
        self._client = http_client
        self.importer_factory = importer_factory
        self.poll_interval = max(0.0, poll_interval)
        self.poll_timeout = poll_timeout

    @property
    def index_path(self) -> Path:
        return self.batches_root / "index.csv"

    def list_batches(self) -> list[BatchSpec]:
        """Read the authoritative CSV index and return all versioned inputs."""
        if not self.index_path.is_file():
            raise ApifyRunnerError(f"Batch index not found: {self.index_path}")
        with self.index_path.open("r", encoding="utf-8", newline="") as stream:
            rows = csv.DictReader(stream)
            required = {"version", "batch", "file", "kind", "region_id"}
            missing = required - set(rows.fieldnames or ())
            if missing:
                raise ApifyRunnerError(f"Batch index missing columns: {', '.join(sorted(missing))}")
            result = []
            for row in rows:
                result.append(BatchSpec(
                    version=row["version"], batch=row["batch"], file=row["file"],
                    kind=row["kind"], region_id=row["region_id"],
                    location_or_ids=row.get("location_or_ids", ""),
                ))
        return result

    def resolve_file(self, file_name: str) -> tuple[BatchSpec, Path]:
        """Resolve only files present in index.csv and confined to batches_root."""
        requested = Path(file_name)
        specs = self.list_batches()
        spec = next((item for item in specs if item.file == file_name), None)
        if spec is None:
            # Accept a path relative to batches_root for operator convenience, but
            # still require its canonical path to be indexed.
            candidate = (self.batches_root / requested).resolve()
            for item in specs:
                indexed = (self.batches_root / item.file).resolve()
                if indexed == candidate:
                    spec = item
                    break
        if spec is None:
            raise ApifyRunnerError(f"File is not in the authoritative batch index: {file_name}")
        path = (self.batches_root / spec.file).resolve()
        root = self.batches_root.resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ApifyRunnerError("Batch file escapes the configured batches directory") from exc
        if path.suffix.lower() != ".json" or not path.is_file():
            raise ApifyRunnerError(f"Batch JSON file not found: {path}")
        return spec, path

    def resolve_batch(self, batch_name: str) -> list[tuple[BatchSpec, Path]]:
        matches = [(spec, self.resolve_file(spec.file)[1]) for spec in self.list_batches() if spec.batch == batch_name]
        if not matches:
            raise ApifyRunnerError(f"Unknown batch: {batch_name}")
        return matches

    def load_input(self, path: Path) -> dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as stream:
                payload = json.load(stream)
        except (OSError, json.JSONDecodeError) as exc:
            raise ApifyRunnerError(f"Cannot read batch JSON {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ApifyRunnerError(f"Actor input must be a JSON object: {path}")
        self._reject_secrets(payload)
        return payload

    @classmethod
    def _reject_secrets(cls, value: Any, location: str = "input") -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                normalized = str(key).lower().replace("-", "_")
                if normalized in _SECRET_KEYS or any(part in normalized for part in ("token", "apikey", "password")):
                    raise ApifyRunnerError(f"Secret-like field is not allowed in actor input ({location}.{key})")
                cls._reject_secrets(child, f"{location}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                cls._reject_secrets(child, f"{location}[{index}]")

    @staticmethod
    def _load_tokens_from_file(token_file: Path) -> list[str]:
        """Load tokens from a file, one token per line. Ignores empty lines and comments."""
        if not token_file.is_file():
            raise ApifyRunnerError(f"Token file not found: {token_file}")
        try:
            content = token_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise ApifyRunnerError(f"Cannot read token file {token_file}: {exc}") from exc
        tokens = []
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                tokens.append(line)
        if not tokens:
            raise ApifyRunnerError(f"No valid tokens found in {token_file}")
        return tokens

    @staticmethod
    def token_from_file(token_file: str | Path, *, token_index: int = 0) -> str:
        """Load a specific token from a token file by index (0-based)."""
        tokens = ApifyBatchRunner._load_tokens_from_file(Path(token_file))
        if token_index < 0 or token_index >= len(tokens):
            raise ApifyRunnerError(
                f"Token index {token_index} out of range (file contains {len(tokens)} token(s))"
            )
        return tokens[token_index]

    @staticmethod
    def token_from_environment_or_prompt(
        *,
        prompt: bool = True,
        token_file: str | Path | None = None,
        token_index: int = 0,
    ) -> str:
        """Resolve a token from file, then environment, then an interactive prompt."""
        if token_file is not None:
            return ApifyBatchRunner.token_from_file(token_file, token_index=token_index)
        if token_index != 0:
            raise ApifyRunnerError("--token-index requires --token-file")
        token = os.environ.get("APIFY_TOKEN")
        if token:
            return token
        if not prompt:
            raise ApifyRunnerError("APIFY_TOKEN is not set (interactive prompt disabled)")
        token = getpass.getpass("Apify token: ").strip()
        if not token:
            raise ApifyRunnerError("An Apify token is required")
        return token

    def _client_for(self, token: str) -> Any:
        if self._client is None:
            self._client = httpx.Client(
                timeout=60.0,
                headers={"Authorization": f"Bearer {token}", "User-Agent": "RecommendationTraveller-ApifyRunner/1.0"},
            )
        return self._client

    @staticmethod
    def _raise_for_status(response: Any) -> None:
        try:
            response.raise_for_status()
        except Exception as exc:
            status = getattr(response, "status_code", "unknown")
            detail = ""
            try:
                detail = response.text[:500]
            except Exception:
                pass
            raise ApifyRunnerError(f"Apify API request failed ({status}): {detail}") from exc

    def verify_token(self, token: str) -> dict[str, Any]:
        if not token or not token.strip():
            raise ApifyRunnerError("An Apify token is required")
        response = self._client_for(token).get(f"{self.api_url}/users/me")
        self._raise_for_status(response)
        payload = response.json()
        if not isinstance(payload, dict):
            raise ApifyRunnerError("Apify token verification returned an unexpected response")
        return payload.get("data", payload)

    def _start_run(self, token: str, payload: dict[str, Any]) -> dict[str, Any]:
        actor_path = quote(self.actor_id.replace("/", "~"), safe="~")
        response = self._client_for(token).post(
            f"{self.api_url}/acts/{actor_path}/runs", json=payload
        )
        self._raise_for_status(response)
        result = response.json()
        data = result.get("data", result) if isinstance(result, dict) else result
        if not isinstance(data, dict) or not data.get("id"):
            raise ApifyRunnerError("Apify run response did not contain a run id")
        return data

    def _poll_run(self, token: str, run_id: str) -> dict[str, Any]:
        started = time.monotonic()
        while True:
            response = self._client_for(token).get(f"{self.api_url}/actor-runs/{quote(run_id, safe='')}")
            self._raise_for_status(response)
            body = response.json()
            data = body.get("data", body) if isinstance(body, dict) else body
            if not isinstance(data, dict):
                raise ApifyRunnerError("Apify run status response was invalid")
            status = str(data.get("status", "")).upper()
            if status in TERMINAL_STATUSES:
                if status != "SUCCEEDED":
                    raise ApifyRunnerError(f"Apify run {run_id} ended with status {status}")
                return data
            if time.monotonic() - started >= self.poll_timeout:
                raise ApifyRunnerError(f"Timed out waiting for Apify run {run_id}")
            if self.poll_interval:
                time.sleep(self.poll_interval)

    def _download_dataset(self, token: str, dataset_id: str) -> bytes:
        response = self._client_for(token).get(
            f"{self.api_url}/datasets/{quote(dataset_id, safe='')}/items",
            params={"clean": "true", "format": "json"},
        )
        self._raise_for_status(response)
        content = getattr(response, "content", None)
        if content is None:
            content = json.dumps(response.json(), ensure_ascii=False).encode("utf-8")
        if isinstance(content, str):
            content = content.encode("utf-8")
        try:
            parsed = json.loads(content)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ApifyRunnerError("Downloaded dataset is not valid JSON") from exc
        if not isinstance(parsed, list):
            raise ApifyRunnerError("Downloaded Apify dataset must be a JSON array")
        # Keep the service's raw bytes where possible, but normalize fake clients
        # and pretty JSON into a deterministic UTF-8 export.
        return content

    def _write_artifacts(self, spec: BatchSpec, input_path: Path, run: dict[str, Any], dataset: bytes) -> Path:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        destination = self.output_root / spec.region_id / date_str
        destination.mkdir(parents=True, exist_ok=True)
        places_path = destination / "places.json"
        # Avoid exposing partial/zero-byte exports if interrupted.
        with tempfile.NamedTemporaryFile("wb", delete=False, dir=destination, prefix=".places-", suffix=".tmp") as tmp:
            tmp.write(dataset)
            temporary = Path(tmp.name)
        temporary.replace(places_path)
        shutil.copyfile(input_path, destination / "input.json")
        checksum = hashlib.sha256(dataset).hexdigest()
        metadata = {
            "actor": self.actor_id,
            "run_id": run.get("id"),
            "dataset_id": run.get("defaultDatasetId") or run.get("datasetId"),
            "status": run.get("status", "SUCCEEDED"),
            "started_at": run.get("startedAt"),
            "finished_at": run.get("finishedAt"),
            "input_file": str(input_path),
            "region": spec.region_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "places_sha256": checksum,
        }
        (destination / "run.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (destination / "checksums.sha256").write_text(f"{checksum}  places.json\n", encoding="utf-8")
        return places_path

    def run_file(self, spec: BatchSpec, path: Path, token: str, *, import_after: bool = True) -> dict[str, Any]:
        payload = self.load_input(path)
        run = self._start_run(token, payload)
        run_id = str(run["id"])
        status = self._poll_run(token, run_id)
        dataset_id = status.get("defaultDatasetId") or status.get("datasetId") or run.get("defaultDatasetId")
        if not dataset_id:
            raise ApifyRunnerError(f"Apify run {run_id} has no dataset id")
        dataset = self._download_dataset(token, str(dataset_id))
        places_path = self._write_artifacts(spec, path, status, dataset)
        imported = None
        if import_after:
            factory = self.importer_factory
            if factory is None:
                from src.collectors.apify_google_maps import ApifyGoogleMapsImporter
                factory = ApifyGoogleMapsImporter
            imported = factory().import_dataset(str(places_path))
        return {"batch": spec.batch, "file": spec.file, "region": spec.region_id,
                "run_id": run_id, "dataset_id": dataset_id, "places_path": str(places_path),
                "imported": imported}

    def dry_run(self, targets: Iterable[tuple[BatchSpec, Path]]) -> list[dict[str, Any]]:
        planned = []
        for spec, path in targets:
            payload = self.load_input(path)
            planned.append({"batch": spec.batch, "file": spec.file, "kind": spec.kind,
                            "region": spec.region_id, "actor": self.actor_id,
                            "input_keys": sorted(payload), "would_contact_apify": False})
        return planned

    def targets(self, *, batch: str | None = None, file: str | None = None) -> list[tuple[BatchSpec, Path]]:
        if bool(batch) == bool(file):
            raise ApifyRunnerError("Specify exactly one of batch or file")
        if batch:
            return self.resolve_batch(batch)
        return [self.resolve_file(file or "")]

    def close(self) -> None:
        if self._client is not None and hasattr(self._client, "close"):
            self._client.close()


# Short alias for callers that prefer a service-style name.
ApifyRunner = ApifyBatchRunner
