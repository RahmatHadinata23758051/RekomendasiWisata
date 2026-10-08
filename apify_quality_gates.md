# Apify Import Quality Gates and Master-Pipeline Data Contract

**Status:** Design / acceptance policy (no code changes made)  
**Scope:** Apify Google Maps imports, normalized records, cross-source deduplication, enrichment, reconciliation, and consolidated master publication  
**Applies to:** Every import run, including a re-run of an unchanged export  
**Owner:** Data ingestion and recommendation-data maintainers

## 1. Executive decision

An Apify export must be treated as an immutable, versioned source snapshot. It may enter the staging layer after parsing, but it must not update the canonical or recommender datasets until all hard gates pass and the remaining row-level exceptions have been quarantined with reason codes.

The existing pipeline has the right broad stages—raw Apify records, normalization, deduplication, enrichment, and a consolidated master—but its current acceptance checks are too permissive for unattended publication. In particular, the importer currently requires only a non-empty `title`, can synthesize a place ID from title and coordinates, defaults an unrecognized region to Bandar Lampung during normalization, uses a coarse provincial bounding box, and records only limited provenance for reviews and prices. These behaviors are acceptable as staging inputs only; they are not publication-quality identity or provenance guarantees.

### Evidence from the repository (as-of the existing July 2026 reports)

- A Bandar Lampung Apify audit contained **882 raw records / 882 unique IDs**, with **509 accepted, 168 rejected, and 205 manual-review** records.
- That audit reported **181 records without a rating (20.52%)**, 181 without a review count, 2 without an address, 0 without coordinates, and 22 outside the Bandar Lampung boundary box (2.49%).
- The province-wide reconciliation reported **4,869 raw inputs** (4,539 Apify and 330 OSM), **4,207 normalized**, **500 rejected**, and **162 duplicate source records removed**. The conservation equation passed: `4,869 = 4,207 + 500 + 162`.
- The same reconciliation produced **4,178 canonical places** from 4,207 normalized records, with 29 merges. This equation passed: `4,207 = 4,178 + 29`.
- The latest consolidated-master summary reports 3,130 identity rows (100%), but only **172/3,130 review coverage (5.50%)**, **1,141/3,130 opening-hours coverage (36.45%)**, **8/3,130 local-price coverage (0.26%)**, and **0 external verified prices**. These are coverage facts, not failures by themselves; publication must expose them as explicit statuses rather than implying completeness.
- The existing 300-row join audit is a useful target: every join stage stayed at 300 rows, 300 unique IDs, zero duplicate IDs, and row multiplier 1.0. The same invariant is required for the full master.

The July evidence is not a current-freshness pass. With a 7-day identity/review freshness SLA and a 30-day maximum stale-serving window, these snapshots must be marked stale until refreshed.

## 2. Current contract and observed risks

### 2.1 Current normalized model flow

The current models in `Scraping/src/models/schemas.py` represent these layers:

1. `RawAttractionRecord`: source identity, raw name/address/categories, coordinates, source payload path, status, rating, review count, and collection time.
2. `NormalizedAttractionRecord`: cleaned identity, regional assignment, categories, contact fields, business status, classification and confidence, and dedup annotations.
3. `CanonicalAttractionRecord`: canonical identity, merged fields, category tags, source count, timestamps, dedup confidence, and manual-review flag.
4. `ReviewRecord` and `PriceRecord`: separate enrichment facts.
5. Consolidated master: a flat, one-row-per-`canonical_id` output assembled from canonical, review, metadata, facilities, opening-hours, and price relations.

This separation is sound, but lineage must be made explicit at every boundary. A flat value without its source, observation time, and confidence must not be treated as verified current data.

### 2.2 High-risk behaviors to address before production acceptance

