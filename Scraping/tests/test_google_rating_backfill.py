import json

import pandas as pd
import pytest

from src.enrichment.google_rating_backfill import (
    NEW_COLUMNS,
    backfill_google_ratings,
    haversine_m,
    load_raw_rating_index,
    normalize_name,
    update_manifest,
)


def _master_row(**overrides):
    base = {
        "canonical_id": "can_test0001",
        "name": "Pantai Mutun",
        "latitude": -5.5,
        "longitude": 105.25,
        "review_rating_mean": float("nan"),
    }
    base.update(overrides)
    return base


def _raw_record(title, lat, lng, rating=4.5, reviews=120, place_id="place-1", scraped_at="2026-01-01T00:00:00Z"):
    return {
        "title": title,
        "totalScore": rating,
        "reviewsCount": reviews,
        "placeId": place_id,
        "scrapedAt": scraped_at,
        "location": {"lat": lat, "lng": lng},
    }


def test_normalize_name_ignores_case_and_punctuation():
    assert normalize_name("  Pantai   MUTUN!!! ") == "pantai mutun"
    assert normalize_name("Pantai Mutun") == normalize_name("pantai mutun")


def test_haversine_is_zero_for_same_point_and_positive_otherwise():
    assert haversine_m(-5.5, 105.25, -5.5, 105.25) == 0.0
    assert haversine_m(-5.5, 105.25, -5.5, 105.26) > 0.0


def test_backfill_matches_name_and_coordinates():
    master = pd.DataFrame([_master_row()])
    index = {"pantai mutun": [{"rating": 4.5, "review_count": 120.0, "place_id": "p1", "observed_at": "t", "lat": -5.5, "lng": 105.25}]}

    updated, report = backfill_google_ratings(master, index)

    assert report["matched_within_threshold"] == 1
    assert report["rating_coverage_before"] == 0
    assert report["rating_coverage_after"] == 1
    assert updated.loc[0, "google_rating"] == pytest.approx(4.5)
    assert updated.loc[0, "google_review_count"] == pytest.approx(120.0)
    assert updated.loc[0, "google_place_id"] == "p1"
    for column in NEW_COLUMNS:
        assert column in updated.columns


def test_backfill_rejects_far_away_same_name_place():
    # Same name, ~180 km away -> must not be accepted.
    master = pd.DataFrame([_master_row()])
    index = {
        "pantai mutun": [
            {"rating": 4.9, "review_count": 9.0, "place_id": "far", "observed_at": "t", "lat": -4.0, "lng": 105.25}
        ]
    }

    updated, report = backfill_google_ratings(master, index)

    assert report["matched_within_threshold"] == 0
    assert report["rejected_distance"] == 1
    assert pd.isna(updated.loc[0, "google_rating"])


def test_backfill_picks_nearest_candidate_for_ambiguous_names():
    master = pd.DataFrame([_master_row()])
    index = {
        "pantai mutun": [
            {"rating": 3.0, "review_count": 5.0, "place_id": "near", "observed_at": "t", "lat": -5.5001, "lng": 105.2501},
            {"rating": 5.0, "review_count": 500.0, "place_id": "far", "observed_at": "t", "lat": -5.6, "lng": 105.35},
        ]
    }

    updated, report = backfill_google_ratings(master, index)

    assert report["ambiguous_names"] == 1
    assert updated.loc[0, "google_place_id"] == "near"
    assert updated.loc[0, "google_rating"] == pytest.approx(3.0)


def test_backfill_never_overwrites_review_rating_mean():
    master = pd.DataFrame([_master_row(review_rating_mean=4.0)])
    index = {"pantai mutun": [{"rating": 5.0, "review_count": 10.0, "place_id": "p1", "observed_at": "t", "lat": -5.5, "lng": 105.25}]}

    updated, report = backfill_google_ratings(master, index)

    assert updated.loc[0, "review_rating_mean"] == pytest.approx(4.0)
    # Google rating is stored separately; coverage is not double counted.
    assert updated.loc[0, "google_rating"] == pytest.approx(5.0)
    assert report["rating_coverage_before"] == 1
    assert report["rating_coverage_after"] == 1
    assert report["newly_covered"] == 0


def test_backfill_is_idempotent():
    master = pd.DataFrame([_master_row()])
    index = {"pantai mutun": [{"rating": 4.5, "review_count": 120.0, "place_id": "p1", "observed_at": "t", "lat": -5.5, "lng": 105.25}]}

    first, _ = backfill_google_ratings(master, index)
    second, _ = backfill_google_ratings(first, index)

    pd.testing.assert_frame_equal(first, second)


