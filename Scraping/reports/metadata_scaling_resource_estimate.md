# Metadata Scaling Resource Estimate

## Processing Metrics
- **Total Attractions**: 3130
- **Already Mapped (Pilot)**: 271
- **To Be Mapped (New)**: 2859
- **Total Batches**: 32
- **Batch Size**: 100 records (Batch 32 has 30 records)

## Resource Requirements
- **External Network Requests**: 0 requests (Data is processed locally using raw scraped source files under `data/processed/apify/` and `data/normalized/all_normalized.parquet`).
- **CPU Time Estimate**: ~30-45 seconds total execution time (~1.2 seconds per batch of 100).
- **RAM Usage**: ~150-250 MB peak memory for pandas DataFrames loading.
- **Disk Space usage**: ~5 MB for normalized metadata CSV/Parquet files and relation outputs.
- **API Call Cost**: $0.00 (Purely local execution, no external paid API calls required).

## Execution Schedule
The execution will be processed sequentially starting from `batch_001` through `batch_032`.
The resume logic in the manifest will track the status of each batch to ensure recovery in case of interruption.
