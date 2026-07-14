# Mock External Data Audit Report

## Overview
An audit of the previous price verification run has revealed that all processed records were derived from mock search results. This report documents these records, their status, and the corrective actions taken.

## Summary Metrics
- **Total Audited Records**: 53
- **Source Registry Records**: 11
- **Price Observations**: 22
- **Selected External Prices**: 20

## Action Required
1. Move mock search results and expected datasets into `tests/fixtures/external_price/`.
2. Mark all mock-derived records as simulated/not_verified.
3. Remove all mock-derived verified prices from production datasets.
4. Perform real public-source verification for the 11 candidate attractions.

## Audited Records Detail

| Record Type | Record ID | Canonical ID | Source ID | Source URL | Previous Status | Corrected Status | Action Required |
| --- | --- | --- | --- | --- | --- | --- | --- |
| source_registry | src_ext_0001 | can_1fef284e7d10 | src_ext_0001 | https://www.pahawangtour.com | verified | simulated_not_verified | reverify_with_real_public_source |
| source_registry | src_ext_0002 | can_151f3bbf542d | src_ext_0002 | https://www.pantaimutun.com | verified | simulated_not_verified | reverify_with_real_public_source |
| source_registry | src_ext_0003 | can_cada872752b2 | src_ext_0003 | https://www.facebook.com/pantaisariringgungofficial | verified | simulated_not_verified | reverify_with_real_public_source |
| source_registry | src_ext_0004 | can_1f6b9f3c2ceb | src_ext_0004 | https://www.travelerlampung.com/camping-sonokeling | probable | simulated_not_verified | reverify_with_real_public_source |
| source_registry | src_ext_0005 | can_a0d4ca18f1f7 | src_ext_0005 | https://tanggamuskab.go.id/wisata-kolam-renang-tanggamus | verified | simulated_not_verified | reverify_with_real_public_source |
| source_registry | src_ext_0006 | can_17b24ba62485 | src_ext_0006 | https://citragardenwaterpark.co.id | verified | simulated_not_verified | reverify_with_real_public_source |
| source_registry | src_ext_0007 | can_2850f83ad341 | src_ext_0007 | https://www.instagram.com/kolamperahulayar | verified | simulated_not_verified | reverify_with_real_public_source |
| source_registry | src_ext_0008 | can_58c471e76647 | src_ext_0008 | https://www.slanikwaterpark.co.id | verified | simulated_not_verified | reverify_with_real_public_source |
| source_registry | src_ext_0009 | can_1a46f7a6372c | src_ext_0009 | https://www.lampungtimurkab.go.id/wisata-way-kambas | verified | simulated_not_verified | reverify_with_real_public_source |
| source_registry | src_ext_0010 | can_b4a866f13078 | src_ext_0010 | https://www.campingislandpringsewu.com | verified | simulated_not_verified | reverify_with_real_public_source |
| source_registry | src_ext_0011 | can_5dd47abc65d1 | src_ext_0011 | https://www.pantauwisata.com/tirta-garden | probable | simulated_not_verified | reverify_with_real_public_source |
| external_observation | obs_ext_0001 | can_1fef284e7d10 | src_ext_0001 | https://www.pahawangtour.com | official_live_unbounded | simulated_only | reverify_with_real_public_source |
| external_observation | obs_ext_0002 | can_1fef284e7d10 | src_ext_0001 | https://www.pahawangtour.com | official_live_unbounded | simulated_only | reverify_with_real_public_source |
| external_observation | obs_ext_0003 | can_151f3bbf542d | src_ext_0002 | https://www.pantaimutun.com | verified_current | simulated_only | reverify_with_real_public_source |
| external_observation | obs_ext_0004 | can_151f3bbf542d | src_ext_0002 | https://www.pantaimutun.com | verified_current | simulated_only | reverify_with_real_public_source |
| external_observation | obs_ext_0005 | can_151f3bbf542d | src_ext_0002 | https://www.pantaimutun.com | verified_current | simulated_only | reverify_with_real_public_source |
| external_observation | obs_ext_0006 | can_cada872752b2 | src_ext_0003 | https://www.facebook.com/pantaisariringgungofficial | official_live_unbounded | simulated_only | reverify_with_real_public_source |
| external_observation | obs_ext_0007 | can_cada872752b2 | src_ext_0003 | https://www.facebook.com/pantaisariringgungofficial | official_live_unbounded | simulated_only | reverify_with_real_public_source |
| external_observation | obs_ext_0008 | can_cada872752b2 | src_ext_0003 | https://www.facebook.com/pantaisariringgungofficial | official_live_unbounded | simulated_only | reverify_with_real_public_source |
| external_observation | obs_ext_0009 | can_1f6b9f3c2ceb | src_ext_0004 | https://www.travelerlampung.com/camping-sonokeling | recent_external_unverified | simulated_only | reverify_with_real_public_source |
| external_observation | obs_ext_0010 | can_a0d4ca18f1f7 | src_ext_0005 | https://tanggamuskab.go.id/wisata-kolam-renang-tanggamus | recent_external_unverified | simulated_only | reverify_with_real_public_source |
| external_observation | obs_ext_0011 | can_17b24ba62485 | src_ext_0006 | https://citragardenwaterpark.co.id | official_live_unbounded | simulated_only | reverify_with_real_public_source |
| external_observation | obs_ext_0012 | can_17b24ba62485 | src_ext_0006 | https://citragardenwaterpark.co.id | official_live_unbounded | simulated_only | reverify_with_real_public_source |
| external_observation | obs_ext_0013 | can_2850f83ad341 | src_ext_0007 | https://www.instagram.com/kolamperahulayar | official_live_unbounded | simulated_only | reverify_with_real_public_source |
| external_observation | obs_ext_0014 | can_58c471e76647 | src_ext_0008 | https://www.slanikwaterpark.co.id | official_live_unbounded | simulated_only | reverify_with_real_public_source |
| external_observation | obs_ext_0015 | can_58c471e76647 | src_ext_0008 | https://www.slanikwaterpark.co.id | official_live_unbounded | simulated_only | reverify_with_real_public_source |
| external_observation | obs_ext_0016 | can_58c471e76647 | src_ext_0008 | https://www.slanikwaterpark.co.id | official_live_unbounded | simulated_only | reverify_with_real_public_source |
| external_observation | obs_ext_0017 | can_58c471e76647 | src_ext_0008 | https://www.slanikwaterpark.co.id | official_live_unbounded | simulated_only | reverify_with_real_public_source |
| external_observation | obs_ext_0018 | can_1a46f7a6372c | src_ext_0009 | https://www.lampungtimurkab.go.id/wisata-way-kambas | recent_external_unverified | simulated_only | reverify_with_real_public_source |
| external_observation | obs_ext_0019 | can_1a46f7a6372c | src_ext_0009 | https://www.lampungtimurkab.go.id/wisata-way-kambas | recent_external_unverified | simulated_only | reverify_with_real_public_source |
| external_observation | obs_ext_0020 | can_1a46f7a6372c | src_ext_0009 | https://www.lampungtimurkab.go.id/wisata-way-kambas | recent_external_unverified | simulated_only | reverify_with_real_public_source |
| external_observation | obs_ext_0021 | can_1a46f7a6372c | src_ext_0009 | https://www.lampungtimurkab.go.id/wisata-way-kambas | recent_external_unverified | simulated_only | reverify_with_real_public_source |
| external_observation | obs_ext_0022 | can_5dd47abc65d1 | src_ext_0011 | https://www.pantauwisata.com/tirta-garden | recent_external_unverified | simulated_only | reverify_with_real_public_source |
| selected_external_price | vpr_0001 | can_1fef284e7d10 | src_ext_0001 | https://www.pahawangtour.com | official_live_unbounded | simulated_only | remove_from_production_outputs |
| selected_external_price | vpr_0002 | can_1fef284e7d10 | src_ext_0001 | https://www.pahawangtour.com | official_live_unbounded | simulated_only | remove_from_production_outputs |
| selected_external_price | vpr_0003 | can_151f3bbf542d | src_ext_0002 | https://www.pantaimutun.com | verified_current | simulated_only | remove_from_production_outputs |
| selected_external_price | vpr_0004 | can_151f3bbf542d | src_ext_0002 | https://www.pantaimutun.com | verified_current | simulated_only | remove_from_production_outputs |
| selected_external_price | vpr_0005 | can_151f3bbf542d | src_ext_0002 | https://www.pantaimutun.com | verified_current | simulated_only | remove_from_production_outputs |
| selected_external_price | vpr_0006 | can_cada872752b2 | src_ext_0003 | https://www.facebook.com/pantaisariringgungofficial | official_live_unbounded | simulated_only | remove_from_production_outputs |
| selected_external_price | vpr_0007 | can_cada872752b2 | src_ext_0003 | https://www.facebook.com/pantaisariringgungofficial | official_live_unbounded | simulated_only | remove_from_production_outputs |
| selected_external_price | vpr_0008 | can_cada872752b2 | src_ext_0003 | https://www.facebook.com/pantaisariringgungofficial | official_live_unbounded | simulated_only | remove_from_production_outputs |
| selected_external_price | vpr_0009 | can_a0d4ca18f1f7 | src_ext_0005 | https://tanggamuskab.go.id/wisata-kolam-renang-tanggamus | externally_supported_recent | simulated_only | remove_from_production_outputs |
| selected_external_price | vpr_0010 | can_17b24ba62485 | src_ext_0006 | https://citragardenwaterpark.co.id | official_live_unbounded | simulated_only | remove_from_production_outputs |
| selected_external_price | vpr_0011 | can_17b24ba62485 | src_ext_0006 | https://citragardenwaterpark.co.id | official_live_unbounded | simulated_only | remove_from_production_outputs |
| selected_external_price | vpr_0012 | can_2850f83ad341 | src_ext_0007 | https://www.instagram.com/kolamperahulayar | official_live_unbounded | simulated_only | remove_from_production_outputs |
| selected_external_price | vpr_0013 | can_58c471e76647 | src_ext_0008 | https://www.slanikwaterpark.co.id | official_live_unbounded | simulated_only | remove_from_production_outputs |
| selected_external_price | vpr_0014 | can_58c471e76647 | src_ext_0008 | https://www.slanikwaterpark.co.id | official_live_unbounded | simulated_only | remove_from_production_outputs |
| selected_external_price | vpr_0015 | can_58c471e76647 | src_ext_0008 | https://www.slanikwaterpark.co.id | official_live_unbounded | simulated_only | remove_from_production_outputs |
| selected_external_price | vpr_0016 | can_58c471e76647 | src_ext_0008 | https://www.slanikwaterpark.co.id | official_live_unbounded | simulated_only | remove_from_production_outputs |
| selected_external_price | vpr_0017 | can_1a46f7a6372c | src_ext_0009 | https://www.lampungtimurkab.go.id/wisata-way-kambas | externally_supported_recent | simulated_only | remove_from_production_outputs |
| selected_external_price | vpr_0018 | can_1a46f7a6372c | src_ext_0009 | https://www.lampungtimurkab.go.id/wisata-way-kambas | externally_supported_recent | simulated_only | remove_from_production_outputs |
| selected_external_price | vpr_0019 | can_1a46f7a6372c | src_ext_0009 | https://www.lampungtimurkab.go.id/wisata-way-kambas | externally_supported_recent | simulated_only | remove_from_production_outputs |
| selected_external_price | vpr_0020 | can_1a46f7a6372c | src_ext_0009 | https://www.lampungtimurkab.go.id/wisata-way-kambas | externally_supported_recent | simulated_only | remove_from_production_outputs |
