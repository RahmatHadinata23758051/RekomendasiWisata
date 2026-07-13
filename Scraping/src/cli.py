import typer
import asyncio
import os
import glob
import json
import logging
import pandas as pd
from datetime import datetime, timezone
from typing import Optional
from rich.console import Console
from rich.logging import RichHandler

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)]
)
logger = logging.getLogger("scraper.cli")
console = Console()

app = typer.Typer(help="Lampung Tourism Data Collection CLI")

def get_event_loop():
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop

@app.command()
def discover(
    source: str = typer.Option(..., help="Collector source: osm, google-places, official-sites, all"),
    region: Optional[str] = typer.Option(None, help="Specific region ID (e.g. bandar_lampung)"),
    keyword: Optional[str] = typer.Option(None, help="Specific keyword to search"),
    limit: Optional[int] = typer.Option(None, help="Limit number of items to collect"),
    resume: bool = typer.Option(False, "--resume", help="Resume from cached response files"),
    output_dir: Optional[str] = typer.Option(None, help="Override output directory for raw files")
):
    """
    Stage 1: Discover attraction candidates from sources and save raw payloads.
    """
    from src.collectors.osm import OSMCollector
    from src.collectors.google_places import GooglePlacesCollector
    from src.collectors.official_sites import OfficialSitesCollector
    from src.storage.writer import save_dataset
    
    loop = get_event_loop()
    
    async def run_discovery():
        collectors = []
        if source in ["osm", "all"]:
            collectors.append(OSMCollector())
        if source in ["google-places", "all"]:
            collectors.append(GooglePlacesCollector())
        if source in ["official-sites", "all"]:
            collectors.append(OfficialSitesCollector())
            
        all_raw_records = []
        
        for col in collectors:
            if output_dir:
                col.raw_dir = output_dir
            try:
                console.print(f"[bold blue]Running discovery for source: {col.source_name}[/bold blue]")
                records = await col.discover(region_id=region, keyword=keyword, limit=limit, resume=resume)
                all_raw_records.extend(records)
                console.print(f"[green]Discovered {len(records)} raw records for source {col.source_name}[/green]")
                
                # Save raw records as list of dicts to standard file
                if records:
                    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    save_dir = os.path.join("data", "raw_records", col.source_name)
                    res = save_dataset(records, save_dir, f"raw_records_{date_str}")
                    console.print(f"Saved dataset formats to: {res}")
            except Exception as e:
                logger.error(f"Discovery failed for source {col.source_name}: {e}", exc_info=True)
            finally:
                await col.close()
                
        return all_raw_records

    loop.run_until_complete(run_discovery())

@app.command(name="import-apify")
def import_apify(
    input: str = typer.Option("data/raw/apify/google_maps/bandar_lampung/2026-07-13/places.json", help="Path to Apify exported JSON file")
):
    """
    Import raw Apify Google Maps exported dataset.
    """
    from src.collectors.apify_google_maps import ApifyGoogleMapsImporter
    console.print(f"[bold blue]Importing Apify dataset from {input}...[/bold blue]")
    try:
        importer = ApifyGoogleMapsImporter()
        result = importer.import_dataset(input)
        if result.get("is_skipped"):
            console.print(f"[yellow]Skipped (already imported): {input}[/yellow]")
        else:
            console.print(f"[green]Successfully imported Apify dataset![/green]")
            console.print(f" - Valid records: {result['valid_count']}")
            console.print(f" - Failed records: {result['failed_count']}")
    except Exception as e:
        console.print(f"[red]Failed to import Apify dataset: {e}[/red]")
        raise e

@app.command(name="import-apify-all")
def import_apify_all(
    root: str = typer.Option("data/raw/apify/google_maps", help="Root directory containing region folders with places.json")
):
    """
    Recursively discover and import all places.json files from the root directory.
    """
    from src.collectors.apify_google_maps import ApifyGoogleMapsImporter
    
    console.print(f"[bold blue]Scanning for places.json recursively in {root}...[/bold blue]")
    pattern = os.path.join(root, "**", "places.json")
    pattern = pattern.replace("\\", "/")
    files = glob.glob(pattern, recursive=True)
    
    if not files:
        console.print("[yellow]No places.json files found recursively.[/yellow]")
        return
        
    console.print(f"[green]Found {len(files)} places.json file(s) to import.[/green]")
    importer = ApifyGoogleMapsImporter()
    
    total_valid = 0
    total_failed = 0
    
    for filepath in sorted(files):
        filepath_normalized = filepath.replace("\\", "/")
        console.print(f"\n[bold]Importing: {filepath_normalized}[/bold]")
        try:
            result = importer.import_dataset(filepath_normalized)
            if result.get("is_skipped"):
                console.print(f"[yellow]Skipped (already imported): {filepath_normalized}[/yellow]")
            else:
                console.print(f"[green]Successfully imported![/green]")
                console.print(f" - Valid: {result['valid_count']}")
                console.print(f" - Failed: {result['failed_count']}")
                total_valid += result['valid_count']
                total_failed += result['failed_count']
        except Exception as e:
            console.print(f"[red]Failed to import {filepath_normalized}: {e}[/red]")
            
    console.print(f"\n[bold green]All imports completed. Total new valid: {total_valid}, new failed: {total_failed}[/bold green]")