- **Synthetic identity:** if Apify has neither `placeId` nor `cid`, the importer creates an ID from `title + lat + lng`. This is not a provider identity and can collide or change after a name/coordinate correction. Such rows must be quarantined or explicitly labeled `synthetic_identity` and excluded from automatic canonical publication.
- **Region fallback:** `normalize_record` falls back to `Kota Bandar Lampung` when no region is resolved. This can silently misassign an attraction. Unknown region must remain `unknown` and fail the region gate, not be converted to a valid region.
- **Coordinate validation:** the current `parse_coordinate` accepts a value if it is in either latitude or longitude range; it does not independently enforce latitude `[-90, 90]` and longitude `[-180, 180]`, and does not clearly reject NaN. Both axes must be validated independently, followed by the Lampung boundary test.
- **Boundary semantics:** the provincial box (`lat -6.5..-3.5`, `lon 103.0..106.5`) is a coarse inclusion check, not proof that a record belongs to the queried regency/city. Target-region bounding boxes and address/region agreement are separate gates.
- **Random canonical IDs:** deduplication creates `can_<random UUID>` IDs. A full rebuild can therefore change canonical IDs even when inputs are identical. Stable IDs require a persisted identity map or a deterministic canonical-key policy.
- **Snapshot over-counting:** `merge_records` increments `source_count` and can add review counts while processing multiple observations of the same source place. A source snapshot is not a distinct source. `source_count` must count distinct source systems (or the contract must rename it to `observation_count`), and provider aggregate review counts must not be summed across snapshots.
- **Non-deterministic review IDs:** review processing currently uses a random UUID for `review_id`. Reprocessing the same review payload can create duplicates. Review keys must be deterministic.
- **Weak price evidence:** parsed prices carry a URL and timestamp but no quote/excerpt, content hash, identity-match result, or source-type decision. A URL that returns HTTP 200 is not evidence that its page describes the attraction or a current price.
- **Implicit timestamps:** Apify collection time falls back to import-time `now` when `scrapedAt` is absent. This must be recorded as `timestamp_quality = import_time_fallback` and cannot pass a current-freshness gate.
- **Mutable append output:** append-safe files and manifests are useful staging mechanisms, but the active canonical/master pointer must be transactional. A failed run must never partially replace a prior passing master.

## 3. Required lineage and normalized contract

The existing fields may be retained for compatibility, but the following contract is required for each layer. New fields can be added in an expand/dual-write migration; old readers must continue to receive their existing fields until the migration is verified.

### 3.1 Run and source-snapshot fields (mandatory for every raw row)

| Field | Requirement |
|---|---|
| `ingestion_run_id` | UUID/ULID for the run; non-null and stable for all rows in the run |
| `source` | Exact enum: `apify_google_maps`, `google_places`, `osm`, `official_sites` |
| `source_file_uri` | Immutable path/object key to the original export |
| `source_file_sha256` | Full SHA-256 of the source file; non-null |
| `source_row_number` | Original array index; non-null and unique within file |
| `source_place_id` | Native Apify `placeId` or `cid` preferred; never silently substitute synthetic IDs |
| `source_id_type` | `native_place_id`, `native_cid`, or `synthetic_identity` |
| `source_record_id` | Deterministic key: `source + source_place_id + provider_account/snapshot namespace` |
| `raw_payload_path` | Immutable raw payload reference; must resolve |
| `collected_at` | Provider timestamp, ISO-8601 UTC; missing provider time must be separately flagged |
| `imported_at` | Ingestion timestamp, ISO-8601 UTC |
| `record_payload_sha256` | Hash of canonicalized raw row; detects same-ID field conflicts |

`source_record_id` is the idempotency key for a source observation, while `source_place_id` is the provider identity. A changed snapshot for the same provider ID is a new observation/version, not another place.

### 3.2 Normalized and canonical fields

At minimum, normalized rows must have non-empty `name`, deterministic `source_record_id`, `source_place_id`, `source`, `ingestion_run_id`, valid `collected_at`, and a resolvable raw payload. Accepted rows must additionally have a valid coordinate pair or an explicit `coordinate_status = missing` and manual-review disposition; `city_regency` must be a configured Lampung value (never a silent default); at least one normalized category or a `missing_category` review reason; and a controlled `business_status`.

Canonical entities must have:

- immutable `canonical_id` (stable across a replay of the same source set);
- one and only one canonical row;
- at least one source mapping row;
- the full source mapping list, match method, score, and decision timestamp;
- `first_seen_at`, `last_seen_at`, and `last_verified_at` with timestamp quality;
- field-level provenance for name, coordinates, region, category, status, rating, review count, price, hours, and facilities;
- `needs_manual_review` and machine-readable reason codes;
- `canonical_status`: `verified`, `candidate`, `quarantined`, or `retired`.

