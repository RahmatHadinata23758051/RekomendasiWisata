# Metadata Scaling Canary Plan

This plan documents the representative canary selection for verifying the scaled metadata backfill pipeline before executing it across the entire 3,130-attraction population.

## Canary Selection
The selection consists of exactly 9 attractions:
- **3 Pilot Mapped Attractions**: Previously included in the pilot and successfully mapped to raw records.
- **3 Pilot Unmapped Attractions**: Previously included in the pilot but remained unmapped due to lack of raw records/matching evidence.
- **3 New Verified Attractions**: Brand new attractions not included in the 300-place pilot population.

### Canary Attractions Table
| Canonical ID | Name | Region | Category | Pilot Member | Existing Status | Priority | Batch ID |
| --- | --- | --- | --- | --- | --- | --- | --- |
| can_07f1c277cc43 | Sawah yuk ari | Kabupaten Lampung Barat | agrotourism | True | mapped | high | batch_001 |
| can_69d3f2d38cb6 | Kebun Raya Liwa | Kabupaten Lampung Barat | agrotourism | True | mapped | high | batch_001 |
| can_01336cdc6ae6 | Pantai Pase | Kabupaten Lampung Barat | beach | True | mapped | high | batch_001 |
| can_0eb029a1fef8 | Cagar Budaya Sipahit Lidah | Kabupaten Lampung Barat | history | True | unmapped | high | batch_001 |
| can_1084427b1bc7 | TUGU PERBATASAN | Kabupaten Lampung Barat | history | True | unmapped | high | batch_001 |
| can_267739168349 | TUGU BATAS CANGGU-PEKON BALAK | Kabupaten Lampung Barat | history | True | unmapped | high | batch_001 |
| can_1067b71513e9 | Sawah lek sukirin | Kabupaten Lampung Barat | agrotourism | False | not_evaluated | high | batch_001 |
| can_185ae4342ce4 | Wisata Talang Sawah | Kabupaten Lampung Barat | agrotourism | False | not_evaluated | high | batch_001 |
| can_2095102c27cb | Kebun alpukat ryo | Kabupaten Lampung Barat | agrotourism | False | not_evaluated | high | batch_001 |