@app.command()
def normalize(
    input_dir: str = typer.Option("data/raw_records", help="Directory containing raw records"),
    output_dir: str = typer.Option("data/normalized", help="Directory to save normalized records")
):
    """
    Stage 2: Normalize fields like name, address, coordinates, and contact details.
    """
    from src.models.schemas import RawAttractionRecord, NormalizedAttractionRecord
    from src.pipeline.normalize import normalize_record
    from src.storage.writer import save_dataset
    
    import hashlib
    import re

    console.print("[bold blue]Starting Normalization stage...[/bold blue]")
    
    # 1. Load manifest for Apify Google Maps
    manifest_path = os.path.join(input_dir, "apify_google_maps", "manifest.json")
    apify_files = []
    expected_apify_raw = 0
    
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception as e:
            console.print(f"[red]Failed to load manifest: {e}[/red]")
            raise typer.Exit(code=1)
            
        for entry in manifest:
            raw_path = entry["filepath"]
            if not os.path.exists(raw_path):
                # Try relative to CWD if it was saved as relative
                raw_path = os.path.join(os.getcwd(), raw_path)
            if not os.path.exists(raw_path):
                console.print(f"[red]Reconciliation Error: Raw source file not found: {entry['filepath']}[/red]")
                raise typer.Exit(code=1)
                
            # Validate checksum
            hasher = hashlib.sha256()
            with open(raw_path, "rb") as bf:
                for chunk in iter(lambda: bf.read(4096), b""):
                    hasher.update(chunk)
            current_checksum = hasher.hexdigest()
            if current_checksum != entry["checksum"]:
                console.print(f"[red]Reconciliation Error: Checksum mismatch for raw file {raw_path}. Expected {entry['checksum']}, got {current_checksum}[/red]")
                raise typer.Exit(code=1)
                
            # Count elements in raw places.json
            try:
                with open(raw_path, "r", encoding="utf-8") as rf:
                    raw_data = json.load(rf)
                    file_raw_count = len(raw_data)
                    expected_apify_raw += file_raw_count
            except Exception as e:
                console.print(f"[red]Failed to load raw JSON {raw_path}: {e}[/red]")
                raise typer.Exit(code=1)
                
            # Determine date folder from path
            path_parts = os.path.normpath(raw_path).replace("\\", "/").split("/")
            date_str = None
            date_pat = re.compile(r"^\d{4}-\d{2}-\d{2}$")
            for part in path_parts:
                if date_pat.match(part):
                    date_str = part
                    break
            if not date_str:
                date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                
            staging_jsonl = os.path.join(input_dir, "apify_google_maps", entry["region"], date_str, "places.jsonl")
            if not os.path.exists(staging_jsonl):
                console.print(f"[red]Reconciliation Error: Staging jsonl file not found: {staging_jsonl}[/red]")
                raise typer.Exit(code=1)
                
            apify_files.append((staging_jsonl, file_raw_count))
            
    # 2. Count OSM raw records
    osm_files = glob.glob(os.path.join(input_dir, "osm", "*.jsonl"))
    osm_raw = 0
    for filepath in osm_files:
        with open(filepath, "r", encoding="utf-8") as f:
            osm_raw += sum(1 for line in f if line.strip())
            
    expected_total_raw = expected_apify_raw + osm_raw
    if expected_total_raw == 0:
        console.print("[yellow]No raw records to process.[/yellow]")
        return
        
    # 3. Load records and verify counts file-by-file
    raw_records = []
    
    def load_jsonl_file(filepath):
        file_records = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = RawAttractionRecord.model_validate(json.loads(line))
                    file_records.append(rec)
        return file_records

    # Load Apify
    for filepath, expected_count in apify_files:
        with open(filepath, "r", encoding="utf-8") as f:
            count = sum(1 for line in f if line.strip())
        if count != expected_count:
            console.print(f"[red]Reconciliation Error: Staging file {filepath} has {count} records, but raw file has {expected_count} records.[/red]")
            raise typer.Exit(code=1)
            
        file_records = load_jsonl_file(filepath)
        raw_records.extend(file_records)
        
    # Load OSM
    for filepath in osm_files:
        file_records = load_jsonl_file(filepath)
        raw_records.extend(file_records)
        
    actual_total_raw = len(raw_records)
    if actual_total_raw != expected_total_raw:
        console.print(f"[red]Reconciliation Error: Total loaded raw records ({actual_total_raw}) does not match expected raw records ({expected_total_raw}).[/red]")
        raise typer.Exit(code=1)
        
    # Deduplicate source_record_id for pipeline flow
    unique_raw_records = []
    seen_ids = set()
    for rec in raw_records:
        if rec.source_record_id not in seen_ids:
            seen_ids.add(rec.source_record_id)
            unique_raw_records.append(rec)
            
    console.print(f"Loaded {len(raw_records)} raw records before source deduplication, {len(unique_raw_records)} after source deduplication.")
    raw_records = unique_raw_records
    
    normalized_records = []
    all_normalized_records = []
    apify_accepted = []
    apify_manual = []
    apify_rejected = []
    
    for raw in raw_records:
        try:
            norm = normalize_record(raw)
            all_normalized_records.append(norm)
            
            # Segregate Apify specific classifications
            if norm.source == "apify_google_maps":
                if norm.classification == "accepted":
                    apify_accepted.append(norm)
                elif norm.classification == "manual_review":
                    apify_manual.append(norm)
                elif norm.classification == "rejected":
                    apify_rejected.append(norm)
            
            # Filter out rejected records from going to deduplication
            if norm.classification != "rejected":
                normalized_records.append(norm)
        except Exception as e:
            logger.warning(f"Failed to normalize record {raw.source_record_id}: {e}")
            
    # Save general normalized records (non-rejected)
    if normalized_records:
        res = save_dataset(normalized_records, output_dir, "normalized_attractions")
        console.print(f"[green]Normalized {len(normalized_records)} records (excluding rejected) and saved: {res}[/green]")
    else:
        console.print("[yellow]No records normalized.[/yellow]")
        
    # Save all normalized records (including rejected)
    if all_normalized_records:
        res_all = save_dataset(all_normalized_records, output_dir, "all_normalized")
        console.print(f"[green]Saved all {len(all_normalized_records)} normalized records (including rejected) to: {res_all}[/green]")
        
    # Save Apify processed outputs
    apify_processed_dir = os.path.join("data", "processed", "apify")
    os.makedirs(apify_processed_dir, exist_ok=True)
    
    if apify_accepted:
        res_accepted = save_dataset(apify_accepted, apify_processed_dir, "attractions_accepted")
        console.print(f"[green]Saved {len(apify_accepted)} accepted Apify records to data/processed/apify/[/green]")
    else:
        for ext in ["csv", "jsonl", "parquet"]:
            open(os.path.join(apify_processed_dir, f"attractions_accepted.{ext}"), "w").close()

    # Save manual review list as CSV
    df_manual = pd.DataFrame([r.model_dump() for r in apify_manual]) if apify_manual else pd.DataFrame(columns=list(NormalizedAttractionRecord.model_fields.keys()))
    df_manual.to_csv(os.path.join(apify_processed_dir, "manual_review.csv"), index=False, encoding="utf-8")
    console.print(f"[yellow]Saved {len(apify_manual)} Apify manual review records to manual_review.csv[/yellow]")

    # Save rejected list as CSV
    df_rejected = pd.DataFrame([r.model_dump() for r in apify_rejected]) if apify_rejected else pd.DataFrame(columns=list(NormalizedAttractionRecord.model_fields.keys()))
    df_rejected.to_csv(os.path.join(apify_processed_dir, "rejected_places.csv"), index=False, encoding="utf-8")
    console.print(f"[red]Saved {len(apify_rejected)} Apify rejected records to rejected_places.csv[/red]")