`source_count` means distinct source systems, not raw rows or snapshots. Keep `observation_count` separately if operational reporting needs it.

### 3.3 Enrichment fact contracts

**Reviews:** use a deterministic `review_key = SHA256(source | source_place_id | native_review_id)` when native ID exists; otherwise use a documented fallback hash of normalized text, rating, review date, and source place ID. Store source URL, source-place ID, review observed/published time, collected time, text hash, language, and processing version. A provider aggregate rating and count are separate from the sampled review rows and must not be presented as the same metric.

**Prices:** each observation must contain `price_observation_id`, canonical/source identity, `price_type`, amount or range, currency, applies-to, source URL, source type, observed/published time, fetched time, content hash, identity-match status, evidence excerpt or structured field path, parser version, and confidence. `verified_current` requires an identity match and an allowed source type; `completed_no_price` or `unresolved` must leave amount fields null. “Free” is an explicit observed price of zero only when the evidence states free entry; missing evidence is not zero.

**Operational status:** use a controlled enum (`OPERATIONAL`, `CLOSED_TEMPORARILY`, `CLOSED_PERMANENTLY`, `UNKNOWN`) plus source, checked time, evidence URL, and confidence. A missing status is `UNKNOWN`, not `OPERATIONAL`.

## 4. Apify acceptance gates

The gate runner must produce one machine-readable result per gate, with numerator, denominator, percentage, threshold, severity, and disposition. Percentages are calculated over the stated denominator after excluding only rows explicitly classified in an earlier gate; do not hide failures by changing the denominator.

### 4.1 Batch envelope and identity gates

| ID | Metric and exact rule | Threshold | Failure action |
|---|---|---:|---|
| A0 | File exists, is valid UTF-8 JSON, root is an array, SHA-256 is recorded, and manifest has run ID/file path/size/checksum | 100% | Hard fail entire batch |
| A1 | `raw_row_count = valid_object_rows + malformed_rows + quarantined_rows`; every array index appears exactly once in one bucket | Exact equality | Hard fail; do not publish |
| A2 | JSON object rows have non-empty `title` after trimming | >=99.5% | Quarantine bad rows; hard fail if >0.5% |
| A3 | Rows with native Apify `placeId` or `cid` | >=99.0% for production; 100% preferred | Rows without native ID go to identity quarantine; hard fail if >1.0% |
| A4 | `source_record_id` uniqueness within file and against accepted source registry | 100%; duplicate count = 0 | Quarantine all conflicting versions; hard fail on unresolved conflicts |
| A5 | Same `(source_place_id, source_file_sha256)` replay produces no new accepted rows | Delta = 0 | Hard fail idempotency gate |
| A6 | Same native ID with differing payload hash has a version record and conflict review | 100% of conflicts versioned | Hard fail if conflict is silently overwritten |
| A7 | Raw payload reference resolves and row hash recomputes | 100% of accepted rows | Quarantine unresolved rows; hard fail if >0.1% |

A synthetic-ID row may be retained for audit, but it cannot be `verified` or auto-merged. A run containing synthetic IDs must publish the count and percentage; it must not claim native identity completeness.

### 4.2 Boundary, coordinate, and region gates

| ID | Metric and exact rule | Threshold | Failure action |
|---|---|---:|---|
| B1 | Non-null finite latitude and longitude, each independently in its axis range | >=99.5% of accepted rows | Quarantine invalid rows; hard fail if <99.5% |
| B2 | Accepted coordinates inside Lampung province box (`-6.5 <= lat <= -3.5`, `103.0 <= lon <= 106.5`) | 100% | Quarantine out-of-province rows; hard fail if any is published |
| B3 | Query-region address/coordinates agree with one configured regency/city bbox | >=98.0% | Remaining rows require `boundary_manual_review`; hard fail if >2.0% |
| B4 | Address-derived region and coordinate-derived region agree when both are present | >=99.0% | Manual review; hard fail if <99.0% |
| B5 | Region is a configured one of the 15 Lampung regencies/cities | 100% of accepted rows | Hard fail; `unknown` is not a valid published region |
| B6 | Rows outside the requested city/regency but inside Lampung have an explicit reason and source evidence | 100% of exceptions | Quarantine undocumented exceptions |

The provincial box is a coarse safety boundary. It must not replace the configured regional bboxes or a geospatial boundary dataset when exact administrative membership is required.

