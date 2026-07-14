# Price Research Input Audit Report

## 1. Audit Summary
- **Audit Date**: 2026-07-14
- **Input File**: `data/enrichment/price/validation/research_price_candidates.csv`
- **Total Records Checked**: 11
- **Status**: PASSED

## 2. Parameter Audits
1. **Total Records Count**: Tepat 11 records. (PASSED)
2. **Canonical ID Uniqueness**: 11 unique `canonical_id` values. (PASSED)
3. **Original Priority Bounds**: All records have original priority as either `high` (3 records) or `medium` (8 records). None are low or not_applicable. (PASSED)
4. **Scope Status**: All records have `validation_scope_status` = `in_scope`. (PASSED)
5. **Validation Status**: All records have `validation_status` = `validated`. (PASSED)
6. **Decision Match**: All records have `final_decision` = `research`. (PASSED)
7. **Operational Status**: None are `permanently_closed`. All are `open` or `OPERATIONAL`. (PASSED)
8. **Query Templates Availability**: All records have valid generated values for:
   - `entry_ticket_query`
   - `parking_query`
   - `activity_query`
   - `official_source_query`
   - `social_media_query`
   - `government_source_query`
   (PASSED)
9. **Decision Provenance Check**: Decision provenance exists for all in-scope records in the decision provenance registry. (PASSED)

## 3. Audited Candidate List
| Canonical ID | Name | Category | Priority | Operational Status | Paid Score | Decision Rule |
| --- | --- | --- | --- | --- | --- | --- |
| `can_1fef284e7d10` | Dermaga Pulau Pahawang | island | medium | open | 3 | strong_paid_evidence |
| `can_151f3bbf542d` | Pantai Mutun | beach | medium | open | 3 | strong_paid_evidence |
| `can_cada872752b2` | Pantai Sari Ringgung | beach | medium | open | 3 | strong_paid_evidence |
| `can_1f6b9f3c2ceb` | Camping Area Sonokeling 1 | camping | high | open | 6 | strong_paid_evidence |
| `can_a0d4ca18f1f7` | Kolam renang | waterpark | high | open | 6 | strong_paid_evidence |
| `can_17b24ba62485` | Water Park Citra Garden | waterpark | high | open | 7 | strong_paid_evidence |
| `can_2850f83ad341` | Kolam Renang Perahu Layar | waterpark | medium | open | 6 | strong_paid_evidence |
| `can_58c471e76647` | Slanik Waterpark Lampung | waterpark | medium | open | 9 | strong_paid_evidence |
| `can_1a46f7a6372c` | Taman Nasional Way Kambas | park | medium | open | 3 | strong_paid_evidence |
| `can_b4a866f13078` | Camping island | island | medium | open | 6 | strong_paid_evidence |
| `can_5dd47abc65d1` | Kolam Renang Tirta Garden | waterpark | medium | open | 6 | strong_paid_evidence |