def test_weighted_rating_shrinks_small_samples_toward_prior():
    master = pd.DataFrame(
        [
            _master_row(canonical_id="can_low_sample", name="Low Sample", latitude=-5.5, longitude=105.25),
            _master_row(canonical_id="can_high_sample", name="High Sample", latitude=-5.6, longitude=105.35),
        ]
    )
    index = {
        "low sample": [{"rating": 5.0, "review_count": 1.0, "place_id": "p1", "observed_at": "t", "lat": -5.5, "lng": 105.25}],
        "high sample": [{"rating": 4.0, "review_count": 100.0, "place_id": "p2", "observed_at": "t", "lat": -5.6, "lng": 105.35}],
    }

    updated, report = backfill_google_ratings(master, index)

    prior_mean = (5.0 + 4.0) / 2.0
    prior_weight = report["rating_prior_weight"]
    low = updated.loc[updated["canonical_id"] == "can_low_sample", "google_rating_weighted"].iloc[0]
    high = updated.loc[updated["canonical_id"] == "can_high_sample", "google_rating_weighted"].iloc[0]

    assert report["rating_prior_mean"] == pytest.approx(prior_mean)
    assert report["weighted_rating_applied"] == 2
    assert low == pytest.approx((1 * 5.0 + prior_weight * prior_mean) / (1 + prior_weight))
    assert high == pytest.approx((100 * 4.0 + prior_weight * prior_mean) / (100 + prior_weight))
    # The low-sample place is pulled down and the high-sample place barely moves.
    assert low < 5.0
    assert high == pytest.approx(4.0, abs=0.1)
    # Raw display value is untouched.
    assert updated.loc[updated["canonical_id"] == "can_low_sample", "google_rating"].iloc[0] == pytest.approx(5.0)
    assert "google_rating_weighted" in NEW_COLUMNS


def test_weighted_ranking_rejects_lone_perfect_score_above_well_reviewed_place():
    # A realistic prior needs more than two rows: the global mean must not be
    # dominated by the two extremes under test.
    rows = [
        _master_row(canonical_id="can_one", name="One Review", latitude=-5.5, longitude=105.25),
        _master_row(canonical_id="can_many", name="Many Reviews", latitude=-5.6, longitude=105.35),
    ]
    index = {
        "one review": [{"rating": 5.0, "review_count": 1.0, "place_id": "p1", "observed_at": "t", "lat": -5.5, "lng": 105.25}],
        "many reviews": [{"rating": 4.8, "review_count": 5000.0, "place_id": "p2", "observed_at": "t", "lat": -5.6, "lng": 105.35}],
    }
    for n in range(10):
        name = f"filler {n}"
        lat, lng = -5.0 - n * 0.01, 105.0 + n * 0.01
        rows.append(_master_row(canonical_id=f"can_filler_{n}", name=name, latitude=lat, longitude=lng))
        index[name] = [{"rating": 4.0, "review_count": 100.0, "place_id": f"pf{n}", "observed_at": "t", "lat": lat, "lng": lng}]

    updated, _ = backfill_google_ratings(pd.DataFrame(rows), index)
    one = updated.loc[updated["canonical_id"] == "can_one", "google_rating_weighted"].iloc[0]
    many = updated.loc[updated["canonical_id"] == "can_many", "google_rating_weighted"].iloc[0]

    # Display still shows 5.0, but ranking puts the well-reviewed 4.8 first.
    assert updated.loc[updated["canonical_id"] == "can_one", "google_rating"].iloc[0] == pytest.approx(5.0)
    assert many > one


def test_manifest_patch_is_idempotent(tmp_path):
    artifact = tmp_path / "master.parquet"
    artifact.write_bytes(b"data")
    manifest_path = tmp_path / "consolidated_master_manifest_full.json"
    manifest_path.write_text(
        json.dumps({"master_version": "base", "enrichment_patches": [{"patch": "other"}]}),
        encoding="utf-8",
    )

    for _ in range(2):
        update_manifest(
            str(manifest_path),
            {"max_distance_m": 300.0},
            {"parquet": str(artifact)},
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["master_version"] == "base+google_rating_backfill.1"
    assert [item["patch"] for item in manifest["enrichment_patches"]] == [
        "other",
        "google_rating_backfill",
    ]


def test_backfill_skips_rows_without_coordinates():
    master = pd.DataFrame([_master_row(latitude=float("nan"))])
    index = {"pantai mutun": [{"rating": 4.5, "review_count": 1.0, "place_id": "p1", "observed_at": "t", "lat": -5.5, "lng": 105.25}]}

    updated, report = backfill_google_ratings(master, index)

    assert report["matched_within_threshold"] == 0
    assert pd.isna(updated.loc[0, "google_rating"])


def test_load_raw_rating_index_skips_inputs_and_incomplete_records(tmp_path):
    dataset = [
        _raw_record("Pantai Mutun", -5.5, 105.25),
        {"title": "No Score", "location": {"lat": -5.5, "lng": 105.25}},
        {"title": "No Location", "totalScore": 4.0},
        "not-a-dict",
    ]
    (tmp_path / "dataset_places.json").write_text(json.dumps(dataset), encoding="utf-8")
    (tmp_path / "INPUT.json").write_text(json.dumps([_raw_record("Ignored", -5.5, 105.25)]), encoding="utf-8")

    index = load_raw_rating_index(str(tmp_path))

    assert list(index) == ["pantai mutun"]
    assert index["pantai mutun"][0]["rating"] == pytest.approx(4.5)
