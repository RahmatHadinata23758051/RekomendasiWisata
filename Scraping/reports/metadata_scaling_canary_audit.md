# Metadata Scaling Canary Audit Report

This report documents the quality audit of the canary run outputs to verify pipeline scaling correctness before launching the full execution.

## Audit Findings
- **Canary Population Count**: 9 (Verified)
- **Output Record Count**: 9 (Verified)
- **Unique Canonical IDs**: 9 (Verified, zero duplicates)

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
| mapped | 6 |
| unmapped | 3 |


- **Operational status distribution**:
| Value | Count |
| --- | --- |
| open | 6 |
| unknown | 3 |


- **Completeness class distribution**:
| Value | Count |
| --- | --- |
| moderate | 6 |
| sparse | 3 |


## Conclusion
The canary run passes all validation criteria. The pipeline is ready to scale to the full population of 3,130 attractions.
