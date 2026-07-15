# Metadata Scaling Manifest Audit Report

This report documents the validation of the scaled metadata manifest file: `data/enrichment/metadata/full/metadata_full_manifest.json`.

## Manifest Verification Matrix

| Metrics Dimension | Expected Value | Manifest Value | Verification Status |
| --- | --- | --- | --- |
| **Population Count** | 3,130 | 3,130 | Passed |
| **Output Row Count** | 3,130 | 3,130 | Passed |
| **Output Unique IDs** | 3,130 | 3,130 | Passed |
| **Mapping Mapped Count** | 2,992 | 2,992 | Passed |
| **Mapping Unmapped Count** | 138 | 138 | Passed |
| **Mapping Total Count** | 3,130 | 3,130 (2992 + 138) | Passed |
| **Addresses Relation Count** | 2,991 | 2,991 | Passed |
| **Phones Relation Count** | 752 | 752 | Passed |
| **Websites Relation Count** | 2,992 | 2,992 | Passed |
| **Opening Hours Relation Count** | 7,968 | 7,968 | Passed |
| **Facilities Relation Count** | 5,600 | 5,600 | Passed |
| **Integrity Status** | passed | passed | Passed |
| **Scaling Tests Passed** | 32 | 32 | Passed |

## Checksum Audits
- **Source Checksums**: Validated against baseline checksums with **zero drift** found on frozen inputs.
- **Output Checksums**: Matches exactly the SHA256 hashes of generated CSV, Parquet, and JSONL place metadata files.

## Summary Conclusion
The manifest file `metadata_full_manifest.json` is verified to be completely accurate, with zero discrepancies between physical files, row counts, and mapping distributions.
