# Metadata Scaling Canary Audit Report

This report documents the quality audit of the canary run outputs to verify pipeline scaling correctness before launching the full execution.

## Audit Findings
- **Canary Population Count**: 30 (Verified)
- **Output Record Count**: 30 (Verified)
- **Unique Canonical IDs**: 30 (Verified, zero duplicates)

### Column Integrity Check
All required metadata schema columns are fully populated with appropriate data types and zero drift:
- `canonical_id`
- `mapping_status`
- `address`
- `address_status`
- `phone`
- `phone_status`
- `official_website`
- `website_status`
- `operational_status`
- `operational_status_status`
- `opening_hours_status`
- `facility_data_status`
- `accessibility_status`
- `metadata_completeness_score`
- `metadata_completeness_class`

### Distribution Analysis
- **Mapping status distribution**:
| Value | Count |
| --- | --- |
| mapped | 28 |
| unmapped | 2 |


- **Operational status distribution**:
| Value | Count |
| --- | --- |
| open | 23 |
| temporarily_closed | 3 |
| unknown | 2 |
| permanently_closed | 2 |


- **Completeness class distribution**:
| Value | Count |
| --- | --- |
| moderate | 20 |
| strong | 7 |
| sparse | 2 |
| complete | 1 |


## Conclusion
The canary run passes all validation criteria. The pipeline is ready to scale to the full population of 3,130 attractions.
