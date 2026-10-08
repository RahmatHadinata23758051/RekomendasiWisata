# Lampung Tourism Data Collection Pipeline

A robust, modular, and multi-source scraping and data engineering pipeline designed to collect, normalize, deduplicate, and enrich public tourist attractions in all 15 regencies and cities of Lampung Province.

## Project Structure

```text
Scraping/
├── config/
│   ├── regions.yaml        # Coordinates and names for the 15 regencies/cities
│   ├── keywords.yaml       # Configured search terms by category (nature, culture, etc.)
│   ├── sources.yaml        # Target configurations for official government portals
│   └── settings.yaml       # Concurrency, timeouts, retries, and bounding box limits
├── src/
│   ├── collectors/
│   │   ├── base.py         # Abstract base collector with retry/backoff & cache
│   │   ├── osm.py          # OpenStreetMap Overpass QL collector with mirror fallbacks
│   │   ├── google_places.py# Google Places API Text Search collector (New API)
│   │   └── official_sites.py# Scrapers for Lampung official tourism and Jadesta portals
│   ├── models/
│   │   └── schemas.py      # Pydantic data schemas for stages 1 to 5
│   ├── pipeline/
│   │   ├── normalize.py    # Name, phone, coordinate validation & Indonesian price parser
│   │   ├── deduplicate.py  # Fuzzy name match & Haversine distance-based deduplication
│   │   ├── enrich.py       # Price extraction with provenance
│   │   └── reviews.py      # Review sentiment categorization and target distribution
│   ├── storage/
│   │   └── writer.py       # CSV, JSONL, and Parquet multi-format writer
│   ├── reporting/
│   │   └── reporter.py     # Automated markdown and CSV coverage reports
│   └── cli.py              # CLI entry point using Typer
├── data/                   # Git-ignored data repository
│   ├── raw/                # Cached raw HTTP/API response payloads
│   ├── normalized/         # Sanitized normalized records
│   ├── canonical/          # Merged deduplicated attraction profiles
│   ├── reviews/            # Processed reviews
│   └── manual_review/      # Low-confidence match records for human inspection
├── reports/                # Generated data coverage reports
├── tests/                  # Pytest unit tests suite
├── .env.example            # Environment template file
├── .gitignore              # Git ignore rules
├── pyproject.toml          # Package dependencies and configuration
├── README.md               # User documentation
└── run.ps1                 # Windows PowerShell orchestrator script
```

## Installation & Setup

1. **Prerequisites**: Python 3.11 or later is recommended.
2. **Install dependencies**:
   ```powershell
   pip install -e .[dev]
   ```
3. **Configure Environment**:
   * Copy `.env.example` to `.env`.
   * Open `.env` and fill in your `GOOGLE_PLACES_API_KEY`. If left empty, the pipeline will log a warning and safely skip the Google Places stage without crashing.

## Usage

### Orchestrating with PowerShell

You can execute the entire collection, normalization, deduplication, and reporting pipeline in one command using the helper PowerShell script:
```powershell
.\run.ps1
```

### CLI Commands

For granular execution, use the Typer CLI:

#### 1. Discovery (Stage 1)
Collect attraction candidates from a specific source (or all) and cache raw JSON payloads:
```powershell
python -m src.cli discover --source osm
python -m src.cli discover --source google-places
python -m src.cli discover --source official-sites
python -m src.cli discover --source all
```
*Options:*
* `--region <region_id>`: Limit discovery to a specific region (e.g., `bandar_lampung`).
* `--limit <number>`: Cap the number of records collected.
* `--resume`: Use cached raw responses to skip network calls.

#### 1b. Apify Batch Runner & Importer (Stage 1)
Safely list, verify, dry-run, or execute versioned Apify Google Maps batches from `config/apify_batches/v1.0/`:
```powershell
# List all 47 versioned batches and files from the authoritative index
python run_apify.py --list-batches

# Verify APIFY_TOKEN against Apify REST API
python run_apify.py --verify-token

# Dry-run validation without spending API credits or making external requests
python run_apify.py --batch batch-01-canary --dry-run
python run_apify.py --file v1.0/batch-01-canary/discovery-bandar_lampung-canary.v1.0.json --dry-run

# Secure execution (token via APIFY_TOKEN env var or interactive prompt):
python run_apify.py --file v1.0/batch-01-canary/discovery-bandar_lampung-canary.v1.0.json

# Using a local ignored token file (one APIFY_TOKEN per line) and picking a specific account (0-based index):
python run_apify.py --file v1.0/batch-01-canary/discovery-bandar_lampung-canary.v1.0.json --token-file .apify-tokens --token-index 0
python run_apify.py --verify-token --token-file .apify-tokens --token-index 1

# Or using the Typer CLI:
python -m src.cli run-apify --list-batches
python -m src.cli run-apify --dry-run --batch batch-01-canary
python -m src.cli run-apify --file v1.0/batch-01-canary/discovery-bandar_lampung-canary.v1.0.json --token-file .apify-tokens --token-index 0
```

When executed, the runner triggers `compass/crawler-google-places`, polls completion, writes raw artifacts to `data/raw/apify/google_maps/<region>/<date>/places.json`, saves `input.json`, `run.json`, and `checksums.sha256`, and automatically invokes `ApifyGoogleMapsImporter`.

Manual import of an existing exported JSON file:
```powershell
python -m src.cli import-apify --input "data/raw/apify/google_maps/bandar_lampung/2026-07-13/places.json"
```

#### 2. Normalization (Stage 2)
Sanitize names, extract city/regencies from addresses, normalize phone/website URLs, validate coordinates within Lampung bounds, and parse Indonesian price strings:
```powershell
python -m src.cli normalize
```

#### 3. Deduplication & Enrichment (Stage 3 & 4)
Group duplicate entries across sources based on fuzzy name matching and distance metrics. Calculate price ranges with provenance and export low-confidence candidates for manual review:
```powershell
python -m src.cli deduplicate
```

#### 4. Generate Reports (Stage 5)
Produce metrics summaries, regional breakdowns, and coverage lists:
```powershell
python -m src.cli report
```

#### 5. Run Complete Pipeline
Execute the full collection, normalization, deduplication, and reporting steps sequentially:
```powershell
python -m src.cli run-pipeline --include-apify
```

#### 6. Verify Configuration (Dry-Run)
Check that all YAML settings and paths are correct:
```powershell
python -m src.cli run-pipeline --dry-run
```

## Data Quality & Bounding Box Checks

To ensure data integrity, the pipeline validates that coordinates lie inside Lampung Province:
* **Latitude bounds**: `[-6.5, -3.5]`
* **Longitude bounds**: `[103.0, 106.5]`

Any records with coordinates outside these bounds or with missing information are flagged in the reports.

## Running Tests

Run the full suite of unit tests to verify normalization, distance calculations, parsing, and storage writer logic:
```powershell
python -m pytest tests/
```