### 4.3 Category and attraction eligibility gates

| ID | Metric and exact rule | Threshold | Failure action |
|---|---|---:|---|
| C1 | Non-empty raw category or explicit category-missing reason | >=99.0% | Quarantine/review missing-category rows |
| C2 | Every normalized category maps to the versioned category vocabulary or `other` with reason | 100% | Hard fail unmapped values |
| C3 | No accepted row has a known excluded primary category (hotel, lodging, restaurant, travel agent, school, shop, office, etc.) | 0 excluded-category rows | Reject; never allow name-only override |
| C4 | Automatic `accepted` classification precision on a stratified labeled sample (minimum n=200 or all if fewer) | >=98.0%; lower 95% CI >=95% | Stop auto-accept; route class to manual review |
| C5 | False-positive rate for severe non-attraction classes in the same sample | <=1.0% | Hard fail and quarantine affected rule/category |
| C6 | Manual-review rate is reported by category, region, and query keyword | 100% reporting coverage | Gate failure is observability failure, not a reason to hide rows |

Classification based only on a tourism keyword in the name is insufficient evidence. A category, description, source context, or manual decision must support an accepted classification.

### 4.4 Business status, rating, and review gates

| ID | Metric and exact rule | Threshold | Failure action |
|---|---|---:|---|
| D1 | `business_status` in controlled enum; permanently and temporarily closed flags mapped without contradiction | 100%; contradictions = 0 | Quarantine contradictory rows |
| D2 | Rating is null or numeric in `[1.0, 5.0]` | 100% | Quarantine invalid values |
| D3 | Review count is null or integer `>=0`; rating and count carry the same source observation | 100% paired provenance | Quarantine provenance failures |
| D4 | `review_key` uniqueness in the review fact table | Duplicate keys = 0 | Hard fail; deduplicate before publish |
| D5 | Every review has source place ID, source URL/locator, published/observed time, collected time, and ingestion run ID | 100% | Quarantine incomplete review rows |
| D6 | Review coverage status agrees with eligibility and attempts (`ineligible`, `no_reviews`, `scraped`, `failed`) | 100% of master entities | Hard fail reconciliation |
| D7 | Review source identity maps to exactly one canonical entity or is in an orphan quarantine | Orphans = 0 in published layer | Do not publish orphan reviews |

Provider aggregate review counts must be retained as observations. Do not add the same place's counts across repeated Apify snapshots or across source systems.

### 4.5 Price provenance gates

| ID | Metric and exact rule | Threshold | Failure action |
|---|---|---:|---|
| E1 | Every non-null published amount has currency, type, applies-to, source URL, observed time, evidence excerpt/field path, content hash, and parser version | 100% | Null the value and quarantine the observation |
| E2 | Amounts are finite and `>=0`; range satisfies `price_min <= price_max`; currency is controlled (`IDR` unless explicitly supported) | 100%; violations = 0 | Hard fail invalid price rows |
| E3 | Price source identity matches the canonical attraction (name plus region/coordinates or source place ID) | >=99% of published price observations | Quarantine unmatched observations |
| E4 | `verified_current` prices have an allowed source type, successful fetch, identity match, and age within current-price SLA | 100% of `verified_current` | Downgrade to `unresolved`/`historical`, never retain current label |
| E5 | No amount is emitted for `completed_no_price`, `completed_unresolved`, `not_verified`, or missing evidence statuses | Violations = 0 | Hard fail master publication |
| E6 | Price parser review sample precision (minimum n=100 observations or all if fewer) | >=98% | Disable parser version and quarantine its outputs |

A URL returning HTTP 200 does not pass E3/E4. The existing clean-room audit demonstrates why: pages can be reachable while the expected attraction identity or price excerpt is absent.

### 4.6 Freshness gates

Freshness is measured from `collected_at`/`observed_at`, not `imported_at`. A fallback import timestamp is never considered current.

| Data fact | Current target | Maximum stale-serving window | Required status when older |
|---|---:|---:|---|
| Apify identity/name/coordinates/status | 30 days | 90 days | `stale_identity` then retire/quarantine |
| Reviews and provider rating/count | 14 days | 60 days | `stale_reviews` |
| Opening hours | 30 days | 90 days | `stale_hours` |
| Prices | 7 days | 30 days | `historical`/`stale_price`; not budget-filter eligible |
| Official metadata/facilities | 90 days | 180 days | `stale_metadata` |

