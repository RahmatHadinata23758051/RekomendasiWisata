# Consolidated Master Source Inventory

This report lists all the source files discovered for the HERA/Recommendation Traveller Lampung consolidation pipeline.

## Source Files

| Source Name | Path | Format | Row Count | Unique Canonical IDs | Duplicate IDs | Frozen | SHA-256 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| canonical_verified | data/canonical/attractions_master_verified.parquet | parquet | 3130 | 3130 | 0 | true | `d9dd9500` |
| attractions_candidates | data/canonical/attractions_candidates.parquet | parquet | 1048 | 1048 | 0 | true | `4f5dc5c3` |
| place_metadata | data/enrichment/metadata/place_metadata.parquet | parquet | 300 | 300 | 0 | true | `f27d66b7` |
| reviews | data/enrichment/final/reviews.parquet | parquet | 924 | 172 | 752 | true | `6fdef9b6` |
| facilities | data/enrichment/metadata/facilities.parquet | parquet | 596 | 223 | 373 | false | `ae744f5b` |
| opening_hours | data/enrichment/metadata/opening_hours.parquet | parquet | 692 | 99 | 593 | false | `02ad26f1` |
| operational_status | data/enrichment/metadata/operational_status.parquet | parquet | 300 | 300 | 0 | false | `d98a7f7d` |
| research_price_candidates | data/enrichment/price/validation/research_price_candidates.csv | csv | 11 | 11 | 0 | true | `b0f9758b` |
| price_observations | data/enrichment/price/research/price_observations.csv | csv | 32 | 8 | 24 | true | `322b6f2b` |
| prices | data/enrichment/price/final/prices.csv | csv | 30 | 8 | 22 | true | `c40a3399` |
| external_price_verification_queue | data/enrichment/price/research/external_price_verification_queue.csv | csv | 11 | 11 | 0 | true | `24e3456c` |
| external_verification_coverage | data/enrichment/price/external/external_verification_coverage.csv | csv | 11 | 11 | 0 | true | `13d12cf0` |
| prices_external_verified | data/enrichment/price/final/prices_external_verified.csv | csv | 0 | 0 | 0 | true | `9e82d811` |
