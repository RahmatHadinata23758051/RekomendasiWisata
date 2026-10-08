# Apify Google Maps Dataset Acquisition Strategy — Lampung

**Status:** Execution-ready playbook  
**Prepared:** 2026-10-08  
**Scope:** Recover the 3,130-place Lampung catalogue and establish repeatable Apify ingestion through `Scraping/src/collectors/apify_google_maps.py`.

## 1. Objective and baseline

The current ML audit (`ml_model_audit_report.md`, generated 2026-10-08) reports:

| Gap | Current | Recovery target |
|---|---:|---:|
| Places in canonical catalogue | 3,130 | Preserve 3,130 IDs; discover and review net-new candidates |
| Review coverage | 172/3,130 (5.5%); **2,958 missing (94.5%)** | >=90% of active places have a review count; >=80% have at least one captured review |
| Price fields | **3,130/3,130 missing (100%)** | >=70% have a Google price bracket or explicit `price_unavailable`; never turn missing into zero |
| Opening hours | **~36.5% present; 63.5% missing** | >=90% have hours or an explicit `hours_unavailable` outcome |
| Region coverage | 15 Lampung regencies/cities | 15/15 runs completed and quality-gated |

The existing Bandar Lampung Apify audit provides a useful calibration point: 882 raw results, 882 unique place IDs, 509 accepted, 168 rejected, 205 manual-review records. Its keyword yields show that broad terms (`destinasi wisata`, `pantai`, `taman wisata`, `taman kota`) outperform low-precision terms such as `wisata religi`, `agrowisata`, and `pulau wisata`. Therefore this plan separates **catalogue discovery** from **place-detail/review recovery**, rather than assuming one broad search is complete.

### Definition of done

A release is complete only when:

1. Each of the 15 regional runs has a successful Apify run ID, immutable dataset ID, input JSON, export checksum, and manifest entry.
2. The raw export is archived before transformation; rerunning the same checksum is idempotent.
3. Existing canonical places are matched by Google `placeId`, then `cid`/`fid`, then deterministic name+coordinate fallback. No source record is silently overwritten.
4. Coordinates fall inside the Lampung province bounds (`lat -6.5..-3.5`, `lon 103.0..106.5`) and the expected regency; out-of-region rows are quarantined.
5. Place-level completion, review completion, price completion, and hours completion all pass the gates in section 8.
6. Counts and null rates are compared against the pre-run baseline before publishing recommender features.

## 2. Actor selection and billing assumptions

Use the official Apify Store actor **`compass/crawler-google-places` (Google Maps Scraper)**. Its documented output contains the fields already consumed by the collector: `title`, `placeId`, `cid`, `fid`, `address`, `location`, `categories`, `totalScore`, `reviewsCount`, `openingHours`, `price`, `website`, `phoneUnformatted`, `additionalInfo`, `permanentlyClosed`, `temporarilyClosed`, `description`, `imageUrl`, `scrapedAt`, and nested `reviews` when review collection is enabled.

The actor page currently advertises a base rate **from $1.50 per 1,000 scraped places**. Detail and review events are add-ons and vary by Apify subscription; the actor's published example uses approximately **$0.15 per place for additional details** and **$3.70 per 10,000 reviews** on a paid tier (the displayed example is not a quote). Prices change, so verify the Actor's **Pricing** tab immediately before the first paid run. Do not enable contact, social-profile, lead-enrichment, image, table-reservation, competitor-analysis, or personal-reviewer-data add-ons for this dataset.

Cost estimates below use a planning assumption of `$1.50/1,000 places`, `$0.15/place detail`, and `$0.00037/review`; actual billing must be read from the run invoice. Apify compute/subscription charges, retries, and duplicate place-detail events can increase totals.

### Planned volume and cost envelope