For a normal current release, at least 95% of published identity rows must be within 30 days and 95% of published current prices within 7 days. Any row older than its maximum window cannot be in the active master without an explicit `stale` status and UI/API behavior that prevents it being represented as current.

### 4.7 Completeness and idempotency gates

Core identity completeness is calculated per accepted normalized row as:

`core_completeness = present(name, source_place_id, source_record_id, source, collected_at, category, city_regency, latitude, longitude) / 9`.

- Required core fields: 100% for `verified` canonical rows.
- Core completeness >=8/9 is the minimum for a candidate row; missing coordinate or region must be explicitly visible.
- Optional fields (address, phone, website, hours, facilities, rating, review count) are reported by field and region; absence is not imputed as false, zero, free, or operational.
- The master must carry `coverage_status` for each enrichment layer, including `ineligible`, `not_attempted`, `attempt_failed`, `no_data`, `stale`, and `present`.

Idempotency acceptance requires all of the following:

1. Re-importing a file with the same SHA-256 changes zero accepted source rows, zero canonical IDs, zero review keys, and zero price observation IDs.
2. Re-running normalization and deduplication on an unchanged source registry produces the same source-to-canonical mapping and canonical IDs (byte-for-byte output is preferred; semantic equality is mandatory).
3. Re-running consolidation produces the same row count, unique ID set, join counts, and field values apart from run metadata.
4. A changed source snapshot creates a new observation/version and updates only fields whose provenance selects the new observation.
5. A failed run writes no active pointer and cannot overwrite the last passing master.

## 5. Deduplication and entity-resolution policy

### 5.1 Match order

Use a deterministic, explainable order:

1. Same source system + native source place ID: automatic match, confidence 1.0.
2. Same native Google/Apify place ID across collector formats: automatic match, confidence 1.0.
3. Same normalized phone after country-code normalization, with non-placeholder value: candidate match, confidence 0.95.
4. Same trusted website host and normalized path, excluding generic social/maps hosts: candidate match, confidence 0.95.
5. Exact normalized name plus distance <=500 m: candidate match, confidence 1.0 only after region agreement.
6. Fuzzy name >=90 plus distance <=300 m, or address similarity >=85 plus distance <=500 m: manual-review match unless corroborated by a second independent signal.
7. Possible parent/child, facility, gate, parking, administrative place, or attraction-within-attraction: do not merge; create an explicit relationship edge.

Different native Google place IDs must not be merged solely because names are similar. Parent/child edges are not duplicate merges and must be counted separately.

### 5.2 Dedup acceptance metrics

- Source mapping uniqueness: each source observation maps to exactly one canonical ID or quarantine; 100%.
- Native-ID conflict merges: 0. A canonical cannot contain two different native Google place IDs unless a human-approved merge decision records both IDs and evidence.
- Auto-merge precision: >=99.5% on a stratified labeled sample (minimum 200 matches; lower 95% CI >=98%).
- False-merge rate over all sampled candidate pairs: <=0.5%; severe identity false merges: 0.
- Candidate recall on a fixed gold set of known duplicates: >=95%. If no gold set exists, create one from at least 200 independently reviewed pairs before enabling fuzzy auto-merge.
- Stable replay mapping: 100% of unchanged source observations retain their canonical ID.
- Cluster size alert: any cluster with >3 observations from the same source system, or any sudden >2x increase in median cluster size, requires review; it is not automatically an error because snapshots can be repeated.
- Reconciliation must separately report exact source duplicates, cross-source merges, unresolved duplicate candidates, and parent/child relationships.

### 5.3 Canonical-field conflict resolution

Identity fields (name, coordinate, region) require field-level precedence and conflict records. Provider aggregate ratings/counts are selected from the newest trusted observation, not summed. Status is selected by the newest verified observation with source and confidence. Categories are unioned only after controlled-vocabulary normalization; a source disagreement remains in `source_conflicts` and is not silently resolved. Every selected field must retain `selected_source_record_id` and `selected_observed_at`.

## 6. Enrichment and consolidated-master reconciliation

### 6.1 Master join invariants

For every master release (pilot or full):

