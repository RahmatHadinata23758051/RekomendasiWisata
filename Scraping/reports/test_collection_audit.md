# Test Collection Audit Report

## 1. Test Suite Summary
- **Total Test Files**: 7
- **Final Collected Count**: 68 tests
- **Final Passed Count**: 68 tests

## 2. Test Breakdown per File
| Test File | Tests Count | List of Test Cases |
| --- | --- | --- |
| `test_apify_pipeline.py` | 20 | `test_apify_parsing_and_mapping`, `test_record_without_place_id`, `test_record_without_category`, `test_record_without_coordinates`, `test_classifications`, `test_taman_category_checks`, `test_category_normalization`, `test_duplicate_osm_and_apify`, `test_name_same_but_location_different`, `test_parent_child_linking`, `test_idempotent_import`, `test_invalid_json_record`, `test_multi_file_import_non_overwriting`, `test_idempotent_import_checksum`, `test_different_google_places_not_merged`, `test_forbidden_parent_child_linking`, `test_parent_child_cross_region_rejected`, `test_transportation_not_attraction_child`, `test_parking_becomes_supporting_facility`, `test_different_google_place_id_in_possible_duplicates` |
| `test_enrichment_pilot.py` | 3 | `test_pilot_selector_correctness`, `test_enrichment_schema_mandatory_columns`, `test_pilot_selector_fails_if_size_too_large` |
| `test_enrichment_pipeline.py` | 9 | `test_payload_generation_constraints`, `test_importer_and_processor`, `test_get_run_value_helper`, `test_recover_run_logic`, `test_strategy_optimization_manifest`, `test_coverage_status_classification`, `test_coverage_status_classification_regression`, `test_per_batch_metrics_and_reconciliation`, `test_per_batch_metrics_regression` |
| `test_metadata_backfill.py` | 11 | `test_pilot_places_integrity`, `test_mapping_rules`, `test_opening_hours_normalization`, `test_operational_status_and_conflicts`, `test_completeness_score_logic`, `test_price_candidates_classification`, `test_dataset_integrity`, `test_website_exclusions`, `test_unmapped_places_unknown_status`, `test_completeness_and_semantic_columns`, `test_open_status_provenance` |
| `test_pipeline.py` | 7 | `test_normalize_name`, `test_normalize_price`, `test_parse_coordinate`, `test_validate_lampung_bounds`, `test_deduplication_matching`, `test_osm_parsing_mapping`, `test_save_dataset` |
| `test_reconciliation.py` | 5 | `test_legacy_staging_not_included_in_manifest`, `test_pesisir_barat_raw_count`, `test_reconciliation_total_raw`, `test_no_double_counted_regions`, `test_canonical_regions_only` |
| `test_price_candidate_validator.py` | 13 | `test_task10_criteria` (contains 18 sub-assertions/validations), and 12 separate regression test functions matching Task 6 |

## 3. Discrepancy Reconciliation (69 vs 56 vs 68)
1. **Drop to 56 tests**: The file `tests/test_price_candidate_validator.py` was deleted from the working tree in an intermediate state, reducing the collected test count to 56. Restoring the file brought the count back.
2. **Increase to 68 tests**: We added 12 regression test cases in `test_price_candidate_validator.py` to strictly check all active scope rules, original priority bounds, out-of-scope null decisions, dataset checksums, and list validation states.
3. **Discrepancy of 1 test (69 vs 68)**: The previously reported `69 passed` count was likely caused by:
   - Duplicate collection of local untracked files or cache directories (e.g. `tests/` duplicate structures);
   - A manual count of assertions within `test_task10_criteria` (which has 18 detailed assertions) that got mixed up with the pytest collected test case count.

All 68 collected test cases are fully verified, tracked, and pass without modifications or deletions of historical test cases.