| Work package | Planned output | Detail/review setting | Planning estimate |
|---|---:|---|---:|
| 15-region discovery (one run/region) | 3,000–8,000 unique place rows before cross-run dedupe | `scrapePlaceDetailPage=true`, `maxReviews=0` | `$460–$1,230` if every row is billed as detail; `$5–$12` base only |
| Existing-place review recovery | Up to 3,130 matched places | `maxReviews=20`, `reviewsSort="newest"` | Base `$4.70`; reviews up to `$23.16`; detail add-on up to `$469.50` |
| Review long-tail top-up (optional) | 3,130 places | `maxReviews=50`, only places still below 5 reviews | Up to 156,500 reviews: `$57.91` review events plus detail events |
| **Recommended budget authorization** | Discovery + one 20-review recovery + 15% retry reserve | No optional enrichment | **Authorize $650–$1,800**, then stop if live projected spend exceeds the cap |

The high range is deliberate: search runs can rediscover many places and trigger paid detail events. A cheaper alternative is to use the review-recovery run only for the 2,958 missing-review places and set `placeIds` in batches, but direct Place-ID detail extraction is itself a billed add-on. The run operator must capture actual `chargedEvents`/invoice data and update the manifest.

## 3. Exact Actor input contract

### 3.1 Discovery run (one run per region)

Use the following JSON template, substituting the regional `locationQuery` and search terms from section 4:

```json
{
  "searchStringsArray": [
    "tempat wisata",
    "destinasi wisata",
    "objek wisata",
    "wisata alam",
    "pantai",
    "air terjun",
    "bukit",
    "danau",
    "desa wisata",
    "museum",
    "taman wisata",
    "wisata keluarga"
  ],
  "locationQuery": "<REGIONAL NAME>, Lampung, Indonesia",
  "maxCrawledPlacesPerSearch": 100,
  "language": "id",
  "countryCode": "ID",
  "skipClosedPlaces": false,
  "scrapePlaceDetailPage": true,
  "scrapeTableReservationProvider": false,
  "scrapeOrderOnline": false,
  "includeWebResults": false,
  "scrapeDirectories": false,
  "maxQuestions": 0,
  "scrapeContacts": false,
  "maximumLeadsEnrichmentRecords": 0,
  "scrapeSocialMediaProfiles": {
    "facebooks": false,
    "instagrams": false,
    "youtubes": false,
    "tiktoks": false,
    "twitters": false
  },
  "maxReviews": 0,
  "maxImages": 0,
  "scrapeImageAuthors": false,
  "enableCompetitorAnalysis": false
}
```

Why these values:

- `locationQuery` is used instead of embedding the location in every keyword; Apify documents that location-aware searches avoid the 120-result limitation of a bare search URL.
- `maxCrawledPlacesPerSearch=100` is a cost/saturation guard. The actor deduplicates results within a run, but the product of 12 terms and 100 is only a ceiling, not an expected row count. If a region produces fewer than 60 valid rows, run the escalation terms in section 5.
- `scrapePlaceDetailPage=true` is required for dependable hours, amenities, questions, updates, and reviews. It is intentionally disabled for no optional enrichment.
- `skipClosedPlaces=false` preserves closed records so the canonical catalogue can represent operational status rather than silently losing places.
- `language=id` preserves Indonesian labels/review text. Do not enable reviewer personal data; `reviewId` remains available for deduplication.
- `maxReviews=0` makes discovery affordable. Reviews are collected in a separate targeted pass.

### 3.2 Review-recovery input