- Input population has unique canonical IDs: duplicate count = 0.
- Every population ID exists in canonical verified/candidate input: missing IDs = 0.
- Every one-to-many relation is aggregated before joining.
- Each join stage has `input_rows = output_rows = unique_canonical_ids`; duplicate IDs = 0; row multiplier exactly `1.00`.
- Every relation row has a known canonical ID; orphan reviews, metadata, facilities, hours, and prices = 0 in published layers.
- The final master has exactly one row per canonical ID and no IDs outside the declared population.
- Required field domains, counts, coordinates, statuses, and price invariants pass with zero violations.

The existing 300-row audit (all stages 300 rows, multiplier 1.0) is the expected regression fixture. Run the same audit for 3,130/full population releases; do not rely on a hard-coded population count as the only validation.

### 6.2 Conservation equations

Each release must publish these equations with numerator/denominator detail:

```text
raw_rows
  = valid_normalized_rows
  + rejected_rows
  + quarantined_rows
  + duplicate_source_rows
  + malformed_rows

valid_normalized_rows
  = canonical_roots
  + merged_source_observations
  + explicitly_retained_manual_candidates

canonical_population
  = verified_canonical
  + candidate_canonical
  + quarantined_canonical (not in active master)
```

The terms must be mutually exclusive. Manual-review rows must not disappear between reports, and a duplicate source row must not also be counted as rejected. The earlier `4,869 = 4,207 + 500 + 162` result is a passing example, but future runs must include quarantine and malformed buckets explicitly.

### 6.3 Coverage and semantic-null rules

For each layer, report both row coverage and semantic status. `no_review_data` is different from `ineligible`; `completed_no_price` is different from `not_verified`; `unknown operational status` is different from open; and a null price is different from zero. A master release may pass with low optional coverage, but it fails if status labels are missing or semantically misleading.

Recommended release dashboard fields:

- identity coverage and native-ID rate;
- region and boundary pass rate by region;
- accepted/manual/rejected/quarantined rates by category and keyword;
- dedup match count, merge precision sample, candidate count, and parent/child count;
- review eligibility, attempt, success, no-data, and freshness rates;
- price evidence status counts and current-price coverage;
- metadata, facilities, and hours coverage;
- row-conservation and join-multiplier results;
- source and payload checksums, run version, and gate policy version.

## 7. Quarantine, rollback, and recovery policy

### 7.1 Quarantine classes

Quarantine is a first-class output, not a log-only side effect. Store the raw row, source file checksum, source row number, run ID, normalized error fields, and a stable reason code under a run-scoped location such as:

```text
data/quarantine/apify/<ingestion_run_id>/
  records.jsonl
  identity.jsonl
  boundary.jsonl
  category.jsonl
  status.jsonl
  review.jsonl
  price.jsonl
  freshness.jsonl
  conflicts.jsonl
  gate_results.json
```

Minimum reason codes: `MALFORMED_JSON`, `NON_OBJECT_ROW`, `MISSING_TITLE`, `MISSING_NATIVE_ID`, `DUPLICATE_SOURCE_ID`, `SOURCE_ID_CONFLICT`, `PAYLOAD_UNRESOLVED`, `INVALID_COORDINATE`, `OUTSIDE_PROVINCE`, `OUTSIDE_QUERY_REGION`, `UNKNOWN_REGION`, `MISSING_CATEGORY`, `EXCLUDED_CATEGORY`, `INVALID_STATUS`, `INVALID_RATING`, `INVALID_REVIEW_PROVENANCE`, `INVALID_PRICE_PROVENANCE`, `IDENTITY_MISMATCH`, `STALE_OBSERVATION`, `DEDUP_AMBIGUOUS`, and `ORPHAN_RELATION`.

Rows can be reprocessed after correcting a mapping/rule, but the original quarantine record and decision must remain immutable. A human override requires reviewer ID, decision time, reason, evidence reference, and policy version.

### 7.2 Batch fail versus row quarantine

**Hard batch failure** (no canonical/master commit): malformed root/envelope; checksum/manifest failure; any out-of-province row entering the active set; unresolved source-ID conflict; reconciliation equation mismatch; join multiplier other than 1.0; orphan relation in published output; invalid price/current-status provenance; duplicate review keys; or any gate marked hard fail.

