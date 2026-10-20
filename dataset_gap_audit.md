# Current Dataset Gap Audit

**Scope.** This audit covers the current consolidated/recommender population (3,130 places), the metadata/review/price manifests and coverage reports, the Apify Google Maps importer and enrichment tests, and the earlier raw-collection reports. Counts below distinguish the **full master** from the **300-place pilot** where the repository contains both scopes. No code was changed.

## Executive summary

- The full master is structurally complete for identity: **3,130 rows and 3,130 unique canonical IDs**. All 15 Lampung regencies/cities are represented; there is no current zero-place region gap. The principal regional issue is uneven completeness, not discovery coverage.
- Reviews are the largest usable content gap: only **172/3,130 places (5.50%)** have review data, leaving **2,958 (94.50%)** without it. Apify can collect Google reviews for places with a resolvable Google Place ID, but cannot manufacture coverage where Google has no reviews or review text.
- Opening hours are present for **1,141/3,130 (36.45%)**; **1,989 (63.55%)** are missing. Google Maps/Apify is the most direct backfill path, but schedules are time-sensitive and absent data must not be interpreted as closed.
- Pricing is effectively unfilled: only **8 places (0.26%)** have local price evidence, all historical-only; **0 verified current external prices** exist. Apify may provide a Google price tier or a displayed price when a place exposes one, but reliable admission/ride/package prices require official operator sources or targeted manual/web research and temporal verification.
- Category long-tail quality is weak: `other` is **1,012/3,130 (32.33%)**, while culture (4), religious (12), river (14), education (11), and lake (29) are small. Apify's broad keyword search can discover candidates and category signals, but source-specific taxonomy review is required before changing canonical categories.

## 0. Lane A applied — Google rating backfill (2026-10-20)

The gaps above still hold for **review text, opening hours, price, and taxonomy**. The rating/review-count gap has since been partially closed **without spending Apify credits**, because the raw Apify export already contained `totalScore` and `reviewsCount`.

| Metric | Before | After |
|---|---:|---:|
| Places with a rating signal (`review_rating_mean` or `google_rating`) | 172 (5.50%) | **2,245 (71.73%)** |
| `rating_normalized` non-null in recommender features | 172 | **2,245** |
| `rating_weighted_normalized` non-null (ranking-safe) | 0 | **2,245** |
| Frontend catalog rows | 2,889 | **3,130** |
| Catalog rows with `reviews_count > 0` | 161 | **2,245** |

How it was done:

- **No master rebuild.** The canonical snapshot recorded in `consolidated_master_manifest_full.json` (sha256 `d9dd95…`) no longer exists, and the current `attractions_master_verified.parquet` has **zero `canonical_id` overlap** with the frozen master. A rebuild would mint new IDs and break the frontend, ML API, and RAG index.
- **Additive patch.** `Scraping/src/enrichment/google_rating_backfill.py` adds `google_rating`, `google_review_count`, `google_rating_weighted`, `google_place_id`, `google_rating_observed_at`, `google_rating_match_distance_m`. It never overwrites `review_rating_mean`.
- **Matching rule.** Exact normalized name + haversine distance ≤ 300 m. Result: 2,245 accepted, **24 rejected by distance**, 861 with no name match, 51 ambiguous names resolved to the nearest candidate. Median accepted distance was 0 m.
- **Small-sample bias → Bayesian smoothing.** The raw Google rating is kept for display, but ranking uses `google_rating_weighted = (v·R + m·C) / (v + m)` with prior weight `m = 20` and prior mean `C = 4.4924` (the observed mean of the 2,245 matched ratings). With a median of only 8 reviews per place, 703 places had a raw 5.0 and 754 were ≥4.8 with fewer than 10 reviews; unsmoothed, a single 5.0 could outrank a 4.8 with 5,000+ reviews. The weighted value fixes that ordering without erasing the raw value.
- **Provenance.** The patch is recorded under `enrichment_patches` in the consolidated manifest; `master_version` is now `consolidated_enrichment_full_v1+google_rating_backfill.1`. The report stores `rating_prior_weight` and `rating_prior_mean` so the transform is reproducible.
- **Feature version.** `recommender_ready_features` is now **v1.3** with `rating_weighted_normalized` plus a `rating_source` column (`scraped_reviews` 172, `google_maps` 2,073, `missing` 885). `rating_normalized` remains the raw signal; ranking consumers should use the weighted column.
- **Frontend.** `Website/scratch/sync_public_catalog.py` added the 241 missing destinations, replaced the shared `4.6` placeholder rating for 1,785 rows where real Google data exists, and wrote `rating_weighted` for all 3,130 rows. 1,031 rows still have no rating source and keep the placeholder for both fields.
- **Consumers.** The ML API exposes `rating` (raw display) and `rating_weighted` (ranking); `sort_by=rating`, `popular`, and planner relevance use `rating_weighted`. The Explore page sorts on `ratingWeighted`. The chatbot RAG keeps raw `rating` in its facts but scores with `ratingWeighted`, so the boost now spans roughly 7.1–9.8 instead of a flat 9.2 from the old placeholder.
- **Unaffected.** The main `/api/v1/recommendations` model never used rating, so its input vectors and top-10 results are byte-for-byte identical before/after.

