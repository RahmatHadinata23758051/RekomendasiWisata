"""Backfill Google aggregate ratings into the frozen consolidated master.

Why this exists
---------------
``consolidated_master.py`` derives ``review_rating_mean`` only from scraped
review rows. That leaves the 2,958 places without review rows with no rating
signal at all, even though the raw Apify export already carries ``totalScore``
and ``reviewsCount`` for most of them.

Rebuilding the master through ``build-consolidated-master`` is not safe today:
the canonical snapshot recorded in ``consolidated_master_manifest_full.json``
(sha256 ``d9dd95...``) no longer exists on disk and the current
``attractions_master_verified.parquet`` has zero ``canonical_id`` overlap with
the frozen master. Any rebuild would mint new IDs and break the frontend, the
ML API and the RAG index.

This module therefore performs an additive, provenance-preserving backfill:

* never overwrites ``review_rating_mean`` (review-text semantics stay intact);
* only adds new ``google_*`` columns;
* requires an exact normalized-name match *and* a coordinate match within
  ``max_distance_m`` so same-name places in other regencies are rejected.
"""

from __future__ import annotations

import glob
import hashlib
import json
import logging
import math
import os
import re
from typing import Any

import pandas as pd

logger = logging.getLogger("scraper.google_rating_backfill")

MAX_MATCH_DISTANCE_M = 300.0
EARTH_RADIUS_M = 6_371_000.0
# Bayesian prior: shrinks small-sample Google ratings toward the catalog mean.
# The median matched place has only 8 reviews, so a raw 5.0 from one review is
# weak evidence. m=20 (~2.5x the median) keeps such places from outranking
# places with hundreds of reviews while still letting them rise above average.
RATING_PRIOR_WEIGHT = 20.0
_NAME_NOISE = re.compile(r"[^a-z0-9 ]+")
_WHITESPACE = re.compile(r"\s+")

MASTER_CANDIDATES = (
    "Data/consolidated/attractions_enrichment_master_full.parquet",
    "Scraping/data/enrichment/consolidated/attractions_enrichment_master_full.parquet",
    "data/enrichment/consolidated/attractions_enrichment_master_full.parquet",
    "../Machine-Learning/Data/consolidated/attractions_enrichment_master_full.parquet",
)

DATA_DIR_CANDIDATES = (
    "Data",
    "Machine-Learning/Data",
    "../Machine-Learning/Data",
    "../Data",
)

# Columns added by this backfill. Kept as a module constant so callers and
# tests can assert the contract without duplicating strings.
NEW_COLUMNS = (
    "google_rating",
    "google_review_count",
    "google_rating_weighted",
    "google_place_id",
    "google_rating_observed_at",
    "google_rating_match_distance_m",
)


def normalize_name(value: Any) -> str:
    """Lowercase, strip accents-insensitive punctuation, collapse whitespace."""
    text = str(value or "").lower().strip()
    text = _NAME_NOISE.sub(" ", text)
    return _WHITESPACE.sub(" ", text).strip()


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def resolve_master_path(explicit: str | None = None) -> str:
    candidates = (explicit,) if explicit else ()
    for candidate in (*candidates, *MASTER_CANDIDATES):
        if candidate and os.path.exists(candidate):
            return candidate
    raise FileNotFoundError(
        "Consolidated master parquet not found. Looked in: "
        + ", ".join(str(p) for p in (*candidates, *MASTER_CANDIDATES))
    )


def resolve_data_dir(explicit: str | None = None) -> str:
    candidates = (explicit,) if explicit else ()
    for candidate in (*candidates, *DATA_DIR_CANDIDATES):
        if candidate and os.path.isdir(candidate) and glob.glob(os.path.join(candidate, "*.json")):
            return candidate
    raise FileNotFoundError(
        "Raw Apify export directory not found. Looked in: "
        + ", ".join(str(p) for p in (*candidates, *DATA_DIR_CANDIDATES))
    )


def _candidate_from_record(record: dict[str, Any]) -> dict[str, Any] | None:
    """Return a normalized rating candidate, or None when it is unusable."""
    rating = record.get("totalScore")
    if rating is None or pd.isna(rating):
        return None
    location = record.get("location") or {}
    lat, lng = location.get("lat"), location.get("lng")
    if lat is None or lng is None or pd.isna(lat) or pd.isna(lng):
        return None
    try:
        rating = float(rating)
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return None
    if not 0.0 <= rating <= 5.0:
        return None
    review_count = record.get("reviewsCount")
    return {
        "rating": rating,
        "review_count": None if review_count is None else float(review_count),
        "place_id": record.get("placeId"),
        "observed_at": record.get("scrapedAt"),
        "lat": lat,
        "lng": lng,
    }