@app.command()
def deduplicate(
    input_file: str = typer.Option("data/normalized/normalized_attractions.jsonl", help="Normalized JSONL file path"),
    output_dir: str = typer.Option("data/canonical", help="Directory to save canonical records")
):
    """
    Stage 3 & 4: Deduplicate similar records, merge attributes, and enrich with price range/ provenance.
    """
    from src.models.schemas import NormalizedAttractionRecord
    from src.pipeline.deduplicate import deduplicate_records
    from src.pipeline.enrich import extract_prices_from_text, enrich_canonical_place
    from src.storage.writer import save_dataset
    
    console.print("[bold blue]Starting Deduplication and Enrichment stage...[/bold blue]")
    
    if not os.path.exists(input_file):
        console.print(f"[red]Normalized records file not found at {input_file}. Run normalize first.[/red]")
        return
        
    records = []
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(NormalizedAttractionRecord.model_validate(json.loads(line)))
    except Exception as e:
        logger.error(f"Error reading normalized file: {e}")
        return
        
    console.print(f"Loaded {len(records)} normalized records.")
    
    canonical_places, mappings = deduplicate_records(records)
    
    # Enrichment: For each canonical place, look for descriptions/address/names to extract price information
    enriched_places = []
    for place in canonical_places:
        text_for_prices = f"{place.name} {place.address or ''} {place.price_notes or ''}"
        price_records = extract_prices_from_text(text_for_prices, place.website)
        enriched_place = enrich_canonical_place(place, price_records)
        enriched_places.append(enriched_place)
        
    # Re-save the updated normalized records (with dedup_cluster_id and dedup_reason populated)
    save_dataset(records, "data/normalized", "normalized_attractions")
    console.print("[green]Updated normalized_attractions records with cluster and dedup info.[/green]")

    # Restructured Dataset Policy:
    # 1. Master Verified: accepted records or valid OSM records
    # 2. Candidates: manual review records only
    verified_places = []
    candidate_places = []
    
    for place in enriched_places:
        if place.classification == "accepted" or place.primary_source == "osm":
            verified_places.append(place)
        else:
            candidate_places.append(place)
            
    # Save master verified
    res_verified = save_dataset(verified_places, output_dir, "attractions_master_verified")
    console.print(f"[green]Created {len(verified_places)} attractions_master_verified records and saved: {res_verified}[/green]")
    
    # Save candidates
    res_candidates = save_dataset(candidate_places, output_dir, "attractions_candidates")
    console.print(f"[yellow]Created {len(candidate_places)} attractions_candidates records and saved: {res_candidates}[/yellow]")
    
    # Save attraction sources mapping table as Parquet format
    if mappings:
        df_mappings = pd.DataFrame(mappings)
        parquet_path = os.path.join(output_dir, "attraction_sources.parquet")
        df_mappings.to_parquet(parquet_path, index=False, engine="pyarrow")
        console.print(f"[green]Saved source mapping table to {parquet_path}[/green]")
        
        # Save cross_source_matches.csv to reports/
        reports_dir = "reports"
        os.makedirs(reports_dir, exist_ok=True)
        csv_path = os.path.join(reports_dir, "cross_source_matches.csv")
        df_mappings.to_csv(csv_path, index=False, encoding="utf-8")
        console.print(f"[green]Saved matches list to {csv_path}[/green]")

