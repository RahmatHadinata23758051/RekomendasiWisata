# Apify batch inputs

Version **v1.0** contains copy/paste-ready JSON inputs for the approved Apify Google Maps strategy. These are **raw actor inputs**, not wrapper envelopes: each JSON file is one actor run. Files contain no `APIFY_TOKEN`, secrets, reviewer personal data, or images; `maxImages` is `0` and review personal data is disabled. No Apify call or production import is performed by committing these files.

## Layout and naming

```text
apify_batches/
  index.csv
  README.md
  v1.0/
    SHA256SUMS.txt
    batch-01-canary/
    batch-02-discovery-west/
    batch-03-discovery-east/
    batch-04-review-recovery-a/
    batch-05-review-recovery-b/
```

Names use `*.v1.0.json`. `batch-01` is the first gate: it has the approved Bandar Lampung 25-place discovery canary plus a 25-place review-recovery canary. Discovery batches split the 15 regions west/east for free-account scheduling; every region still has its own actor input. Recovery batches split missing-review IDs round-robin by region to preserve regional balance. `index.csv` is the authoritative file-to-region/run map.

## Safety limits and source basis

* Actor: `compass/crawler-google-places` (Google Maps Scraper).
* Discovery: `maxCrawledPlacesPerSearch=100`, `maxReviews=0`, detail enabled, only public place fields.
* Discovery canary: five high-yield terms (`tempat wisata`, `destinasi wisata`, `pantai`, `taman wisata`, `museum`) and `maxCrawledPlacesPerSearch=25`.
* Review recovery: existing `placeIds` whose checked raw snapshots have no `reviewsCount`; `maxReviews=20`, `reviewsSort=newest`; 25 IDs are reserved for the review canary.
* All inputs use `language=id`, `countryCode=id`, `scrapeReviewsPersonalData=false`, `maxImages=0`, no contacts/leads/social/image-author/competitor enrichment.
* Conservative limits are intentional. Do not increase them or add terms without a new version.

The recovery IDs are generated from the checked-in raw snapshots under `Data/*.json` and are evidence inputs only; they do not change the canonical 3,130-row dataset. Discovery results are candidates until quality gates and reconciliation pass.

## Exact run / export / import procedure

Run from the repository root. **Review the live Actor pricing, account spend cap, and current actor input schema before any run. Never paste a token into an input file or shell history.**

### 1. Verify inputs without contacting Apify

```powershell
cd Scraping
Get-FileHash config/apify_batches/v1.0/batch-01-canary/discovery-bandar_lampung-canary.v1.0.json -Algorithm SHA256
Get-Content config/apify_batches/v1.0/SHA256SUMS.txt
```

The checksums file covers all versioned inputs; each file can be checked with `Get-FileHash` before copy/paste. Confirm each JSON parses and contains no token/key fields.

### 2. Run the discovery canary

In Apify Console, open `compass/crawler-google-places`, paste the exact contents of `v1.0/batch-01-canary/discovery-bandar_lampung-canary.v1.0.json`, and start one run only. Save the run ID, dataset ID, actor version, UTC times, actual billed events/cost, and the exact input file. Download `items?clean=true&format=json`; save it as:

```text
data/raw/apify/google_maps/bandar_lampung/YYYY-MM-DD/places.json
data/raw/apify/google_maps/bandar_lampung/YYYY-MM-DD/input.json
data/raw/apify/google_maps/bandar_lampung/YYYY-MM-DD/run.json
data/raw/apify/google_maps/bandar_lampung/YYYY-MM-DD/checksums.sha256
```

Inspect 25 random records. Stop if root is not an array, `placeId` coverage is below 95%, or more than 10% of coordinates are outside Lampung. Do not import to production; use a temporary output root until all gates pass.

### 3. Run discovery regions

After the canary passes, run each `discovery-*.v1.0.json` from batches 02 and 03 as a separate Actor run (copy/paste one file at a time). Save each export under its exact `region_id/YYYY-MM-DD` path and write run metadata before import. If a region returns fewer than 60 valid rows, use the escalation terms from `apify_dataset_acquisition_strategy.md` in a new, recorded run; do not edit v1.0 in place.

### 4. Run review recovery

After discovery matching, run `review-recovery-canary.v1.0.json` first with `maxReviews=20`; verify nested reviews and `reviewsCount`. Only then run every file in batches 04 and 05, one Actor run per file. Keep the exact `placeIds` and record run/dataset IDs and costs. Do not retry a confirmed zero-review place indefinitely.

### 5. Export, checksum, and import

For every successful run, download the unmodified JSON export and calculate its checksum. Preserve `input.json`, `run.json`, and `checksums.sha256` beside `places.json`; archive raw data before transformation. Then, only after quality gates pass, run:

```powershell
cd Scraping
python -m src.cli import-apify --input "data/raw/apify/google_maps/<region_id>/<YYYY-MM-DD>/places.json"
python -m src.cli import-apify-all --root "data/raw/apify/google_maps"
python -m src.cli normalize
python -m src.cli deduplicate
python -m src.cli report
# Full pipeline option:
python -m src.cli run-pipeline --include-apify
```

The importer must reconcile `valid + failed == raw` and skip an already-recorded checksum. Review recovery exports are staging evidence; nested reviews must be normalized by the review stage and are not a direct canonical overwrite. Never alter `Data/` or `Data/consolidated/` during this batch exercise.

## Operator checklist

- [ ] Confirm actor version/pricing/spend cap and keep `APIFY_TOKEN` in secret storage only.
- [ ] Run and inspect both canaries before batches 02–05.
- [ ] Preserve raw exports and immutable run metadata.
- [ ] Run structural, identity, coordinate, regional, privacy, and cost gates.
- [ ] Quarantine invalid/out-of-region rows; do not silently drop them.
- [ ] Reconcile stable IDs and keep net-new discoveries separate from the canonical catalogue.
- [ ] Record actual invoice/billed events; stop on spend-cap breach.
- [ ] Do not publish or rebuild the recommender dataset from these files alone.
