"""Durable storage for approved crowdsourced catalog submissions.

The ML service intentionally uses a tiny JSON store rather than a second database:
submissions are small, append-only records and the source catalog remains the
frozen parquet dataset. Writes are atomic (temporary file + fsync + replace), so
an interrupted write cannot leave a partially written catalog. A process lock
also makes duplicate requests idempotent when requests arrive concurrently.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional


class CatalogStore:
    """Append-only, restart-safe store for approved catalog records."""

    FORMAT_VERSION = 1

    def __init__(self, path: Optional[str] = None) -> None:
        configured = path or os.getenv("CATALOG_SUBMISSIONS_PATH")
        if configured:
            self.path = Path(configured).expanduser()
        else:
            # Resolve from this module, not the process cwd, so restart commands
            # launched by a supervisor from another directory see the same file.
            self.path = Path(__file__).resolve().parents[2] / "Data" / "consolidated" / "approved_catalog_submissions.json"
        self._lock = threading.RLock()

    def _read_unlocked(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Unable to read catalog store {self.path}: {exc}") from exc

        if isinstance(payload, dict):
            if payload.get("format_version") != self.FORMAT_VERSION:
                raise RuntimeError(f"Unsupported catalog store format in {self.path}")
            records = payload.get("records", [])
        else:
            raise RuntimeError(f"Invalid catalog store envelope in {self.path}")
        if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
            raise RuntimeError(f"Invalid records in catalog store {self.path}")
        return records

    def list_records(self) -> List[Dict[str, Any]]:
        with self._lock:
            # Return copies so callers cannot mutate the store's in-memory view.
            return [dict(record) for record in self._read_unlocked()]

    def add_if_absent(self, record: Dict[str, Any]) -> bool:
        """Persist *record* unless its canonical ID already exists.

        Returns True only when a new record was committed. The check and write
        happen under one lock, making retries safe and deterministic.
        """
        canonical_id = str(record.get("canonical_id", "")).strip()
        if not canonical_id:
            raise ValueError("catalog records require a canonical_id")
        normalized = dict(record)
        normalized["canonical_id"] = canonical_id

        with self._lock:
            records = self._read_unlocked()
            if any(str(existing.get("canonical_id", "")).strip() == canonical_id for existing in records):
                return False
            records.append(normalized)
            self._write_unlocked(records)
            return True

    def _write_unlocked(self, records: List[Dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"format_version": self.FORMAT_VERSION, "records": records}
        temporary = self.path.with_name(f".{self.path.name}.tmp-{os.getpid()}-{threading.get_ident()}")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            # Directory fsync is not available on every supported platform.
            # The file fsync + atomic replace is sufficient on Windows/Linux;
            # best-effort directory sync is used where the platform supports it.
            try:
                directory_fd = os.open(str(self.path.parent), os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except (OSError, AttributeError):
                pass
        except OSError as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise RuntimeError(f"Unable to persist catalog store {self.path}: {exc}") from exc