**Row quarantine with otherwise eligible staging:** isolated missing optional fields; invalid coordinates; unknown category; outside query region but inside Lampung; synthetic identity; ambiguous dedup; missing review text; stale enrichment; or unresolved price identity. Thresholds above determine whether the row-level rate escalates to a batch failure.

**Reject:** confirmed non-attraction, permanent duplicate, malformed/unrecoverable row, or confirmed out-of-scope location. Keep the raw evidence and rejection reason.

### 7.3 Transactional publication and rollback

1. Assign `ingestion_run_id` and write raw export/checksum/manifest immutably.
2. Build normalized, dedup, enrichment, and master outputs in a run-scoped staging directory; never write directly to the active dataset.
3. Run all gates and emit `gate_results.json`, reconciliation reports, and checksums for every output.
4. If all hard gates pass, atomically publish a versioned manifest/pointer (for example `master_version`, input checksums, policy version, output checksums, and generated time).
5. If any hard gate fails, leave the previous active pointer unchanged, mark the run `failed` or `quarantined`, and retain staging/quarantine artifacts for diagnosis.
6. To roll back, repoint the active manifest to the last `passed` version after verifying its checksums and API-compatible schema. Do not delete or mutate the failed run.
7. Reprocess quarantine using a new run ID and policy version; do not edit historical rows in place.

Rollback target: the last passing master whose input/output checksums and gate report are available. If no passing version exists, serve no new master rather than publishing incomplete or unverified data.

## 8. Release checklist (must be attached to every Apify run)

- [ ] Source file checksum, row count, provider timestamp quality, and manifest recorded.
- [ ] Raw conservation equation passes; every malformed/rejected/quarantined row is accounted for.
- [ ] Native-ID rate, duplicate/conflict counts, and replay idempotency pass.
- [ ] Coordinate, provincial boundary, query-region, and region-resolution gates pass.
- [ ] Category vocabulary and attraction-eligibility sample pass.
- [ ] Status, rating, review, and deterministic review-key gates pass.
- [ ] Price amounts have identity-matched evidence and correct temporal status; no unsupported amount is published.
- [ ] Freshness SLAs and stale-status behavior pass.
- [ ] Dedup precision/recall sample and stable source-to-canonical mapping pass.
- [ ] Master joins have one row per canonical ID, zero orphans, and multiplier 1.0.
- [ ] Semantic-null audit distinguishes missing, ineligible, unresolved, historical, and current values.
- [ ] Staging output checksums match the release manifest.
- [ ] Active pointer changed only after all hard gates passed; rollback target is known.

## 9. Migration and implementation order (design only)

Use an expand-migrate-contract sequence rather than changing readers and writers at once:

1. **Expand:** add run, snapshot, row-number, native-ID-type, payload-hash, timestamp-quality, field-provenance, deterministic review-key, and controlled status fields as nullable/dual-written fields.
2. **Observe:** generate the gate report in shadow mode for one complete Apify export; compare rates with the existing reports, especially the observed 20.52% missing-rating rate and 2.49% out-of-target-boundary rate.
3. **Backfill:** populate lineage for existing raw/normalized/master artifacts where evidence exists; mark unavailable provenance as `legacy_unknown`, never infer it as current.
4. **Read switch:** make recommendation/API readers consume explicit coverage and temporal statuses; ensure null is not converted to free/open/default Bandar Lampung.
5. **Enforce:** turn hard gates on, enable transactional active-manifest publication, and require the release checklist.
6. **Contract:** only after one compatibility window of passing runs may legacy fields, random-ID behavior, and silent fallbacks be retired.

Backfill and gate runs must be resumable by `ingestion_run_id` and source checksum, with no duplicate source/review/price facts after a retry. Required verification commands should include the importer tests, normalization/dedup tests, reconciliation audit, join audit, semantic-null audit, and an unchanged-input replay test.

## 10. Acceptance outcome for the current data

The existing reports demonstrate useful reconciliation and join accounting, but they do **not** constitute a pass for the proposed production gates. The current data should be classified as **staging / candidate** until native identity lineage, stable canonical IDs, deterministic review keys, field-level review/price provenance, and freshness timestamps are present. The current 0% external verified-price coverage and 5.50% review coverage must be truthfully exposed as coverage statuses; neither should be filled with inferred values. No code was edited as part of this design review.