Residual rating gap: **885 places (28.27%)** still have no rating signal — mostly places with no matching raw Google record. These need a fresh targeted Apify run by place ID or name, not a pipeline change.


## 1. Population and regional coverage

### Full master distribution

| Region | Places | Share |
|---|---:|---:|
| Kota Bandar Lampung | 473 | 15.11% |
| Kabupaten Lampung Selatan | 396 | 12.65% |
| Kabupaten Tanggamus | 337 | 10.77% |
| Kabupaten Pesawaran | 280 | 8.95% |
| Kabupaten Lampung Barat | 248 | 7.92% |
| Kabupaten Lampung Tengah | 214 | 6.84% |
| Kabupaten Lampung Timur | 206 | 6.58% |
| Kabupaten Pringsewu | 170 | 5.43% |
| Kabupaten Lampung Utara | 168 | 5.37% |
| Kabupaten Way Kanan | 160 | 5.11% |
| Kabupaten Tulang Bawang | 125 | 3.99% |
| Kabupaten Tulang Bawang Barat | 107 | 3.42% |
| Kabupaten Pesisir Barat | 91 | 2.91% |
| Kota Metro | 89 | 2.84% |
| Kabupaten Mesuji | 66 | 2.11% |

All 15 regions have records. The old July raw coverage report had 659 canonical attractions, was heavily concentrated in Bandar Lampung (512/659), and explicitly showed **Kabupaten Lampung Timur as uncovered**. The scaled/final master subsequently contains 206 Lampung Timur records, so that historical gap is closed; it should not be reported as a current gap.

### Regional completeness and metadata gaps

Metadata mapping is **2,992/3,130 (95.59%)**, leaving **138 unmapped (4.41%)**. The regional scaling report provides a more useful targeting signal than raw row count:

- Lowest mapping rates: Lampung Barat **87.90%** (30 unmapped), Lampung Selatan **91.16%** (35), Lampung Tengah **92.52%** (16), Metro **93.26%** (6), Tulang Bawang **93.60%** (8).
- Highest mapping rates: Lampung Timur **100%**, Pesawaran **99.64%**, Pringsewu **99.41%**, Tulang Bawang Barat **99.07%**.
- Opening-hours coverage by region ranges from **26.17% Lampung Tengah** and **27.82% Lampung Barat** to **43.60% Lampung Timur** and **43.70% Pesawaran**. This is a broad, statewide gap rather than a single missing district.
- Phone coverage is only roughly **13.64%–33.57%** by region and website coverage is roughly **0%–4.29%** in the scaling report. These fields are secondary to the requested gaps but indicate that metadata is not uniformly rich even where an attraction is mapped.
- Facilities coverage ranges from **65.12% Bandar Lampung** to **91.59% Tulang Bawang Barat**, so facilities should not be treated as complete merely because identity mapping is complete.

