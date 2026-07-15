# Metadata Scaling Source Inventory Report

| Source Name | File Path | Format | Exists | Rows | Unique IDs | Dupes | Join Key | Frozen | SHA256 | Role |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| verified_canonical_attractions_parquet | data/canonical/attractions_master_verified.parquet | parquet | True | 3130 | 3130 | 0 | canonical_id | True | d9dd9500c0ab | canonical_verified_attractions |
| verified_canonical_attractions_jsonl | data/canonical/attractions_master_verified.jsonl | jsonl | True | 3130 | 3130 | 0 | canonical_id | True | f2b204c78e6c | canonical_verified_attractions |
| canonical_source_mappings | data/canonical/attraction_sources.parquet | parquet | True | 4207 | 4207 | 0 | source_record_id | True | b12962e642d3 | canonical_source_mappings |
| metadata_pilot_output | data/enrichment/metadata/place_metadata.parquet | parquet | True | 300 | 300 | 0 | canonical_id | False | f27d66b7f408 | metadata_pilot_output |
| source_registry | data/canonical/source_mappings.parquet | parquet | True | 330 | 169 | 161 | source_record_id | True | 2ad8bc3b8902 | source_registry |
| existing_metadata_output | data/enrichment/metadata/place_metadata.parquet | parquet | True | 300 | 300 | 0 | canonical_id | False | f27d66b7f408 | existing_metadata_output |
| opening_hours_raw_data | data/enrichment/metadata/opening_hours.parquet | parquet | True | 692 | 99 | 593 | canonical_id | False | 02ad26f1d689 | opening_hours_raw_data |
| facilities_raw_data | data/enrichment/metadata/facilities.parquet | parquet | True | 596 | 223 | 373 | canonical_id | False | ae744f5b0a15 | facilities_raw_data |
| operational_status_data | data/enrichment/metadata/operational_status.parquet | parquet | True | 300 | 300 | 0 | canonical_id | False | d98a7f7dcc47 | operational_status_data |
| pilot_population | data/enrichment/consolidated/pilot_population.csv | csv | True | 300 | 300 | 0 | canonical_id | True | 6c5080dc0df2 | pilot_population_reference |
| attractions_enrichment_master_pilot | data/enrichment/consolidated/attractions_enrichment_master_pilot.parquet | parquet | True | 300 | 300 | 0 | canonical_id | True | 9847866a2b6d | master_pilot_output |
| consolidated_master_manifest | data/enrichment/consolidated/consolidated_master_manifest.json | json | True | 0 | 0 | 0 |  | True | b284ca685e5a | pilot_manifest |
| raw_google_maps_apify | data/raw/apify/google_maps/**/places.json | json | True | 4539 | 0 | 0 | placeId | True | N/A (Multi-f | raw_scraper_output |
| raw_osm_source | data/raw/osm/**/response.json | json | True | 493 | 0 | 0 | id | True | N/A (Multi-f | raw_osm_output |
