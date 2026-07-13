# Data Reconciliation & Quality Audit Report

Generated on: 2026-07-13 13:53:53 UTC

## 1. Executive Summary

This report displays the results of running the multi-dataset importer, normalizer, and deduplicator pipeline on tourism attractions.

| Metric | Count | Percentage | Description |
| :--- | :---: | :---: | :--- |
| **OSM Raw Records** | 330 | 6.78% | Raw places collected via OSM Overpass API |
| **Apify Raw Records** | 4539 | 93.22% | Raw places imported from Google Maps Apify export |
| **Total Input Records** | **4869** | **100.0%** | **Combined Raw inputs** |
| | | | |
| **Total Normalized (Inputs to Dedup)** | **4207** | **86.4%** | **Accepted + Manual Review records** |
| **Total Discarded/Rejected** | **500** | **10.27%** | **Classified as rejected** |
| **Duplicate Source Records Removed** | **162** | **3.33%** | **Duplicate source_record_ids removed** |
| | | | |
| **Verified Canonical Attractions** | 3130 | 74.92% | attractions_master_verified |
| **Manual Review Candidates** | 1048 | 25.08% | attractions_candidates |
| **Total Canonical Places** | **4178** | **100.0%** | **Deduplicated attraction locations** |
| **Duplicates Merged** | **29** | **0.69%** | **Merged source records** |

---

## 2. Leak-Free Reconciliation Math

* **Total Inputs**: `330 (OSM Raw) + 4539 (Apify Raw) = 4869`
* **Reconciliation Equation**:
  `Total Raw Inputs (4869) = Total Normalized (4207) + Total Rejected/Discarded (500) + Duplicate Source Records (162)`
  Verification: `4207 + 500 + 162 = 4869` (Match: YES)
* **Deduplication Equation**:
  `Total Normalized (4207) = Total Canonical (4178) + Duplicates Merged (29)`
  Verification: `4178 + 29 = 4207` (Match: YES)

---

## 3. Per-Region Breakdown

Below are the raw input and classification breakdown counts for each region:

| Region | Raw Records | Accepted | Manual Review | Rejected |
| :--- | :---: | :---: | :---: | :---: |
| **Kabupaten Lampung Barat** | 323 | 233 | 68 | 22 |
| **Kabupaten Lampung Selatan** | 544 | 377 | 131 | 36 |
| **Kabupaten Lampung Tengah** | 337 | 205 | 95 | 37 |
| **Kabupaten Lampung Timur** | 359 | 206 | 105 | 48 |
| **Kabupaten Lampung Utara** | 242 | 163 | 65 | 14 |
| **Kabupaten Mesuji** | 110 | 65 | 36 | 9 |
| **Kabupaten Pesawaran** | 358 | 280 | 47 | 31 |
| **Kabupaten Pesisir Barat** | 137 | 89 | 24 | 24 |
| **Kabupaten Pringsewu** | 255 | 169 | 65 | 21 |
| **Kabupaten Tanggamus** | 435 | 333 | 83 | 19 |
| **Kabupaten Tulang Bawang** | 184 | 123 | 55 | 6 |
| **Kabupaten Tulang Bawang Barat** | 141 | 108 | 31 | 2 |
| **Kabupaten Way Kanan** | 218 | 156 | 56 | 6 |
| **Kota Bandar Lampung** | 913 | 465 | 239 | 209 |
| **Kota Metro** | 151 | 87 | 48 | 16 |

---

## 4. Per-File Breakdown

Below are the metrics showing the source raw file mapping details:

| File Path | Region / Target | Raw Count | Accepted | Manual Review | Rejected |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `places.json` | Kabupaten Pesawaran | 369 | 287 | 47 | 35 |
| `places.json` | Kabupaten Tanggamus | 431 | 324 | 88 | 19 |
| `places.json` | Kota Bandar Lampung | 882 | 451 | 222 | 209 |
| `places.json` | Kabupaten Lampung Barat | 255 | 191 | 47 | 17 |
| `places.json` | Kabupaten Lampung Selatan | 492 | 357 | 102 | 33 |
| `places.json` | Kabupaten Lampung Tengah | 314 | 195 | 83 | 36 |
| `places.json` | Kabupaten Lampung Timur | 364 | 210 | 105 | 49 |
| `places.json` | Kabupaten Lampung Utara | 241 | 169 | 58 | 14 |
| `places.json` | Kabupaten Mesuji | 108 | 63 | 36 | 9 |
| `places.json` | Kota Metro | 139 | 79 | 44 | 16 |
| `places.json` | Kabupaten Pesisir Barat | 177 | 124 | 25 | 28 |
| `places.json` | Kabupaten Pringsewu | 243 | 164 | 60 | 19 |
| `places.json` | Kabupaten Tulang Bawang | 162 | 110 | 46 | 6 |
| `places.json` | Kabupaten Tulang Bawang Barat | 146 | 112 | 32 | 2 |
| `places.json` | Kabupaten Way Kanan | 215 | 156 | 53 | 6 |
| `response.json` | Kota Bandar Lampung | 29 | 12 | 16 | 1 |
| `response.json` | Kabupaten Lampung Barat | 30 | 15 | 15 | 0 |
| `response.json` | Kabupaten Lampung Selatan | 42 | 16 | 26 | 0 |
| `response.json` | Kabupaten Lampung Tengah | 14 | 6 | 8 | 0 |
| `response.json` | Kabupaten Lampung Utara | 7 | 0 | 7 | 0 |
| `response.json` | Kabupaten Mesuji | 2 | 1 | 1 | 0 |
| `response.json` | Kota Metro | 11 | 5 | 6 | 0 |
| `response.json` | Kabupaten Pesawaran | 2 | 0 | 2 | 0 |
| `response.json` | Kabupaten Pesisir Barat | 5 | 1 | 3 | 1 |
| `response.json` | Kabupaten Tanggamus | 7 | 3 | 4 | 0 |
| `response.json` | Kabupaten Tulang Bawang | 14 | 6 | 8 | 0 |
| `response.json` | Kabupaten Tulang Bawang Barat | 2 | 2 | 0 | 0 |
| `response.json` | Kabupaten Way Kanan | 4 | 0 | 4 | 0 |

---

## 5. Cross-Source Deduplication & Matches
- **Matches (Apify & OSM Merged)**: 23
- **Apify-only Canonical Attractions**: 4017
- **OSM-only Canonical Attractions**: 138
- **Parent-Child candidates linked**: 112