**Regional recommendation:** prioritize the lowest-mapped and lowest-hours regions (Lampung Barat, Lampung Selatan, Lampung Tengah, Metro), then use regional quotas so the next collection does not revert to the old Bandar Lampung bias. For the 300-place pilot, tests explicitly require all 15 regions and cap Bandar Lampung at 45 places (15%), which is a sound sampling guardrail.

## 2. Category coverage and category gaps

Canonical primary-category distribution:

| Category | Places | Share | Assessment |
|---|---:|---:|---|
| other | 1,012 | 32.33% | Main taxonomy/labeling gap; investigate before collection expansion |
| park | 441 | 14.09% | Strong volume; likely keyword/search duplication pressure |
| beach | 339 | 10.83% | Adequate volume |
| agrotourism | 180 | 5.75% | Moderate |
| hill | 167 | 5.34% | Moderate |
| recreation | 167 | 5.34% | Moderate |
| waterfall | 207 | 6.61% | Moderate/strong |
| mountain | 120 | 3.83% | Moderate |
| island | 70 | 2.24% | Moderate |
| waterpark | 72 | 2.30% | Moderate |
| history | 63 | 2.01% | Thin but usable |
| family | 62 | 1.98% | Thin |
| camping | 45 | 1.44% | Thin |
| museum | 42 | 1.34% | Thin |
| nature | 41 | 1.31% | Thin |
| lake | 29 | 0.93% | Long tail |
| river | 14 | 0.45% | Long tail |
| education | 11 | 0.35% | Long tail |
| religious | 12 | 0.38% | Long tail |
| culture | 4 | 0.13% | Critical long-tail sparsity |

The older 659-record raw report had a different, pre-consolidation category profile, so its frequencies must not be compared as if they were current counts. The current issue is not simply “missing categories”: it is the combination of a very large `other` bucket and tiny categories that can create poor recommendation coverage.

**What Apify can do:** run focused Indonesian searches (`museum`, `wisata budaya`, `wisata religi`, `wisata edukasi`, `danau`, `sungai`, `desa wisata`, etc.) and use `categoryName`/`categories` plus search keyword as discovery signals. Existing audit data shows high yield for `pantai` (100%), `taman wisata` (94%), `wisata edukasi` (85.71%), and `wisata budaya` only 25%; `wisata religi` is particularly noisy (3.33%). The importer tests deliberately classify ambiguous/no-category records as `manual_review`, and generic “Taman” records need extra signals. Therefore Apify is useful for candidate discovery, not authoritative category assignment.

**Other source required:** official tourism registries (Dinas Pariwisata/Jadesta) and manual review are needed for culturally/administratively ambiguous sites, especially the four culture records and the religious/education/river long tail.

## 3. Reviews gap

| Scope | Places with reviews | Places without reviews | Coverage |
|---|---:|---:|---:|
| Full master | 172 | 2,958 | 5.50% |
| Review pilot input | 271 eligible for scraping | 29 ineligible | 90.33% eligible |
| Pilot total | 300 | — | — |

The final review layer has 924 rows for 172 canonical IDs (the remaining rows are multiple reviews per place); the source inventory reports 752 duplicate review IDs/rows at the source-layer level. Review coverage is therefore a place-level problem, not just a row-count problem.

The enrichment tests show the intended Apify contract:

- payloads are generated in positive, negative, and neutral modes for **271 eligible places**, four batches, 12 payloads; batch sizes are capped at 70;
- batches request Google reviews in Indonesian and preserve per-place uniqueness per mode;
- places can end as `no_google_reviews`, `reviews_without_text`, `partial_bucket_coverage`, `complete_bucket_coverage`, or `failed_scrape`;
- 29 pilot places are explicitly ineligible and must remain `ineligible`, not be misreported as pending;
- blank text is excluded from representative reviews; duplicates are tracked rather than silently treated as new evidence.

**Apify-fillable:** Google review text, stars, dates, and review counts for resolvable Google Place IDs; re-scraping can refresh stale review evidence. **Not fillable by Apify alone:** places with no Google reviews, reviews with no text, places lacking a resolvable Google ID, or reviews from non-Google platforms. Those require another platform/source or a truthful “no evidence” state. Review sentiment is also not ground truth; it remains a derived layer.

