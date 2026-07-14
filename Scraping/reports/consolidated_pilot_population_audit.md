# Consolidated Pilot Population Audit

This report audits the deterministic 300-place pilot population across the review, metadata, and price validation phases.

## Population Summary

| Metric | Value |
| --- | --- |
| total_pilot_canonical_ids | 300 |
| total_verified_canonical_attractions | 3130 |
| pilot_matched_in_canonical | 300 |
| pilot_matched_in_metadata | 300 |
| pilot_matched_in_price_candidates | 300 |
| pilot_eligible_for_reviews | 271 |
| pilot_not_eligible_for_reviews | 29 |
| pilot_with_actual_reviews_scraped | 172 |

## Audit Observations

- All 300 pilot places exist in the verified canonical attractions dataset.
- Exactly 300 pilot places have backfilled metadata coverage in `place_metadata.parquet`.
- Exactly 300 pilot places have price validation records in `pilot_price_candidates.csv`.
- 271 pilot places were eligible for review scraping (having a Google Place ID), while 29 unmapped places were ineligible.
- 172 pilot places have actual scraped review payloads available in `reviews.parquet`.
