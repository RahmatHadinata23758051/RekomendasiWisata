# PowerShell script to run the Lampung Tourism Scraper Pipeline
$env:PYTHONIOENCODING="utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "==========================================" -ForegroundColor Green
Write-Host "Starting Lampung Tourism Data Collection Pipeline" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green

# 1. Discover all sources and import Apify data
Write-Host "`n[Step 1] Running Discovery & Importers..." -ForegroundColor Cyan

Write-Host "Running recursive Apify multi-file import..." -ForegroundColor Yellow
python -m src.cli import-apify-all --root "data/raw/apify/google_maps"

python -m src.cli discover --source all --resume

# 2. Normalize
Write-Host "`n[Step 2] Normalizing collected records..." -ForegroundColor Cyan
python -m src.cli normalize

# 3. Deduplicate & Merge
Write-Host "`n[Step 3] Running Deduplication & Enrichment..." -ForegroundColor Cyan
python -m src.cli deduplicate

# 4. Report
Write-Host "`n[Step 4] Generating Coverage & Data Quality Report..." -ForegroundColor Cyan
python -m src.cli report

Write-Host "`n==========================================" -ForegroundColor Green
Write-Host "Pipeline execution complete! Check reports/ for findings." -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