def load_raw_rating_index(
    data_dir: str,
    pattern: str = "*.json",
) -> dict[str, list[dict[str, Any]]]:
    """Index raw Apify exports by normalized name.

    ``INPUT.json`` (the actor input, not a dataset) is skipped, matching the
    existing ``Model/api/app.py`` behaviour.
    """
    index: dict[str, list[dict[str, Any]]] = {}
    files = 0
    records = 0
    usable = 0
    for path in sorted(glob.glob(os.path.join(data_dir, pattern))):
        if "INPUT" in os.path.basename(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as stream:
                payload = json.load(stream)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Skipping unreadable raw export %s: %s", path, exc)
            continue
        if not isinstance(payload, list):
            logger.warning("Skipping non-array raw export: %s", path)
            continue
        files += 1
        for record in payload:
            records += 1
            if not isinstance(record, dict):
                continue
            name = normalize_name(record.get("title"))
            if not name:
                continue
            candidate = _candidate_from_record(record)
            if candidate is None:
                continue
            index.setdefault(name, []).append(candidate)
            usable += 1
    logger.info(
        "Loaded %s raw file(s): %s records, %s usable ratings, %s unique names",
        files,
        records,
        usable,
        len(index),
    )
    return index


def backfill_google_ratings(
    master: pd.DataFrame,
    index: dict[str, list[dict[str, Any]]],
    *,
    max_distance_m: float = MAX_MATCH_DISTANCE_M,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Add ``google_*`` columns to ``master`` without mutating the input frame."""
    out = master.copy()
    for column in (
        "google_rating",
        "google_review_count",
        "google_rating_weighted",
        "google_rating_match_distance_m",
    ):
        out[column] = pd.Series(float("nan"), index=out.index, dtype="float64")
    for column in ("google_place_id", "google_rating_observed_at"):
        out[column] = pd.Series(None, index=out.index, dtype="object")

    matched = 0
    ambiguous = 0
    distance_rejected = 0
    no_name_match = 0

    for idx, row in out.iterrows():
        name = normalize_name(row.get("name"))
        candidates = index.get(name) if name else None
        if not candidates:
            no_name_match += 1
            continue
        if len(candidates) > 1:
            ambiguous += 1

        lat, lng = row.get("latitude"), row.get("longitude")
        if lat is None or lng is None or pd.isna(lat) or pd.isna(lng):
            no_name_match += 1
            continue

        best = min(
            candidates,
            key=lambda item: haversine_m(float(lat), float(lng), item["lat"], item["lng"]),
        )
        distance = haversine_m(float(lat), float(lng), best["lat"], best["lng"])
        if distance > max_distance_m:
            distance_rejected += 1
            continue

        out.at[idx, "google_rating"] = best["rating"]
        out.at[idx, "google_review_count"] = best["review_count"]
        out.at[idx, "google_place_id"] = best["place_id"]
        out.at[idx, "google_rating_observed_at"] = best["observed_at"]
        out.at[idx, "google_rating_match_distance_m"] = round(distance, 2)
        matched += 1

    # Bayesian weighted rating for ranking. Display keeps the raw Google value;
    # ranking uses this so a lone 5.0 does not outrank a 4.8 with thousands of
    # reviews. Places with a rating but no review count keep the raw value.
    rated_mask = out["google_rating"].notna()
    prior_mean = float("nan")
    weighted_applied = 0
    if rated_mask.any():
        prior_mean = float(out.loc[rated_mask, "google_rating"].mean())
        review_counts = pd.to_numeric(
            out.loc[rated_mask, "google_review_count"], errors="coerce"
        ).fillna(0.0)
        raw = out.loc[rated_mask, "google_rating"].astype(float)
        shrunk = (review_counts * raw + RATING_PRIOR_WEIGHT * prior_mean) / (
            review_counts + RATING_PRIOR_WEIGHT
        )
        weighted = raw.where(review_counts <= 0, shrunk)
        out.loc[rated_mask, "google_rating_weighted"] = weighted
        weighted_applied = int(rated_mask.sum())

    has_review_rating = out["review_rating_mean"].notna() if "review_rating_mean" in out else pd.Series(False, index=out.index)
    coverage_before = int(has_review_rating.sum())
    coverage_after = int((has_review_rating | out["google_rating"].notna()).sum())

    report = {
        "total_rows": int(len(out)),
        "matched_within_threshold": matched,
        "rejected_distance": distance_rejected,
        "no_name_match": no_name_match,
        "ambiguous_names": ambiguous,
        "max_distance_m": max_distance_m,
        "rating_coverage_before": coverage_before,
        "rating_coverage_after": coverage_after,
        "newly_covered": coverage_after - coverage_before,
        "weighted_rating_applied": weighted_applied,
        "rating_prior_weight": RATING_PRIOR_WEIGHT,
        "rating_prior_mean": None if pd.isna(prior_mean) else round(prior_mean, 6),
    }
    logger.info("Google rating backfill report: %s", report)
    return out, report


def write_master_artifacts(
    master: pd.DataFrame,
    output_dir: str,
    *,
    filename_prefix: str = "attractions_enrichment_master_full",
) -> dict[str, str]:
    """Write csv/parquet/jsonl, mirroring ``consolidated_master`` output style.

    Only formats already present in ``output_dir`` are refreshed; a directory
    that tracks the parquet alone (``Data/consolidated``) is not polluted with
    new csv/jsonl copies.
    """
    os.makedirs(output_dir, exist_ok=True)
    known = {
        "csv": os.path.join(output_dir, f"{filename_prefix}.csv"),
        "parquet": os.path.join(output_dir, f"{filename_prefix}.parquet"),
        "jsonl": os.path.join(output_dir, f"{filename_prefix}.jsonl"),
    }
    present = {key: path for key, path in known.items() if os.path.exists(path)}
    if not present:
        present = known

    if "csv" in present:
        master.to_csv(present["csv"], index=False, encoding="utf-8")
    if "parquet" in present:
        master.to_parquet(present["parquet"], index=False)
    if "jsonl" in present:
        with open(present["jsonl"], "w", encoding="utf-8") as stream:
            for _, row in master.iterrows():
                record = row.to_dict()
                for key, value in record.items():
                    if pd.isna(value):
                        record[key] = None
                stream.write(json.dumps(record) + "\n")
    return present


def update_manifest(
    manifest_path: str,
    report: dict[str, Any],
    artifacts: dict[str, str],
) -> dict[str, Any] | None:
    """Record the backfill as an additive patch on the existing manifest.

    The original build inputs and their checksums are left untouched: they are
    still the inputs that produced the base master. Only the output checksums
    and a new ``enrichment_patches`` entry change.
    """
    if not os.path.exists(manifest_path):
        return None
    with open(manifest_path, "r", encoding="utf-8") as stream:
        manifest = json.load(stream)

    def sha256(path: str) -> str:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                digest.update(chunk)
        return digest.hexdigest()

    checksums = {}
    for key, path in artifacts.items():
        if os.path.exists(path):
            checksums[os.path.basename(path)] = sha256(path)
    manifest.setdefault("output_checksums", {}).update(checksums)

    patches = manifest.setdefault("enrichment_patches", [])
    # Re-running the CLI must replace the previous record, not stack duplicates.
    patches = [item for item in patches if item.get("patch") != "google_rating_backfill"]
    patches.append(
        {
            "patch": "google_rating_backfill",
            "applied_at": pd.Timestamp.now(tz="UTC").isoformat(),
            "source": "raw Apify exports (Data/*.json)",
            "matching": f"normalized name + haversine <= {report['max_distance_m']}m",
            "report": report,
            "output_checksums": checksums,
        }
    )
    manifest["enrichment_patches"] = patches
    base_version = re.sub(
        r"(\+google_rating_backfill\.\d+)+$", "", manifest.get("master_version", "")
    )
    manifest["master_version"] = base_version + "+google_rating_backfill.1"
    with open(manifest_path, "w", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2)
    return manifest


def main(
    master_path: str | None = None,
    data_dir: str | None = None,
    max_distance_m: float = MAX_MATCH_DISTANCE_M,
    mirror_dirs: list[str] | None = None,
) -> dict[str, Any]:
    master_path = resolve_master_path(master_path)
    data_dir = resolve_data_dir(data_dir)
    logger.info("Backfilling Google ratings from %s into %s", data_dir, master_path)

    master = pd.read_parquet(master_path)
    index = load_raw_rating_index(data_dir)
    updated, report = backfill_google_ratings(master, index, max_distance_m=max_distance_m)

    output_dir = os.path.dirname(master_path) or "."
    artifacts = write_master_artifacts(updated, output_dir)

    for mirror in mirror_dirs or ():
        if os.path.abspath(mirror) == os.path.abspath(output_dir):
            continue
        mirror_artifacts = write_master_artifacts(updated, mirror)
        update_manifest(
            os.path.join(mirror, "consolidated_master_manifest_full.json"),
            report,
            mirror_artifacts,
        )

    update_manifest(
        os.path.join(output_dir, "consolidated_master_manifest_full.json"),
        report,
        artifacts,
    )

    report["master_path"] = master_path
    report["data_dir"] = data_dir
    report["artifacts"] = artifacts
    return report


if __name__ == "__main__":  # pragma: no cover - manual entry point
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    print(json.dumps(main(), indent=2))