@app.command()
def report():
    """
    Generate automated coverage and data quality report.
    """
    from src.reporting.reporter import generate_reports
    
    console.print("[bold blue]Generating reports...[/bold blue]")
    try:
        generate_reports()
        console.print("[green]Reports generated successfully under reports/ folder.[/green]")
    except Exception as e:
        logger.error(f"Failed to generate reports: {e}", exc_info=True)

@app.command()
def run_pipeline(
    region: Optional[str] = typer.Option(None, help="Specific region ID"),
    keyword: Optional[str] = typer.Option(None, help="Specific keyword"),
    limit: Optional[int] = typer.Option(None, help="Limit number of items to collect per source"),
    resume: bool = typer.Option(False, "--resume", help="Resume from cached response files"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Verify configuration and pipeline flow without scraping"),
    include_apify: bool = typer.Option(False, "--include-apify", help="Include Apify import in the pipeline run")
):
    """
    Runs the complete pipeline: discovery -> normalize -> deduplicate -> report.
    """
    if dry_run:
        console.print("[bold green]Dry Run Validation Mode[/bold green]")
        from src.collectors.google_places import GooglePlacesCollector
        g = GooglePlacesCollector()
        console.print(f"Google Places Configured: {'[green]YES[/green]' if g.is_configured() else '[red]NO (will skip execution)[/red]'}")
        console.print("Validating configurations...")
        for name in ["regions", "keywords", "sources", "settings"]:
            path = f"config/{name}.yaml"
            if os.path.exists(path):
                console.print(f" - {path}: [green]OK[/green]")
            else:
                console.print(f" - {path}: [red]MISSING[/red]")
        console.print("[green]Dry run validation complete.[/green]")
        return
        
    console.print("[bold green]=== RUNNING FULL DATA PIPELINE ===[/bold green]")
    
    # 1. Discover
    console.print("\n[bold]Step 1: Discovery[/bold]")
    if include_apify:
        import_apify_all()
            
    discover(source="all", region=region, keyword=keyword, limit=limit, resume=resume)
    
    # 2. Normalize
    console.print("\n[bold]Step 2: Normalization[/bold]")
    normalize()
    
    # 3. Deduplicate
    console.print("\n[bold]Step 3: Deduplication & Enrichment[/bold]")
    deduplicate()
    
    # 4. Report
    console.print("\n[bold]Step 4: Reporting[/bold]")
    report()
    
    console.print("\n[bold green]=== PIPELINE RUN COMPLETE ===[/bold green]")

@app.command(name="create-enrichment-pilot")
def create_enrichment_pilot(
    size: int = typer.Option(300, help="Target size of the pilot sample"),
    seed: int = typer.Option(42, help="Random seed for selection"),
    input: str = typer.Option("data/canonical/attractions_master_verified.jsonl", help="Input verified canonical attractions JSONL/Parquet path"),
    output_dir: str = typer.Option("data/enrichment/pilot", help="Output directory for pilot datasets"),
    min_per_region: int = typer.Option(10, help="Minimum quota per region"),
    max_region_share: float = typer.Option(0.15, help="Maximum percentage share for a single region"),
    include_special_samples: bool = typer.Option(True, help="Whether to prioritize special sample pools"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Dry run mode to print metrics and allocations without writing files")
):
    """
    Selects 300 representative pilot attractions, sets up schemas, and compiles coverage reports.
    """
    from src.enrichment.pilot_selector import select_pilot_places, write_enrichment_schemas, write_reports
    import pandas as pd
    import json
    
    console.print(f"[bold blue]Creating Enrichment Pilot: size={size}, seed={seed}...[/bold blue]")
    
    try:
        # If input path doesn't exist but parquet does, fallback to parquet
        input_path = input
        if not os.path.exists(input_path) and input_path.endswith(".jsonl"):
            parq_path = input_path.replace(".jsonl", ".parquet")
            if os.path.exists(parq_path):
                input_path = parq_path
                
        # Also determine parquet/jsonl paths
        # We need sources_path and normalized_path
        sources_path = "data/canonical/attraction_sources.parquet"
        normalized_path = "data/normalized/all_normalized.jsonl"
        possible_dup_path = "reports/possible_duplicate_candidates.csv"
        
        # Load verified to pass to write_reports
        if input_path.endswith(".parquet"):
            df_verified = pd.read_parquet(input_path)
        else:
            records = []
            with open(input_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        records.append(json.loads(line))
            df_verified = pd.DataFrame(records)

        df_pilot = select_pilot_places(
            input_path=input_path,
            sources_path=sources_path,
            normalized_path=normalized_path,
            possible_dup_path=possible_dup_path,
            size=size,
            seed=seed,
            min_per_region=min_per_region,
            max_region_share=max_region_share,
            include_special=include_special_samples
        )
        
        console.print(f"[green]Successfully selected {len(df_pilot)} pilot attractions![/green]")
        
        if dry_run:
            console.print("[yellow]Dry run mode enabled. No files written.[/yellow]")
            # Print basic statistics
            console.print(df_pilot["region"].value_counts())
            return
            
        # Write outputs
        os.makedirs(output_dir, exist_ok=True)
        
        # Save pilot places in 3 formats
        df_pilot.to_csv(os.path.join(output_dir, "pilot_places.csv"), index=False, encoding="utf-8")
        df_pilot.to_parquet(os.path.join(output_dir, "pilot_places.parquet"), index=False)
        
        # Save as JSONL
        with open(os.path.join(output_dir, "pilot_places.jsonl"), "w", encoding="utf-8") as f:
            for _, r in df_pilot.iterrows():
                # Convert list/dict values to JSON strings if they're not strings to ensure clean JSONL
                r_dict = r.to_dict()
                if isinstance(r_dict.get("category_tags"), list):
                    pass # json.dumps handles list perfectly
                f.write(json.dumps(r_dict) + "\n")
                
        # 1. pilot_google_places_input.csv
        gp_rows = []
        for _, row in df_pilot.iterrows():
            g_id = row["google_place_id"]
            eligible = pd.notna(g_id) and g_id != ""
            
            gp_rows.append({
                "canonical_id": row["canonical_id"],
                "name": row["name"],
                "region": row["region"],
                "google_place_id": g_id if eligible else "",
                "source_url": row["source_url"],
                "rating": row["rating"],
                "review_count": row["review_count"],
                "positive_review_target": 5,
                "negative_review_target": 5,
                "neutral_review_target": 3,
                "review_scrape_eligible": "true" if eligible else "false",
                "review_scrape_reason": "" if eligible else "No Google Place ID available"
            })
        df_gp = pd.DataFrame(gp_rows)
        df_gp.to_csv(os.path.join(output_dir, "pilot_google_places_input.csv"), index=False, encoding="utf-8")
        
        # 2. pilot_price_research_input.csv
        pr_rows = []
        for _, row in df_pilot.iterrows():
            name = row["name"]
            reg = row["region"]
            cat = row["primary_category"]
            
            # Determine research priority
            # High priority if popular or in important category
            is_popular = str(row["review_count_segment"]) in ["popular", "medium"]
            is_important_cat = str(cat) in ["nature", "beach", "waterfall", "waterpark"]
            priority = "high" if (is_popular or is_important_cat) else "medium"
            
            pr_rows.append({
                "canonical_id": row["canonical_id"],
                "name": name,
                "region": reg,
                "primary_category": cat,
                "website": row["website"],
                "source_url": row["source_url"],
                "search_query": f"{name} harga tiket masuk {reg}",
                "price_status": "to_be_researched",
                "research_priority": priority
            })
        df_pr = pd.DataFrame(pr_rows)
        df_pr.to_csv(os.path.join(output_dir, "pilot_price_research_input.csv"), index=False, encoding="utf-8")
        
        # 3. pilot_selection_manifest.json
        manifest = {
            "batch_id": "enrichment_pilot_300_v1",
            "version": "v1",
            "selected_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "size": len(df_pilot),
            "seed": seed,
            "min_per_region": min_per_region,
            "max_region_share": max_region_share,
            "include_special_samples": include_special_samples,
            "statistics": {
                "region_counts": df_pilot["region"].value_counts().to_dict(),
                "category_counts": df_pilot["primary_category"].value_counts().to_dict(),
                "rating_segments": df_pilot["rating_segment"].value_counts().to_dict(),
                "review_count_segments": df_pilot["review_count_segment"].value_counts().to_dict(),
                "website_presence": df_pilot["has_website"].value_counts().to_dict(),
                "google_place_id_presence": df_pilot["has_google_place_id"].value_counts().to_dict(),
                "selection_reasons": df_pilot["selection_reason"].value_counts().to_dict()
            },
            "selected_canonical_ids": df_pilot["canonical_id"].tolist()
        }
        with open(os.path.join(output_dir, "pilot_selection_manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
            
        # Write schemas
        write_enrichment_schemas()
        
        # Write reports
        write_reports(df_pilot, df_verified)
        
        console.print("[green]Enrichment Pilot outputs successfully generated![/green]")
        
    except Exception as e:
        logger.error(f"Failed to create enrichment pilot: {e}", exc_info=True)
        raise e

@app.command(name="prepare-review-scraping")
def prepare_review_scraping(
    input: str = typer.Option("data/enrichment/pilot/pilot_google_places_input.csv", help="Path to pilot places input CSV"),
    batch_size: int = typer.Option(70, help="Maximum place IDs per batch"),
    output_dir: str = typer.Option("data/enrichment/apify_review_inputs", help="Output directory for Apify payloads")
):
    """
    Task 2: Partition eligible pilot places and build Apify review scraping payloads.
    """
    from src.enrichment.review_payload_builder import build_review_payloads
    console.print(f"[bold blue]Building review scraping payloads from {input}...[/bold blue]")
    try:
        manifest = build_review_payloads(input_csv_path=input, output_dir=output_dir, batch_size=batch_size)
        console.print(f"[green]Successfully generated payloads! Manifest updated at {output_dir}/review_batch_manifest.json[/green]")
    except Exception as e:
        console.print(f"[red]Error preparing payloads: {e}[/red]")
        raise e

def get_run_value(run, attribute, legacy_key=None):
    if hasattr(run, attribute):
        return getattr(run, attribute)
    if isinstance(run, dict):
        return run.get(legacy_key or attribute)
    raise TypeError(f"Expected dict or Pydantic object, got {type(run)}")

@app.command(name="run-review-scraping")
def run_review_scraping(
    mode: str = typer.Option(..., help="Mode: positive, negative, neutral"),
    batch: str = typer.Option(..., help="Batch ID, e.g. batch_001")
):
    """
    Task 3: Run Apify reviews scraper for a single batch.
    """
    from dotenv import load_dotenv
    load_dotenv()
    token = os.getenv("APIFY_TOKEN")
    if not token or str(token).strip() == "":
        console.print("[yellow]APIFY_TOKEN is missing in .env. Skipping execution. (Dry validation mode)[/yellow]")
        return
        
    try:
        from apify_client import ApifyClient
    except ImportError:
        console.print("[red]apify-client library is not installed. Please run 'pip install apify-client' to use this command.[/red]")
        return
        
    manifest_path = "data/enrichment/apify_review_inputs/review_batch_manifest.json"
    if not os.path.exists(manifest_path):
        console.print("[red]Manifest file not found. Please run prepare-review-scraping first.[/red]")
        return
        
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)
        
    entry = None
    for b in manifest_data.get("batches", []):
        if b["batch_id"] == batch and b["mode"] == mode:
            entry = b
            break
            
    if not entry:
        console.print(f"[red]Batch {batch} ({mode}) not found in manifest.[/red]")
        return
        
    if entry.get("status") == "completed":
        console.print(f"[yellow]Batch {batch} ({mode}) is already completed. Skipping.[/yellow]")
        return
        
    client = ApifyClient(token)
    payload_path = os.path.join("data/enrichment/apify_review_inputs", entry["payload_path"])
    with open(payload_path, "r", encoding="utf-8") as pf:
        run_input = json.load(pf)
        
    console.print(f"[blue]Starting Apify actor compass/google-maps-reviews-scraper for {batch} ({mode})...[/blue]")
    run = client.actor("compass/google-maps-reviews-scraper").call(run_input=run_input)
    
    run_id = get_run_value(run, "id")
    dataset_id = get_run_value(run, "default_dataset_id", "defaultDatasetId")
    
    console.print(f"[green]Run completed: run_id={run_id}, dataset_id={dataset_id}[/green]")
    
    # Download dataset
    items = client.dataset(dataset_id).list_items().items
    raw_dir = os.path.join("data/enrichment/raw_reviews", mode)
    os.makedirs(raw_dir, exist_ok=True)
    raw_path = os.path.join(raw_dir, f"{batch}.json")
    with open(raw_path, "w", encoding="utf-8") as rf:
        json.dump(items, rf, indent=2)
        
    console.print(f"[green]Saved {len(items)} raw reviews to {raw_path}[/green]")
    
    # Update manifest
    entry["status"] = "completed"
    entry["apify_run_id"] = run_id
    entry["dataset_id"] = dataset_id
    
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

@app.command(name="run-review-scraping-all")
def run_review_scraping_all():
    """
    Task 3: Run Apify reviews scraper for all pending batches in manifest.
    """
    from dotenv import load_dotenv
    load_dotenv()
    token = os.getenv("APIFY_TOKEN")
    if not token or str(token).strip() == "":
        console.print("[yellow]APIFY_TOKEN is missing in .env. Skipping execution of run-review-scraping-all.[/yellow]")
        return
        
    manifest_path = "data/enrichment/apify_review_inputs/review_batch_manifest.json"
    if not os.path.exists(manifest_path):
        console.print("[red]Manifest file not found. Please run prepare-review-scraping first.[/red]")
        return
        
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)
        
    pending_batches = [b for b in manifest_data.get("batches", []) if b.get("status") != "completed"]
    
    if not pending_batches:
        console.print("[green]All batches in manifest are already completed![/green]")
        return
        
    console.print(f"[bold blue]Running {len(pending_batches)} pending review scraping batches...[/bold blue]")
    
    for b in pending_batches:
        try:
            run_review_scraping(mode=b["mode"], batch=b["batch_id"])
        except Exception as e:
            console.print(f"[red]Error running batch {b['batch_id']} ({b['mode']}): {e}[/red]")

@app.command(name="import-review-results")
def import_review_results(
    mode: str = typer.Option(..., help="Mode: positive, negative, neutral"),
    batch: str = typer.Option(..., help="Batch ID, e.g. batch_001"),
    input: str = typer.Option(..., help="Path to the downloaded result JSON/JSONL file")
):
    """
    Task 4: Import downloaded reviews JSON/JSONL file offline.
    """
    if not os.path.exists(input):
        console.print(f"[red]Input file not found: {input}[/red]")
        return
        
    manifest_path = "data/enrichment/apify_review_inputs/review_batch_manifest.json"
    if not os.path.exists(manifest_path):
        console.print("[red]Manifest file not found. Please run prepare-review-scraping first.[/red]")
        return
        
    # Read input file (handles JSON array or JSONL)
    reviews = []
    try:
        with open(input, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                reviews = data
            elif isinstance(data, dict):
                reviews = [data]
    except Exception:
        # Fallback to JSONL
        try:
            with open(input, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        reviews.append(json.loads(line))
        except Exception as e:
            console.print(f"[red]Failed to parse file as JSON array or JSONL: {e}[/red]")
            return
            
    raw_dir = os.path.join("data/enrichment/raw_reviews", mode)
    os.makedirs(raw_dir, exist_ok=True)
    raw_path = os.path.join(raw_dir, f"{batch}.json")
    
    with open(raw_path, "w", encoding="utf-8") as rf:
        json.dump(reviews, rf, indent=2)
        
    # Update manifest
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)
        
    updated = False
    for b in manifest_data.get("batches", []):
        if b["batch_id"] == batch and b["mode"] == mode:
            b["status"] = "completed"
            b["dataset_id"] = "imported_offline"
            b["apify_run_id"] = "imported_offline"
            updated = True
            break
            
    if updated:
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)
        console.print(f"[green]Imported {len(reviews)} reviews for {batch} ({mode}) successfully.[/green]")
    else:
        console.print(f"[yellow]Batch {batch} ({mode}) not found in manifest, but saved raw file to {raw_path}[/yellow]")

@app.command(name="import-review-results-all")
def import_review_results_all(
    root: str = typer.Option("data/enrichment/raw_reviews", help="Root directory of raw review JSON files")
):
    """
    Task 4: Scan and update batch status in manifest based on raw files present on disk.
    """
    manifest_path = "data/enrichment/apify_review_inputs/review_batch_manifest.json"
    if not os.path.exists(manifest_path):
        console.print("[red]Manifest file not found. Please run prepare-review-scraping first.[/red]")
        return
        
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)
        
    updated_count = 0
    for b in manifest_data.get("batches", []):
        mode = b["mode"]
        batch_id = b["batch_id"]
        raw_path = os.path.join(root, mode, f"{batch_id}.json")
        if os.path.exists(raw_path) and b["status"] != "completed":
            b["status"] = "completed"
            b["dataset_id"] = b["dataset_id"] or "imported_offline"
            b["apify_run_id"] = b["apify_run_id"] or "imported_offline"
            updated_count += 1
              
    if updated_count > 0:
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)
        console.print(f"[green]Manifest status updated for {updated_count} batches found on disk.[/green]")
    else:
        console.print("[yellow]No pending batches matched files on disk.[/yellow]")

@app.command(name="process-reviews")
def process_reviews():
    """
    Task 6-9: Process raw reviews, map to canonicals, deduplicate, select representative reviews, and compile reports.
    """
    from src.enrichment.review_processor import process_and_select_reviews
    console.print("[bold blue]Starting review processing and selection pipeline...[/bold blue]")
    try:
        process_and_select_reviews()
        console.print("[green]Processing completed successfully. Output files saved in data/enrichment/final/ and reports in reports/.[/green]")
    except Exception as e:
        console.print(f"[red]Error during review processing: {e}[/red]")
        raise e

@app.command(name="recover-review-run")
def recover_review_run(
    mode: str = typer.Option(..., help="Mode: positive, negative, neutral"),
    batch: str = typer.Option(..., help="Batch ID, e.g. batch_001"),
    run_id: str = typer.Option(..., help="Apify Run ID")
):
    """
    Task 2: Recover a single existing successful run from Apify without triggering a new Actor run.
    """
    import hashlib
    from dotenv import load_dotenv
    load_dotenv()
    token = os.getenv("APIFY_TOKEN")
    if not token or str(token).strip() == "":
        console.print("[red]APIFY_TOKEN is missing in .env. Cannot perform recovery.[/red]")
        return
        
    try:
        from apify_client import ApifyClient
    except ImportError:
        console.print("[red]apify-client library is not installed. Please run 'pip install apify-client' to use this command.[/red]")
        return

    manifest_path = "data/enrichment/apify_review_inputs/review_batch_manifest.json"
    if not os.path.exists(manifest_path):
        console.print("[red]Manifest file not found. Please run prepare-review-scraping first.[/red]")
        return
        
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)
        
    entry = None
    for b in manifest_data.get("batches", []):
        if b["batch_id"] == batch and b["mode"] == mode:
            entry = b
            break
            
    if not entry:
        console.print(f"[red]Batch {batch} ({mode}) not found in manifest.[/red]")
        return

    raw_dir = os.path.join("data/enrichment/raw_reviews", mode)
    os.makedirs(raw_dir, exist_ok=True)
    raw_path = os.path.join(raw_dir, f"{batch}.json")

    # Idempotency check:
    if entry.get("status") == "completed" and entry.get("apify_run_id") == run_id and os.path.exists(raw_path):
        with open(raw_path, "r", encoding="utf-8") as rf:
            try:
                existing_items = json.load(rf)
                existing_checksum = hashlib.sha256(json.dumps(existing_items, sort_keys=True).encode("utf-8")).hexdigest()
                if existing_checksum == entry.get("result_checksum"):
                    console.print(f"[green]Batch {batch} ({mode}) run {run_id} already recovered and verified. Skipping.[/green]")
                    return
            except Exception:
                pass

    console.print(f"[blue]Recovering run {run_id} for {batch} ({mode})...[/blue]")
    client = ApifyClient(token)
    
    try:
        run = client.run(run_id).get()
    except Exception as e:
        console.print(f"[red]Failed to retrieve run details for {run_id}: {e}[/red]")
        raise e
        
    status = get_run_value(run, "status")
    if status != "SUCCEEDED":
        console.print(f"[red]Run {run_id} status is {status}, expected SUCCEEDED. Cannot recover.[/red]")
        return

    dataset_id = get_run_value(run, "default_dataset_id", "defaultDatasetId")
    console.print(f"[green]Run SUCCEEDED. Dataset ID: {dataset_id}. Downloading items...[/green]")
    
    try:
        items = client.dataset(dataset_id).list_items().items
    except Exception as e:
        console.print(f"[red]Failed to download dataset items: {e}[/red]")
        raise e
        
    raw_review_count = len(items)
    checksum = hashlib.sha256(json.dumps(items, sort_keys=True).encode("utf-8")).hexdigest()
    
    with open(raw_path, "w", encoding="utf-8") as rf:
        json.dump(items, rf, indent=2)
        
    entry["status"] = "completed"
    entry["apify_run_id"] = run_id
    entry["dataset_id"] = dataset_id
    entry["raw_review_count"] = raw_review_count
    entry["result_checksum"] = checksum
    
    from datetime import datetime, timezone
    entry["completed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
        
    console.print(f"[green]Successfully recovered {raw_review_count} reviews to {raw_path}. Manifest updated.[/green]")

@app.command(name="recover-review-batch")
def recover_review_batch(
    batch: str = typer.Option(..., help="Batch ID, e.g. batch_001")
):
    """
    Task 2: Recover all three modes of a batch using pre-existing runs.
    """
    if batch != "batch_001":
        console.print(f"[red]Only batch_001 is supported for recovery mapping in this command.[/red]")
        return
        
    runs = {
        "positive": "MVrGztxpiTCIXSLsH",
        "negative": "0VCtRHHFadp9JudlV",
        "neutral": "z4UYRSzMdTivVyRD5"
    }
    
    console.print(f"[bold blue]Recovering batch {batch}...[/bold blue]")
    for mode, run_id in runs.items():
        try:
            recover_review_run(mode=mode, batch=batch, run_id=run_id)
        except Exception as e:
            console.print(f"[red]Failed to recover {mode} run {run_id}: {e}[/red]")
            raise e

if __name__ == "__main__":
    app()