## 4. Opening-hours gap

- Current coverage: **1,141/3,130 (36.45%)**.
- Missing: **1,989/3,130 (63.55%)**.
- Metadata scaling confirms 7,968 opening-hours relation rows, but relation-row count is not place coverage; the place-level master metric above is the correct KPI.
- Region-level coverage is low everywhere (about 26%–44%), with the largest improvement opportunity in Lampung Tengah, Lampung Barat, Way Kanan, and Mesuji.

**Apify-fillable:** Google Maps regular hours, day-specific hours, and possibly `temporarily closed`/operational signals when exposed by the detail result. The current `Data/INPUT.json` has `scrapePlaceDetailPage: false`, so the existing broad search configuration is not sufficient to guarantee complete hours extraction; a detail-oriented run and importer mapping are required.

**Other source required:** official attraction/operator pages for venues where Google has no hours, seasonal/special schedules, ticket-gate exceptions, or conflicting listings. Never coerce missing hours into closed: the semantic-null audit explicitly requires `has_opening_hours=False` with status `missing`.

## 5. Price gap

| Metric | Current value |
|---|---:|
| Places with valid local price evidence | 8 (0.26%) |
| Valid local observations | 29 |
| External verification queue | 11 places |
| Completed with no price | 10 |
| Completed unresolved | 1 |
| Selected external prices | 0 |
| Verified current prices | 0 |
| External price-not-verified warning | 3,119/3,130 (99.65%) |

The eight local-evidence places are historical-only; the price reconciliation audit records no active verified-current or official-live-unbounded price. The clean-room canary audit found URLs that returned HTTP 200 but lacked identity/price excerpts, and correctly rejected them as unresolved. A zero price must not be inferred from no result.

**Apify-fillable (limited):** a Google Maps price tier, menu/service snippets, or an explicit price field where the listing publishes one. This can improve discovery and candidate evidence, but it is not sufficient for admission tickets, parking, boat hire, ride packages, seasonal rates, or “current” guarantees. The current Apify input also sets `maxReviews: 0` and `scrapePlaceDetailPage: false`, reinforcing that the broad run is not a complete price collector.

**Other source required:** official venue/park/operator sites, official social channels where permitted, tourism authority pages, or manual verification. Every price needs amount/unit/applicability, source URL, observed/effective date, currency, and verification status. Priority should be the 166 high/medium price-scope places, not all 3,130 equally.

## 6. Identity and deduplication risks

The final manifest passes the basic invariant (**3,130 rows = 3,130 unique canonical IDs**), but collection expansion still has material identity risks:

1. The prior raw run contained 1,212 records, 659 canonical attractions, 381 merged duplicates, and 282 manual-review candidates. This is a high duplicate pressure signal, especially from broad overlapping keywords.
2. Cross-source audit found only 5 Apify↔OSM merges, 499 Apify-only attractions, 155 OSM-only attractions, and 16 possible parent/child links. A low merge count does not prove absence of duplicates; it can also indicate conservative matching or source population differences.
3. The report lists repeated OSM source IDs in merged-source histories (for example, repeated `osm_node_6050519591`), so source lineage should be deduplicated independently of canonical identity.
4. Apify tests correctly prevent merging two different Google Place IDs even when names and coordinates are nearly identical, and they distinguish cross-region same-name records. This protects against over-merging but leaves “possible duplicate” review queues that must be resolved rather than discarded.
5. Parent/child/supporting-facility links are intentionally separate from merges. Tests cover attraction components, parking, transport, forbidden administrative/travel-agency links, and cross-region rejection. A future run must preserve these semantics; otherwise a parking lot, resort component, or travel agency can inflate attraction counts.
6. Records without a place ID receive a generated 16-character fallback ID. This supports ingestion/idempotency but is not a durable external identity and can cause duplicate rows across reruns unless matched on normalized name, coordinates, region, and provenance.
7. Apify's overlapping search strings (`taman`, `wisata`, `museum`, `pantai`, etc.) make repeated listings expected. Preserve `source_place_id`, source URL/CID, query keyword, collection timestamp, and raw payload; dedupe only after normalization and matching.

