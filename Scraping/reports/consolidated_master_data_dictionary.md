# Consolidated Master Data Dictionary

This document acts as the authoritative data dictionary for the Consolidated Enrichment Master Dataset.

## Field Specifications

| Field Name | Data Type | Nullable | Allowed Values / Constraints | Description | Source File | Aggregation Method |
| --- | --- | --- | --- | --- | --- | --- |
| canonical_id | string | False | Pattern: ^can_[a-f0-9]{12}$ | Immutable primary key of canonical attraction | pilot_places.parquet | Direct |
| name | string | False | Any non-empty string | Canonical name of the attraction | pilot_places.parquet | Direct |
| normalized_name | string | False | Any non-empty string | Normalized lowercase name for index matching | attractions_master_verified.parquet | Direct/Join |
| primary_category | string | False | beach, waterfall, island, agrotourism, park, recreation, forest, camping, hill, mountain, religious, museum, history, culture, education, river, lake, family, other | Primary categorized classification of attraction | pilot_places.parquet | Direct |
| category_group | string | False | nature, cultural, recreation, other | High-level categorized group | Derived from primary_category | Conditional mapping |
| region | string | False | Kabupaten and Kota in Lampung | Region name of the attraction | pilot_places.parquet | Direct |
| district | string | True | Any string or empty | District name (kecamatan) | attractions_master_verified.parquet | Join |
| city_or_regency | string | False | Any non-empty string | City or Regency (kabupaten/kota) | attractions_master_verified.parquet | Join |
| latitude | float | False | -90 to 90 | Geographic latitude coordinate | pilot_places.parquet | Direct |
| longitude | float | False | -180 to 180 | Geographic longitude coordinate | pilot_places.parquet | Direct |
| canonical_status | string | False | verified, candidate | Classification status of attraction | attractions_master_verified.parquet / attractions_candidates.parquet | Lookup |
| source_count | integer | False | >= 1 | Total number of mapped raw source records | pilot_places.parquet | Direct |
| has_google_maps_source | boolean | False | true, false | Flag indicating if Google Maps source mapping exists | pilot_places.parquet | Direct |
| has_osm_source | boolean | False | true, false | Flag indicating if OpenStreetMap source mapping exists | attraction_sources.parquet | Boolean match |
| has_apify_source | boolean | False | true, false | Flag indicating if Apify Google Maps mapping exists | pilot_places.parquet | Boolean match |
| source_types | string | False | JSON list e.g. ["google_places", "osm"] | List of all raw source formats contributing to entity | attraction_sources.parquet | List aggregation |
| source_conflict_count | integer | False | >= 0 | Number of conflicted key attributes between raw sources | metadata_conflicts.csv | Join & Count |
| review_eligible | boolean | False | true, false | Whether place was eligible for review scrape (has google_place_id) | pilot_gp | Join |
| review_attempted | boolean | False | true, false | Whether review scrape was attempted in pilot | pilot_gp | Join |
| has_reviews | boolean | False | true, false | Flag indicating presence of reviews in final review dataset | reviews.parquet | Join |
| review_count | integer | False | >= 0 | Total number of reviews in final reviews layer | reviews.parquet | Group Count |
| review_rating_mean | float | True | 1.0 to 5.0 or null | Average rating of reviews | reviews.parquet | Mean |
| review_rating_median | float | True | 1.0 to 5.0 or null | Median rating of reviews | reviews.parquet | Median |
| review_rating_min | float | True | 1.0 to 5.0 or null | Minimum rating among reviews | reviews.parquet | Min |
| review_rating_max | float | True | 1.0 to 5.0 or null | Maximum rating among reviews | reviews.parquet | Max |
| review_text_count | integer | False | >= 0 | Total number of reviews with non-empty review text | reviews.parquet | Count non-empty |
| review_latest_at | string | True | ISO Timestamp or null | Latest review date | reviews.parquet | Max date |
| review_oldest_at | string | True | ISO Timestamp or null | Oldest review date | reviews.parquet | Min date |
| review_coverage_status | string | False | ineligible, no_reviews, scraped | Detailed review status description | reviews.parquet / pilot_gp | Conditional mapping |
| address | string | True | Any address string or null | Enriched address of attraction | place_metadata.parquet | Join |
| phone | string | True | Any phone string or null | Enriched contact phone number | place_metadata.parquet | Join |
| official_website | string | True | Any URL string or null | Authoritative official website (excluding google maps link) | place_metadata.parquet | Join |
| website_status | string | False | missing, google_maps_only, official_domain_present | Status classification of website metadata | place_metadata.parquet | Conditional mapping |
| operational_status | string | False | OPERATIONAL, CLOSED_TEMPORARILY, CLOSED_PERMANENTLY, unknown | Operational status of attraction | operational_status.parquet | Join |
| operational_status_confidence | float | True | 0.0 to 1.0 or null | Confidence of operational status mapping | operational_status.parquet | Join |
| description | string | True | Any string or null | Detailed textual description | place_metadata.parquet | Join |
| metadata_mapping_status | string | False | mapped, unmapped | Indicates if place mapped to Apify raw metadata | place_metadata.parquet | Conditional mapping |
| metadata_completeness_score | float | False | 0.0 to 100.0 | Completeness score of place metadata layer | place_metadata.parquet | Join |
| metadata_completeness_class | string | False | complete, strong, moderate, sparse | Classification tier of metadata completeness | place_metadata.parquet | Conditional mapping |
| has_opening_hours | boolean | False | true, false | Presence flag for opening hours data | opening_hours.parquet | Group Match |
| opening_hours_status | string | False | missing, observed, open_24_7 | General status of hours | opening_hours.parquet | Conditional mapping |
| opening_days_count | integer | False | 0 to 7 | Number of unique days with defined hours | opening_hours.parquet | Unique count of days |
| open_24_hours | boolean | False | true, false | Flag indicating if open 24 hours on all opening days | opening_hours.parquet | Boolean check |
| opening_hours_summary | string | True | Summary string or null | Summary of active days and times | opening_hours.parquet | Text summary |
| opening_hours_source_count | integer | False | >= 0 | Number of raw sources reporting opening hours | opening_hours.parquet | Group Count |
| facility_count | integer | False | >= 0 | Count of listed facilities | facilities.parquet | Group Count |
| facilities | string | False | JSON list e.g. ["parking", "toilet"] | List of facilities available | facilities.parquet | List aggregation |
| has_parking | boolean | False | true, false | Presence of parking facility | facilities.parquet | Boolean match |
| has_toilet | boolean | False | true, false | Presence of public toilet | facilities.parquet | Boolean match |
| has_food | boolean | False | true, false | Presence of food stalls, cafe, or restaurant | facilities.parquet | Boolean match |
| has_prayer_room | boolean | False | true, false | Presence of prayer room (mushola/mosque) | facilities.parquet | Boolean match |
| has_wheelchair_access | boolean | False | true, false | Presence of wheelchair accessibility features | facilities.parquet | Boolean match |
| accessibility_status | string | False | missing, observed_accessible, observed_inaccessible | Accessibility status classification | facilities.parquet | Conditional mapping |
| facility_data_status | string | False | missing, partial, complete | Indicates facility data availability | facilities.parquet | Conditional mapping |
| price_original_priority | string | True | high, medium, low, not_applicable, manual_review or null | Original priority assigned in pilot selection | pilot_price_candidates.csv | Join |
| price_validation_scope | string | False | in_scope, out_of_scope | Validation scope inclusion flag | research_price_candidates.csv / pilot_price_candidates.csv | Conditional join |
| price_validation_status | string | False | validated, pending, excluded_free, excluded_non_attraction, not_applicable, not_evaluated | Validation workflow status | research_price_candidates.csv / pilot_price_candidates.csv | Join / Map |
| price_final_decision | string | True | research, manual_review, excluded_free, excluded_non_attraction, not_applicable, null | Validation final workflow decision | research_price_candidates.csv | Join |
| price_requires_manual_review | boolean | False | true, false | Flag indicating place requires manual validation | research_price_candidates.csv | Join / Map |
| price_candidate_reason | string | True | Any string or null | Rule-derived reason for final decision | research_price_candidates.csv | Join |
| has_local_price_evidence | boolean | False | true, false | Flag indicating valid local price observations exist | price_observations.csv | Group Match |
| local_price_observation_count | integer | False | >= 0 | Total number of price observations found locally | price_observations.csv | Group Count |
| local_valid_price_observation_count | integer | False | >= 0 | Number of observations audited as valid | price_observations.csv | Group Count filtered |
| local_price_type_count | integer | False | >= 0 | Number of unique price types observed | price_observations.csv | Unique count |
| local_price_types | string | False | JSON list e.g. ["ticket", "parking"] | Types of prices observed locally | price_observations.csv | List aggregation |
| local_price_min | float | True | >= 0.0 or null | Minimum valid observed local price amount | price_observations.csv | Min amount |
| local_price_max | float | True | >= 0.0 or null | Maximum valid observed local price amount | price_observations.csv | Max amount |
| local_price_currency | string | True | IDR or null | Currency of observed local prices | price_observations.csv | Mode |
| local_price_temporal_statuses | string | False | JSON list e.g. ["current", "historical"] | Observed temporal statuses | price_observations.csv | List aggregation |
| local_price_best_confidence | float | True | 0.0 to 1.0 or null | Highest confidence score among observations | price_observations.csv | Max |
| local_price_data_status | string | False | no_evidence, historical_only, current_present | Consolidated status of local evidence | price_observations.csv | Conditional mapping |
| external_verification_status | string | False | not_verified, completed_verified, completed_no_price, completed_unresolved, pending | Verification status of external search | external_verification_coverage.csv | Join |
| external_queries_attempted | integer | False | >= 0 | Number of queries searched externally | external_verification_coverage.csv | Join |
| external_sources_checked | integer | False | >= 0 | Number of distinct sources checked | external_verification_coverage.csv | Join |
| external_accepted_sources | integer | False | >= 0 | Number of accepted external sources | external_verification_coverage.csv | Join |
| external_observation_count | integer | False | >= 0 | Total number of external observations | external_verification_coverage.csv | Join |
| external_selected_price_count | integer | False | >= 0 | Number of selected external verified prices | prices_external_verified.csv | Group Count |
| has_verified_current_price | boolean | False | true, false | Whether current verified external price exists | prices_external_verified.csv | Group Match |
| has_official_live_unbounded_price | boolean | False | true, false | Whether official unbounded live price exists | prices_external_verified.csv | Group Match |
| external_price_min | float | True | >= 0.0 or null | Minimum verified external price amount | prices_external_verified.csv | Min amount |
| external_price_max | float | True | >= 0.0 or null | Maximum verified external price amount | prices_external_verified.csv | Max amount |
| external_price_currency | string | True | IDR or null | Currency of external prices | prices_external_verified.csv | Mode |
| external_unresolved_reason | string | True | Any string or null | Reason why external search was unresolved | external_verification_coverage.csv | Join |
| external_price_data_status | string | False | not_verified, completed_no_price, completed_unresolved, verified_present | Consolidated status of external verification search | external_verification_coverage.csv | Conditional mapping |
| has_identity_data | boolean | False | true, false | True if canonical identity is complete | pilot_places.parquet | Boolean match |
| has_review_data | boolean | False | true, false | True if place has review data present | reviews.parquet | Boolean match |
| has_metadata_data | boolean | False | true, false | True if metadata mapping status is mapped | place_metadata.parquet | Boolean match |
| has_facility_data | boolean | False | true, false | True if place has facility records | facilities.parquet | Boolean match |
| has_opening_hours_data | boolean | False | true, false | True if place has opening hours records | opening_hours.parquet | Boolean match |
| has_local_price_data | boolean | False | true, false | True if place has valid local price observations | price_observations.csv | Boolean match |
| has_external_price_data | boolean | False | true, false | True if place has external verified prices | prices_external_verified.csv | Boolean match |
| enrichment_layer_count | integer | False | 0 to 7 | Number of enriched layers present | Derived | Sum of layer flags |
| overall_completeness_score | float | False | 0.0 to 100.0 | Weighted overall completeness score | Derived | Weighted sum formula |
| overall_completeness_class | string | False | complete, strong, moderate, sparse | Quality tier class of overall completeness | Derived | Score range thresholds |
| quality_warning_count | integer | False | >= 0 | Total number of quality warnings triggered | Derived | Count warnings |
| quality_warnings | string | False | JSON list of warning strings | Detailed quality warnings triggered for place | Derived | List aggregation |
| consolidation_status | string | False | consolidated, dry_run | Status of the consolidation process | Derived | Static label |
| master_version | string | False | Any string | Release version of consolidation run | Derived | Static label |
| generated_at | string | False | ISO Timestamp | Consolidation execution date | Derived | Timestamp |