Create batches of at most 250 canonical Google Place IDs (or the actor's documented supported `placeIds` format) from the 2,958 places without review coverage. Use one run per batch or a scheduler-controlled batch size after a 25-place canary:

```json
{
  "placeIds": ["ChIJ...", "ChIJ..."],
  "language": "id",
  "countryCode": "ID",
  "scrapePlaceDetailPage": true,
  "maxReviews": 20,
  "reviewsSort": "newest",
  "reviewsOrigin": "google",
  "reviewsFilterString": "",
  "scrapeReviewsPersonalData": false,
  "maxImages": 0,
  "scrapeContacts": false,
  "maximumLeadsEnrichmentRecords": 0,
  "enableCompetitorAnalysis": false
}
```

`maxReviews=20` is the default recovery target: enough text for sentiment while bounding cost. Use `reviewsSort="newest"` so future refreshes are incremental. Do not set `reviewsStartDate` on the first recovery; it would omit historical evidence. On later monthly refreshes use a recorded watermark (for example `reviewsStartDate` equal to the last successful run date) and keep newest sorting.

For places still at zero reviews after this pass, retain `review_status="confirmed_no_reviews"`; do not repeatedly retry them. For places with 1–4 reviews, the optional top-up can use `maxReviews=50` and only their Place IDs.

## 4. Fifteen-region execution matrix

Run each row as a separate run (or as 15 child runs through the Apify orchestrator). Keep the exact `region_id` in the local job name and export path. These names and queries are aligned with `Scraping/config/regions.yaml`.

| # | `region_id` | `locationQuery` | Discovery terms (append to the common set) |
|---:|---|---|---|
| 1 | `bandar_lampung` | `Kota Bandar Lampung, Lampung, Indonesia` | `taman kota`; `museum`; `waterpark`; `wisata keluarga` |
| 2 | `metro` | `Kota Metro, Lampung, Indonesia` | `taman kota`; `waterpark`; `wisata edukasi`; `agrowisata` |
| 3 | `lampung_selatan` | `Kabupaten Lampung Selatan, Lampung, Indonesia` | `pantai`; `pulau`; `pemandian`; `camping ground`; `mangrove` |
| 4 | `lampung_tengah` | `Kabupaten Lampung Tengah, Lampung, Indonesia` | `bendungan`; `waduk`; `danau`; `agrowisata`; `desa wisata` |
| 5 | `lampung_timur` | `Kabupaten Lampung Timur, Lampung, Indonesia` | `taman nasional`; `pantai`; `mangrove`; `desa wisata`; `wisata religi` |
| 6 | `lampung_utara` | `Kabupaten Lampung Utara, Lampung, Indonesia` | `air terjun`; `curup`; `bukit`; `pemandian`; `wisata religi` |
| 7 | `lampung_barat` | `Kabupaten Lampung Barat, Lampung, Indonesia` | `danau`; `gunung`; `bukit`; `air terjun`; `kebun kopi`; `camping ground` |
| 8 | `pesawaran` | `Kabupaten Pesawaran, Lampung, Indonesia` | `pantai`; `pulau`; `snorkeling`; `mangrove`; `camping ground` |
| 9 | `tanggamus` | `Kabupaten Tanggamus, Lampung, Indonesia` | `pantai`; `air terjun`; `gunung`; `pemandian`; `desa wisata` |
| 10 | `pringsewu` | `Kabupaten Pringsewu, Lampung, Indonesia` | `taman kota`; `waterpark`; `bendungan`; `wisata keluarga`; `agrowisata` |
| 11 | `pesisir_barat` | `Kabupaten Pesisir Barat, Lampung, Indonesia` | `pantai`; `pulau`; `surfing`; `camping ground`; `mangrove` |
| 12 | `tulang_bawang` | `Kabupaten Tulang Bawang, Lampung, Indonesia` | `taman kota`; `bendungan`; `wisata religi`; `desa wisata`; `wisata keluarga` |
| 13 | `tulang_bawang_barat` | `Kabupaten Tulang Bawang Barat, Lampung, Indonesia` | `taman kota`; `danau`; `bendungan`; `desa wisata`; `wisata budaya` |
| 14 | `mesuji` | `Kabupaten Mesuji, Lampung, Indonesia` | `taman kota`; `danau`; `bendungan`; `wisata keluarga`; `desa wisata` |
| 15 | `way_kanan` | `Kabupaten Way Kanan, Lampung, Indonesia` | `air terjun`; `curup`; `bukit`; `pemandian`; `agrowisata`; `desa wisata` |

The common terms are deliberately limited to 12; do not blindly pass every value from `config/keywords.yaml`. Run category-specific terms only where geography makes sense. The `pulau`, `surfing`, and `snorkeling` terms are intentionally coastal-only. Retain `wisata religi` as a discovery term but expect low yield and manually inspect its category precision.

## 5. Run order and escalation rules

### Phase A — canary (must pass before all regions)

1. Run `bandar_lampung` with only: `tempat wisata`, `destinasi wisata`, `pantai`, `taman wisata`, `museum`; `maxCrawledPlacesPerSearch=25`; `maxReviews=0`.
2. Download JSON and inspect 25 random records for `placeId`, coordinates, `openingHours`, `price`, `reviewsCount`, and `searchString`.
3. Import the canary into a temporary output root, not production. Abort if JSON schema is not an array, `placeId` coverage is <95%, or >10% of coordinates are outside Lampung.

### Phase B — discovery

Run regions in this order: Bandar Lampung, Metro, Lampung Selatan, Pesawaran, Pesisir Barat, Tanggamus, Lampung Barat, Lampung Timur, Lampung Tengah, Pringsewu, Lampung Utara, Way Kanan, Tulang Bawang, Tulang Bawang Barat, Mesuji. This puts high-volume and coastal terms first and exposes schema/billing errors early.

For each run:

1. Save input JSON, run metadata, run ID, dataset ID, and UTC start/end timestamps.
2. Export `items?clean=true&format=json`; preserve the unmodified export.
3. If valid rows are <60, execute a second run for that region using only its escalation terms, `maxCrawledPlacesPerSearch=100`.
4. If out-of-region rows exceed 5%, replace free-text location with a `customGeolocation` polygon made from the configured bbox; do not silently accept the spillover.
5. If Apify reports a failed run or actor timeout, retry once with `maxCrawledPlacesPerSearch=50`; never blindly duplicate a successful dataset.

### Phase C — targeted recovery

After cross-source matching, generate the review batch from canonical IDs with missing review count/text. Use the exact Place ID, not a name-only query. Run a 25-place canary with `maxReviews=20`; verify nested reviews and `reviewsCount` before submitting remaining batches.

## 6. Raw storage and automated ingestion

The current collector already provides the important idempotency primitives:

- `ApifyGoogleMapsImporter.load_raw_dataset()` accepts an Apify JSON array, validates `title`, maps `placeId` → `cid` → deterministic SHA-256 fallback, and creates `RawAttractionRecord` values.
- It maps Actor fields to the project contract (`totalScore` → `rating`, `reviewsCount` → `review_count`, `openingHours` → `opening_hours`, `additionalInfo` → `facilities`, and status fields).
- `import_dataset()` calculates a SHA-256 checksum, writes `data/raw_records/apify_google_maps/<region>/<date>/places.*`, appends failed rows to `data/processed/apify/failed_records.jsonl`, upserts `source_records.parquet` by `source_record_id`, and records `manifest.json`.
- Region extraction expects a path component immediately before a `YYYY-MM-DD` component. Use the exact path convention below so the manifest does not become `unknown_region`.

### Required export convention

```text
Scraping/
  data/raw/apify/google_maps/<region_id>/<YYYY-MM-DD>/places.json
  data/raw/apify/google_maps/<region_id>/<YYYY-MM-DD>/run.json
  data/raw/apify/google_maps/<region_id>/<YYYY-MM-DD>/input.json
  data/raw/apify/google_maps/<region_id>/<YYYY-MM-DD>/checksums.sha256
```

The CLI invocation is:

```powershell
cd Scraping
python -m src.cli import-apify --input `
  "data/raw/apify/google_maps/bandar_lampung/2026-10-08/places.json"
```

For all region files:

```powershell
python -m src.cli import-apify-all --root "data/raw/apify/google_maps"
python -m src.cli normalize
python -m src.cli deduplicate
python -m src.cli report
python -m src.cli run-pipeline --include-apify
```

### Recommended automation wrapper

Implement the following operational steps in the job runner (or a small script called by CI):

```text
for each successful Apify run:
  download dataset JSON to the region/date path
  verify content-type, JSON-array root, non-empty checksum
  write run.json (run_id, dataset_id, input_hash, billed_events, cost, actor_version)
  run structural quality gate (section 8)
  python -m src.cli import-apify --input <path>
  assert manifest entry checksum == downloaded checksum
  assert imported valid + failed == JSON row count
  publish per-region audit CSV/JSON
after all regions:
  import-apify-all -> normalize -> deduplicate -> enrich/reviews -> report
  compare baseline and post-run null-rate metrics
```

### Collector hardening required before production

`apify_google_maps.py` currently imports place-level rows but does not extract nested `reviews` into the review processing dataset. The acquisition run must therefore add a review-normalization stage (inside this collector or an adjacent importer called by it) with these rules:

- Emit one review row per nested `reviews[]` item, keyed by `(place_id, reviewId)`; preserve `publishedAtDate`, stars, text/textTranslated, owner response, and `scrapedAt`.
- Preserve the full place JSON in `raw_payload_path`; never discard fields unknown to the Pydantic schema.
- Map `price` to a separate raw field (for example `raw_price`) before normalization. `RawAttractionRecord` currently has no price field, so relying only on the current constructor cannot recover the 100% price gap.
- Store explicit coverage states: `price_status` (`observed`, `not_listed`, `not_applicable`, `parse_failed`), `hours_status` (`observed`, `not_listed`, `parse_failed`), and `review_status` (`observed`, `confirmed_no_reviews`, `not_attempted`). Null must not mean “free,” “closed,” or “zero reviews.”
- Prefer stable `placeId` and then `cid`; retain both IDs in the raw payload to support future matching. Do not use title alone as an identity key.
- Keep `collected_at` as Actor `scrapedAt` and add the Apify run ID/dataset ID to manifest metadata for provenance.

This is a contract change: add tests beside `Scraping/tests/test_apify_pipeline.py` for nested reviews, `price`, missing-vs-zero states, checksum idempotency, and out-of-bound coordinates before the first full recovery.

## 7. Field mapping and review policy

| Apify field | Pipeline destination | Rule |
|---|---|---|
| `placeId` | `source_place_id` | Primary identity; string, non-empty required for accepted detail rows |
| `cid` / `fid` | raw identity columns | Secondary identity and reconciliation evidence |
| `title` | `raw_name` | Required; reject blank |
| `address`, `location.lat/lng` | address/coordinates | Coordinates required for normal acceptance; quarantine out-of-bounds |
| `categories`, `categoryName` | `raw_categories` | Keep all categories; category filters are not authoritative |
| `totalScore` | `rating` | Null is valid when no rating exists |
| `reviewsCount` | `review_count` | Zero is distinct from null |
| nested `reviews[]` | review staging table | Deduplicate by `reviewId`; do not collect reviewer personal data |
| `price` | raw price + parsed IDR range | Google price bracket is evidence, not an invented rupiah amount |
| `openingHours` | `opening_hours` | Preserve day-level closed intervals; missing is not closed |
| `additionalInfo` | `facilities` | Preserve JSON; missing is `[]`, not all-false |
| `permanentlyClosed`, `temporarilyClosed` | operational status | Keep closed rows for catalogue audit; discovery does not skip them |
| `website`, `phoneUnformatted` | contacts | Public business data only; no contacts enrichment |

For price, Google often exposes `$`, `$$`, etc. Convert only when a documented project policy supplies a category-specific mapping; otherwise keep the bracket and set `price_status=observed_bracket`. Never infer an IDR value from a bracket and never represent an unknown amount as 0. The existing semantic-null audit explicitly requires this behavior.

## 8. Data quality gates (automated stop/go)

### Gate 0 — file and provenance (hard fail)

- HTTP/API export status successful; JSON root is an array.
- Dataset ID, run ID, actor version, input hash, UTC timestamp, and checksum are present.
- `raw_count > 0`; importer count invariant: `valid_count + failed_count == raw_count`.
- A checksum already in `manifest.json` is skipped, not imported a second time.

### Gate 1 — row validity (hard fail if breached)

- `title` non-empty: >=99% of rows.
- `placeId` or `cid`: >=95% of rows; deterministic fallback count is <5% and reported.
- Coordinates present: >=98% of accepted rows.
- Coordinates within Lampung bounds: >=95%; each out-of-bound row is quarantined and sampled.
- Duplicate stable IDs within a run: <1%; duplicates are retained in raw evidence but one canonical source row is selected deterministically.
- Permanently/temporarily closed statuses are not filtered from raw output.

### Gate 2 — coverage targets

Measure both the complete discovery output and the matched 3,130 canonical population:

- Regions: all 15 have at least one accepted row and a non-empty audit.
- Existing-place match: >=90% of canonical IDs have a Place ID/cid match after discovery + targeted recovery; all unresolved records go to manual review.
- Reviews: after recovery, `review_count` non-null for >=90% of active canonical places and nested review rows for >=80%. A zero count is valid and separately reported.
- Hours: `opening_hours` or explicit `hours_status` for >=90%; parse failures <5%.
- Price: raw `price` or explicit `price_status` for >=90%; parsed rupiah min/max remains nullable where only a bracket exists. The goal is evidence coverage, not fabricated numbers.
- Review text language/encoding: UTF-8 decode failures <1%; review IDs unique within a place >=99.5%.

### Gate 3 — regression and publish (hard fail)

- Total canonical row count remains exactly 3,130 after reconciliation; net-new discoveries are in a separate candidate table until reviewed.
- No existing non-null rating, hours, or price evidence is replaced by a null from a newer run.
- `source_records.parquet` is unique on `source_record_id`; manifest raw counts reconcile with audit counts.
- Missing semantic values remain null/explicit status. Specifically, never coerce missing price to 0, missing hours to closed, or missing review count to 0.
- Run `python -m pytest tests/test_apify_pipeline.py tests/test_reconciliation.py tests/test_metadata_backfill.py` and publish the generated coverage report.

A failed gate stops downstream model rebuild. It does not delete raw data; operator fixes the input/run and retries with a new run ID.

## 9. Monitoring, retry, and incremental refresh

Capture for every run: run ID, dataset ID, actor version, input JSON hash, region, term list, count of returned rows, accepted/rejected/quarantined counts, stable-ID coverage, coordinate coverage, review/price/hour coverage, billed events, estimated and actual cost, and export checksum.

Schedule:

- **Initial recovery:** one discovery run per region plus one review-recovery pass for missing-review IDs.
- **Monthly refresh:** discovery terms only for changed/new places, `maxReviews=20`, newest sort, and a stored review watermark; do not re-scrape 3,130 places every month unless null-rate regression is detected.
- **Quarterly full audit:** repeat all 15 discovery runs, compare stable IDs and operational status, then top up reviews only where coverage fell below target.

Retry once on transient actor failure. Use exponential backoff at the orchestrator level (5, 15, 45 minutes). A second failure is an escalation, not an invitation to duplicate a successful dataset. Keep Apify token in environment/secret storage (`APIFY_TOKEN`), never in this report, input JSON committed to Git, or raw logs.

## 10. Legal and privacy controls

Collect only public place and review content needed for the tourism recommender. Keep `scrapeReviewsPersonalData=false`, do not enable contact/lead/social enrichments, and do not publish reviewer names, profile URLs, photos, or IDs. Review text is still user-generated content: restrict access, define retention, and follow Google/Apify terms and applicable Indonesian privacy rules. Preserve source URL, scrape timestamp, and deletion/refresh procedure in provenance metadata.

## 11. Operator checklist

- [ ] Confirm Apify actor version, current pricing, account spend cap, and `APIFY_TOKEN`.
- [ ] Run the 25-place Bandar Lampung canary and inspect output schema.
- [ ] Execute 15 discovery runs using section 4, saving input/run/export/checksum artifacts.
- [ ] Run structural gates; quarantine, do not delete, invalid/out-of-region records.
- [ ] Reconcile discovered stable IDs against all 3,130 canonical records.
- [ ] Submit review recovery in <=250-place batches with `maxReviews=20`.
- [ ] Harden/test nested review and price mapping in `apify_google_maps.py`.
- [ ] Import with `import-apify-all`, then normalize, deduplicate, enrich, and report.
- [ ] Verify exact 3,130 canonical rows and all Gate 3 invariants.
- [ ] Publish the post-run null-rate report and actual Apify invoice/cost.

## 12. References

- Apify Google Maps Scraper Actor: <https://apify.com/compass/crawler-google-places>
- Actor OpenAPI/input documentation: <https://apify.com/compass/crawler-google-places/api/openapi>
- Apify dataset API: <https://docs.apify.com/api/v2>
- Repository implementation: `Scraping/src/collectors/apify_google_maps.py`
- Existing actor audit: `Scraping/reports/apify_bandar_lampung_audit.md`
- Existing ML baseline and null-rate evidence: `ml_model_audit_report.md`
- Regional names/bboxes: `Scraping/config/regions.yaml`
- Existing pipeline usage: `Scraping/README.md`