**Required identity controls before scale-up:** reject/queue missing stable IDs for manual resolution, retain a persistent source-ID-to-canonical-ID map, run exact Google Place ID dedupe first, use name+distance only with category/region corroboration, keep parent-child links separate, and export possible duplicates for review. Do not merge different Google Place IDs solely on name and proximity.

## 7. Collection priority tiers

### Tier 0 — integrity and targeting gate (before bulk collection)

- Normalize region labels and preserve all 15-region quotas.
- Resolve the 138 unmapped metadata records, starting with Lampung Barat, Lampung Selatan, and Lampung Tengah.
- Freeze/checkpoint source IDs, canonical IDs, query keyword, and timestamps; prevent generated fallback IDs from becoming silent duplicates.
- Treat `other` as a taxonomy review queue, not as a new category target.

### Tier 1 — highest impact Apify collection

1. **Opening hours for all 1,989 missing places**, prioritizing regions below ~30% coverage (Lampung Tengah, Lampung Barat, Way Kanan, Mesuji) and high-traffic categories. Run detail-enabled Google collection and retain missing/seasonal states.
2. **Reviews for the 2,958 no-review places**, beginning with the 271 eligible pilot places and then the remaining places with stable Google IDs. Keep three review modes only where cost/coverage justifies it; do not retry `no_google_reviews` indefinitely.
3. **Metadata recovery** for unmapped places and missing phone/address/website fields where Google has a stable listing.

### Tier 2 — targeted discovery and enrichment

- Category-balanced searches for culture, education, religious, river, lake, and other long-tail categories, with official-registry/manual validation.
- Facilities and operational-status refreshes, especially places whose metadata is mapped but facility data is unknown or status is stale.
- Regional expansion in historically weak/underrepresented collection areas while preserving pilot caps.

### Tier 3 — non-Apify / human-verified work

- Current prices for the 166 in-scope places, starting with the highest-demand venues and the 11 existing verification-queue candidates.
- Attractions with no Google listing/reviews, official opening schedules, seasonal closures, ticket rules, boat/parking rates, and culturally ambiguous categories.
- Non-Google review platforms only if licensing/provenance requirements are acceptable.

## Evidence index

- `Data/consolidated/recommender_ready_manifest.json` — v1.3, 3,130 rows, 21 categories, 15 regions, 172 sentiment-integrated places, 2,245 rating-signal places, 2,245 ranking-safe ratings.
- `Scraping/reports/consolidated_master_summary.md` — full-master layer coverage, region distribution, warning distribution, price scope.
- `Scraping/reports/metadata_scaling_manifest_audit.md` and `metadata_scaling_region_coverage.csv` — metadata/opening-hours/facilities relation and regional mapping rates.
- `Scraping/reports/consolidated_master_source_inventory.md` — source Parquet/CSV row and ID counts.
- `Scraping/reports/consolidated_master_review_coverage.csv` and `consolidated_master_final_quality_warning_distribution.csv` — review and warning metrics.
- `Scraping/reports/consolidated_master_category_coverage.csv` — current category counts/completeness.
- `Scraping/reports/cross_source_dedup_report.md` and `consolidated_master_duplicate_audit.csv` — identity/dedup evidence.
- `Scraping/reports/coverage_report.md` and `apify_bandar_lampung_audit.md` — historical/raw Apify collection, yields, and pre-scale regional gap.
- `Scraping/tests/test_apify_pipeline.py`, `test_enrichment_pipeline.py`, and `test_enrichment_pilot.py` — importer behavior, review coverage semantics, ID and parent/child safeguards.
- `Scraping/reports/consolidated_master_final_price_reconciliation.csv` and `cleanroom_canary_audit.md` — price evidence and verification limitations.

**Bottom line:** use Apify next for hours, reviews, stable Google metadata, and category candidate discovery; use authoritative/operator sources and manual verification for prices, non-Google evidence, unresolved identities, and ambiguous taxonomy. The next run should be region-balanced and identity-safe rather than another broad Bandar Lampung keyword sweep.
