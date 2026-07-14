# Duplicate and Join Explosion Final Audit Report

### Stage-by-Stage Join Counts

| Stage Name | Input Rows | Output Rows | Unique IDs | Duplicate IDs | Row Multiplier | Audit Status |
| --- | --- | --- | --- | --- | --- | --- |
| pilot_base | 300 | 300 | 300 | 0 | 1.0 | passed |
| join_canonical_details | 300 | 300 | 300 | 0 | 1.0 | passed |
| join_source_flags | 300 | 300 | 300 | 0 | 1.0 | passed |
| join_review_summary | 300 | 300 | 300 | 0 | 1.0 | passed |
| join_metadata_fields | 300 | 300 | 300 | 0 | 1.0 | passed |
| join_opening_hours | 300 | 300 | 300 | 0 | 1.0 | passed |
| join_facilities | 300 | 300 | 300 | 0 | 1.0 | passed |
| join_local_price_summary | 300 | 300 | 300 | 0 | 1.0 | passed |
| join_external_price_summary | 300 | 300 | 300 | 0 | 1.0 | passed |
| final_enrichment_master | 300 | 300 | 300 | 0 | 1.0 | passed |

### Validation Findings
- **Every flat-master join stage remains at exactly 300 rows**: Checked and validated. All stages pass.
- **Final duplicate canonical IDs**: 0. No duplicate canonical IDs exist in the final master dataset.
- **Row multiplier**: 1.0 at every join stage. No join explosion occurred.
- **One-to-many sources aggregated**: Verified. Review, opening hours, facilities, and price observation records were correctly grouped and aggregated before performing joins.
