# External Price Verification Summary Report

Generated at: 2026-07-15 03:54:09 UTC
Verification Version: external_price_verification_pilot_v1

## 1. Executive Summary
- **Total Input Places**: 11
- **Completed Count**: 11
- **Verified Current Places**: 0
- **Official Live Unbounded Places**: 0
- **Provisional Places**: 1
- **Unresolved Places**: 10
- **Total Queries Attempted**: 242
- **Total Sources Checked**: 1
- **Total External Observations**: 3
- **Selected External Prices**: 3

## 2. Place Verification Status Detail
| canonical_id | name | region | verification_status | external_observations |
| --- | --- | --- | --- | --- |
| can_1fef284e7d10 | Dermaga Pulau Pahawang | Kabupaten Pesawaran | completed_no_price | 0 |
| can_151f3bbf542d | Pantai Mutun | Kabupaten Lampung Selatan | completed_provisional | 3 |
| can_cada872752b2 | Pantai Sari Ringgung | Kabupaten Pesawaran | completed_no_price | 0 |
| can_1f6b9f3c2ceb | Camping Area Sonokeling 1 | Kabupaten Tanggamus | completed_no_price | 0 |
| can_a0d4ca18f1f7 | Kolam renang | Kabupaten Tanggamus | completed_no_price | 0 |
| can_17b24ba62485 | Water Park Citra Garden | Kota Bandar Lampung | completed_no_price | 0 |
| can_2850f83ad341 | Kolam Renang Perahu Layar | Kabupaten Lampung Selatan | completed_no_price | 0 |
| can_58c471e76647 | Slanik Waterpark Lampung | Kabupaten Lampung Selatan | completed_no_price | 0 |
| can_1a46f7a6372c | Taman Nasional Way Kambas | Kabupaten Lampung Timur | completed_no_price | 0 |
| can_b4a866f13078 | Camping island | Kabupaten Pringsewu | completed_unresolved | 0 |
| can_5dd47abc65d1 | Kolam Renang Tirta Garden | Kabupaten Tulang Bawang | completed_no_price | 0 |

## 3. Local vs External Price Comparison
| canonical_id | price_type | local_value | external_value | comparison_status |
| --- | --- | --- | --- | --- |
| can_151f3bbf542d | entry_ticket | 35000.0 | 35000.0 | match |
| can_151f3bbf542d | parking | 10000.0 | 5000.0 | historical_difference |
| can_151f3bbf542d | parking | 10000.0 | 10000.0 | match |

## 4. Conflict Audit
No external price conflicts identified.

## 5. False Positive Audit Details
| canonical_id | name | raw_price_text | parsed_amount | false_positive_type | audit_reason | verification_version |
| --- | --- | --- | --- | --- | --- | --- |
| can_151f3bbf542d | Pantai Mutun | Found number 2026 in text: 'Harga tiket masuk Pantai Mutun terbaru 2026 adalah Rp35.000. Parkir motor Rp5.000. parkir mobil Rp10.000.' | 2026.0 | year | Detected number pattern as year. | external_price_verification_pilot_v1 |

## 6. Final Decision & Recommendation
All 11 candidates processed successfully. The pipeline is complete, resume-safe, and ready for consolidation.
