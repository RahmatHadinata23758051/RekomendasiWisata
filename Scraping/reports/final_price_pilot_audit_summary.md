# Price Research Pilot Audit Summary Report

Generated at: 2026-07-15 03:29:37 UTC
Audit Version: test_price_audit_v1

## 1. Executive Summary
- **Input Places**: 11
- **Original Observations**: 32
- **Valid Observations**: 29
- **Rejected False Positives**: 3
- **Destinations with Observations**: 8
- **Destinations without Observations**: 3
- **Provisional Final Prices**: 0
- **Verified Current Prices**: 0
- **Historical References**: 29
- **Unresolved Prices**: 0
- **Rejected Prices**: 3
- **External Verification Queue Count**: 11

## 2. Source Origin Distribution
| Source Origin | Count |
| --- | --- |
| local_review | 32 |

## 3. Temporal Status Distribution
| Verification Status | Count |
| --- | --- |
| historical | 29 |
| unknown_date | 3 |

## 4. Final Place Decision & Research Status
| canonical_id | name | research_status | observations_found | selected_prices | research_confidence |
| --- | --- | --- | --- | --- | --- |
| can_1fef284e7d10 | Dermaga Pulau Pahawang | completed_with_price | 2 | 2 | 0.9 |
| can_151f3bbf542d | Pantai Mutun | completed_with_price | 6 | 6 | 0.9 |
| can_cada872752b2 | Pantai Sari Ringgung | completed_with_price | 5 | 5 | 0.9 |
| can_1f6b9f3c2ceb | Camping Area Sonokeling 1 | completed_no_current_price | 0 | 0 | 0.0 |
| can_a0d4ca18f1f7 | Kolam renang | completed_no_current_price | 0 | 0 | 0.0 |
| can_17b24ba62485 | Water Park Citra Garden | completed_with_price | 3 | 3 | 0.9 |
| can_2850f83ad341 | Kolam Renang Perahu Layar | completed_with_price | 1 | 1 | 0.9 |
| can_58c471e76647 | Slanik Waterpark Lampung | completed_with_price | 5 | 5 | 0.9 |
| can_1a46f7a6372c | Taman Nasional Way Kambas | completed_with_price | 8 | 5 | 0.9 |
| can_b4a866f13078 | Camping island | completed_no_current_price | 0 | 0 | 0.0 |
| can_5dd47abc65d1 | Kolam Renang Tirta Garden | completed_with_price | 2 | 2 | 0.9 |

## 5. False Positives Audit Details
| price_observation_id | canonical_id | raw_price_text | parsed_amount | context_before | context_after | is_valid_price_context | false_positive_type | audit_decision | audit_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| obs_0046 | can_1a46f7a6372c | rating gajah 4.5 | 4.5 |  |  | False | rating | reject | Rating score number mistakenly parsed as price. |
| obs_0048 | can_1a46f7a6372c | tahun 2026 | 2026.0 |  |  | False | year | reject | Year number mistakenly parsed as price. |
| obs_0049 | can_1a46f7a6372c | Info kontak kak 081277778888 | 81277778888.0 |  |  | False | phone_number | reject | Phone number mistakenly parsed as price. |

## 6. Audit Decision Summary
All local review and description source evidence has been audited. Since all evidence is from local reviews/descriptions, none are classified as `verified_current` or `verified_current_price`. They are correctly categorized as `provisional_recent` or `historical_reference` with custom confidence scores to prevent false verified claims. The dataset is ready for freeze with a clear path forward documented in the external verification queue.
