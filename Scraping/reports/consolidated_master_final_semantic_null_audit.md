# Semantic Null Final Audit Report

### Semantic Null Validation

| Field Name | Non-Null Count | Null Count | Unknown Count | Missing Count | Not Applicable Count | False Count | Zero Count | Semantic Issue Count | Audit Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| name | 300 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Looks clean. |
| primary_category | 300 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Looks clean. |
| latitude | 300 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Looks clean. |
| longitude | 300 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Looks clean. |
| official_website | 300 | 0 | 0 | 292 | 0 | 0 | 0 | 0 | Looks clean. |
| website_status | 300 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Looks clean. |
| operational_status | 300 | 0 | 29 | 0 | 0 | 0 | 0 | 0 | Looks clean. |
| facilities | 300 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Looks clean. |
| has_opening_hours | 300 | 0 | 0 | 0 | 0 | 201 | 402 | 0 | Looks clean. |
| price_validation_scope | 300 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Looks clean. |
| price_final_decision | 167 | 133 | 133 | 133 | 134 | 0 | 0 | 0 | Looks clean. |
| has_local_price_evidence | 300 | 0 | 0 | 0 | 0 | 292 | 584 | 0 | Looks clean. |
| local_price_min | 8 | 292 | 292 | 292 | 292 | 0 | 0 | 0 | Looks clean. |
| local_price_max | 8 | 292 | 292 | 292 | 292 | 0 | 0 | 0 | Looks clean. |
| external_verification_status | 300 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Looks clean. |
| external_selected_price_count | 300 | 0 | 0 | 0 | 0 | 300 | 600 | 0 | Looks clean. |
| external_price_min | 0 | 300 | 300 | 300 | 300 | 0 | 0 | 0 | Looks clean. |
| external_price_max | 0 | 300 | 300 | 300 | 300 | 0 | 0 | 0 | Looks clean. |

### Specific Verifications
- **official_website**: Missing website remains null; no values were defaulted.
- **Google Maps URL**: Is not counted as official website. Maps URL values are mapped strictly to `google_maps_url` / metadata Layer, and official website field has `website_status` mapped to `google_maps_only` where appropriate.
- **facilities**: Missing facility is not false (represented as empty JSON `[]`).
- **opening_hours**: Missing opening hours is not closed (represented as has_opening_hours=False and status='missing').
- **completed_no_price / completed_unresolved**: Does not produce amount = 0; min/max amounts remain correctly null.
- **selected external price count = 0**: Produces null external min/max.
- **is_free or equivalent**: No place is marked free without explicit evidence.
