# Software Requirements Specification (SRS)
# Recommendation Traveller Lampung

| Informasi Spesifikasi | Keterangan Teknis |
| :--- | :--- |
| **Nama Sistem** | System Engine Recommendation Traveller Lampung |
| **Tipe Perangkat Lunak** | Data Pipeline, ML Feature Matrix, Recommendation Engine & Model Serving API |
| **Versi Dokumen** | 1.0 (Baseline Architecture) |
| **Status Dokumen** | Active Engineering Specification |
| **Tanggal Terbit** | 29 Juli 2026 |
| **Fase Pengembangan** | Data Engineering Scaling & Recommender-Ready Feature Engineering |
| **Target Dataset Baseline** | `consolidated-enrichment-master-full-v1` (3.130 verified attractions) |
| **Lingkungan Eksekusi** | Python 3.13+, FastAPI, pandas, scikit-learn, PyArrow |

---

## 1. Pendahuluan & Gambaran Umum Sistem

### 1.1 Tujuan Dokumen
Dokumen **Software Requirements Specification (SRS)** ini mendefinisikan spesifikasi arsitektur teknis, aturan tata kelola data, skema matriks fitur, formulasi matematika model rekomendasi, pipeline NLP analisis sentimen, serta kontrak REST API untuk sistem **Recommendation Traveller Lampung**. Dokumen ini menjadi panduan eksekusi utama bagi Data Engineer, ML Engineer, dan AI Coding Agent.

### 1.2 Cakupan Sistem Teknis (Technical System Scope)
Sistem ini terdiri dari 4 komponen inti yang beroperasi secara independen dan terisolasi:
1. **Data Engineering & Cleansing Pipeline (`Scraping/src/`)**: Menangani ingesti data, deduplikasi spasial/nama, *canonicalization*, penegakan *semantic nulls*, dan pembangunan *Consolidated Enrichment Master Dataset*.
2. **Feature Engineering Engine (`Model/feature_engineering/`)**: Mengubah *Consolidated Master* (3.130 baris x 99 kolom) menjadi *Recommender-Ready Feature Matrix* bernilai numerik dan ter-vektorisasi.
3. **Recommendation & Sentiment Machine Learning Engine (`Model/recommender/` & `Model/sentiment/`)**:
   - Memproses algoritma *Content-Based Filtering* berbasis *Cosine Similarity*, *Weighted Scoring*, *Geodesic Distance Decay*, serta *Reason Code Generator*.
   - Memproses pipeline NLP untuk ekstraksi opini dan sentimen ulasan publik.
4. **Model Serving API (`Model/api/` / FastAPI)**: Menyediakan interface RESTful untuk serving hasil inferensi model rekomendasi dan pencarian destinasi.

### 1.3 Direktif Rekayasa: Zero AI Slop & Critical Realism
- **Penulisan Kode & Dokumentasi Tanpa Slop**: Dilarang menggunakan teks basa-basi, penjelasan mengambang, atau kode dummy yang menyamarkan kegagalan. Semua penulisan dokumen teknis dan kode wajib berorientasi pada fungsionalitas riil, efisiensi, dan kebenaran matematika/data.
- **Sikap Kritis & Anti-Sycophancy (Berani Berkata TIDAK)**: AI Agent dan tim pengembang diwajibkan bersikap kritis dan **WAJIB berkata TIDAK** apabila menerima instruksi atau asumsi yang secara teknis tidak realistis, merusak integritas data, atau melanggar determinisme sistem. Kebenaran teknis empiris harus selalu diprioritaskan di atas sekadar menyetujui permintaan pasif.

---

## 2. Arsitektur Repository & Komponen Modul

### 2.1 Arsitektur Direktori Repository
```
Recommendation-Traveller/             # Root Repository
├── .agents/                          # System & AI Agent Documentation
│   ├── README.md                     # Indeks Dokumen
│   ├── PRD.md                        # Product Requirements Document
│   └── SRS.md                        # Software Requirements Specification (File Ini)
├── Data/                             # Storage Artifact Dataset Terverifikasi
│   ├── canonical/                    # Data Verified Canonical Attractions (3.130 records)
│   ├── enrichment/                   # Layer Enrichment (Metadata, Reviews, Hours, Facilities, Prices)
│   └── consolidated/                 # Consolidated Master & Recommender-Ready Datasets
├── Scraping/                         # Production Data Engineering Module
│   ├── src/                          # Script Core ETL Pipeline (consolidated_master.py, metadata.py, etc.)
│   ├── reports/                      # Laporan Audit (Determinism, Semantic Nulls, Manifests)
│   └── tests/                        # Test Suites Pytest (201 Test Functions)
└── Model/                            # Machine Learning & API Module (Fase Berjalan)
    ├── feature_engineering/          # Vectorization & Feature Matrix Builders
    ├── recommender/                  # Content-Based Engine, Similarity Math & Reason Generator
    ├── sentiment/                    # NLP Preprocessing, Sentiment Models & Aggregators
    └── api/                          # FastAPI Serving Endpoints & Pydantic Contracts
```

### 2.2 Arsitektur Alur Data (Data Flow Diagram)
```
[Apify Google Maps / OpenStreetMap / Local Sources]
                       │ (Ingestion & Cleansing)
                       ▼
         [Canonical Attractions (3.130)] ── (Primary Key: canonical_id)
                       │ (Enrichment Consolidation)
                       ▼
   [Consolidated Enrichment Master Dataset] (3.130 rows x 99 columns)
                       │ (Feature Engineering Vectorization)
                       ▼
      [Recommender-Ready Dataset Matrix] (recommender_ready_features.parquet)
                       │
       ┌───────────────┴───────────────┐
       ▼                               ▼
[Content-Based Engine]       [NLP Sentiment Model]
 (Cosine Similarity,          (Text Preprocessing,
  Geodesic Decay,             Sentiment Probabilities,
  Reason Generator)           Sentiment Aggregator)
       │                               │
       └───────────────┬───────────────┘
                       ▼
          [FastAPI Serving Interface] (REST Endpoints)
```

---

## 3. Spesifikasi Data Engineering & Tata Kelola Data

### 3.1 Constraints Identitas Canonical (`canonical_id`)
1. **Primary Key Requirement**: Setiap destinasi fisik wajib memiliki 1 (satu) **`canonical_id`** unik (format: `can_[hash12]`).
2. **Uniqueness**: Jumlah `canonical_id` unik pada master dataset **WAJIB EXACT 3.130**.
3. **Relational Integrity**: Seluruh tabel relasi (`review_summary`, `opening_hours_normalized`, `facilities_normalized`, `local_price_evidence`, `external_price_status`) wajib terikat melalui `canonical_id`.
4. **Zero Join Explosion**: Penggabungan (*join*) data antar-tabel wajib memiliki rasio penggandaan baris (*row multiplier*) tepat $1,0$.

### 3.2 Penegakan State Machine *Semantic Nulls*
Sistem wajib membedakan status nilai kosong secara eksplisit pada level pipeline data dan fitur ML:

```
                  ┌──► observed (Data terverifikasi langsung dari sumber)
                  ├──► inferred (Data diperoleh dari inferensi logis)
                  ├──► missing (Data tidak tercatat pada sumber)
Input Attribute ──┼──► unknown (Kondisi fisik tempat tidak dapat dipastikan)
                  ├──► false (Fitur secara eksplisit tidak ada / 0)
                  ├──► zero (Nilai numerik valid Rp 0 / Gratis)
                  ├──► not_applicable (Field tidak relevan untuk kategori)
                  └──► unresolved (Bukti belum mencukupi untuk keputusan)
```

#### Aturan Penanganan Khusus:
- **Missing Price**: Attribute harga `NaN` **DILARANG HARUS** dikonversi menjadi `0.0` (Free). Status harga ditandai `price_status = unavailable`.
- **Missing Review**: Tempat tanpa ulasan ditandai `review_coverage_status = not_processed` dan `review_attempted = False`. Field rating wajib `NaN`.
- **Missing Opening Hours**: Jam buka yang tidak ada ditandai `opening_hours_status = unknown`, bukan `closed`.

---

## 4. Spesifikasi *Recommender-Ready Dataset* & Fitur ML

*Recommender-Ready Dataset* disimpan dalam format **Parquet** (`recommender_ready_features.parquet`) dengan skema fitur numerik dan kategorikal sebagai berikut:

### 4.1 Skema Kolom Matriks Fitur (Feature Matrix Schema)

| Nama Kolom Fitur | Tipe Data | Deskripsi & Format Transformasi |
| :--- | :--- | :--- |
| `canonical_id` | `String` | Primary Key Unik (3.130 rows). |
| `name` | `String` | Nama tempat wisata terverifikasi. |
| `latitude` | `Float64` | Koordinat Latitude (-6.0 s/d -3.5). |
| `longitude` | `Float64` | Koordinat Longitude (103.5 s/d 106.0). |
| `city_or_regency` | `String` | Kabupaten/Kota (15 Wilayah). |
| `region_vector` | `List[Float32]` | One-Hot Encoding Vektor Wilayah (15-dimensi). |
| `primary_category` | `String` | Kategori Utama (21 Kategori). |
| `category_vector` | `List[Float32]` | One-Hot Encoding Vektor Kategori (21-dimensi). |
| `facility_vector` | `List[Float32]` | Multi-Hot Binary Vector Fasilitas (10-dimensi: Parkir, Toilet, Eatery, Worship, Wheelchair, Guide, Lodging, Camping, Wifi, Transport). |
| `operational_status` | `String` | Status: `open`, `temporarily_closed`, `permanently_closed`, `unknown`. |
| `is_eligible_recommend` | `Boolean` | Flag kelayakan (`True` jika bukan `permanently_closed` & koordinat valid). |
| `review_coverage_status`| `String` | Status ulasan: `scraped`, `no_reviews`, `ineligible`, `not_processed`. |
| `rating_normalized` | `Float32` | Rating skala 0.0 - 1.0 (Skala asli 1-5 dinormalisasi; `NaN` jika `not_processed`). |
| `sentiment_score_mean`  | `Float32` | Rentang -1.0 (Negatif Sangat) s/d +1.0 (Positif Sangat). `NaN` jika tanpa review. |
| `sentiment_confidence`  | `Float32` | Tingkat konfidensi model sentimen (0.0 s/d 1.0). |
| `price_status` | `String` | Status: `verified_current`, `provisional`, `historical`, `unavailable`. |
| `price_min_idr` | `Float64` | Batas bawah harga tiket (IDR); `NaN` jika `unavailable`. |
| `price_max_idr` | `Float64` | Batas atas harga tiket (IDR); `NaN` jika `unavailable`. |
| `completeness_score` | `Float32` | Skor kelengkapan metadata (0.0 s/d 100.0). |
| `quality_warning_count` | `Int32` | Jumlah *quality warnings* pada destinasi. |

---

## 5. Spesifikasi Teknis Model Rekomendasi (*Content-Based Engine*)

### 5.1 Pembentukan Vektor Profil

#### 1. Vektor Profil Pengguna ($\vec{U}$)
Vektor yang dibentuk dari input preferensi pengguna pada request API:
$$\vec{U} = \left[ \vec{U}_{cat}, \vec{U}_{reg}, \vec{U}_{fac}, \text{Budget}_{max}, \text{Lat}_{user}, \text{Long}_{user} \right]$$

#### 2. Vektor Fitur Destinasi ($\vec{I}$)
Vektor fitur yang diambil dari *Recommender-Ready Dataset*:
$$\vec{I} = \left[ \vec{I}_{cat}, \vec{I}_{reg}, \vec{I}_{fac}, \text{Price}_{min}, \text{Lat}_{item}, \text{Long}_{item} \right]$$

### 5.2 Formulasi Matematika Perhitungan Skor Similarity

#### A. Similarity Kategori ($Sim_{cat}$)
Perhitungan kecocokan vektor kategori menggunakan Cosine Similarity:
$$Sim_{cat}(\vec{U}_{cat}, \vec{I}_{cat}) = \frac{\vec{U}_{cat} \cdot \vec{I}_{cat}}{\|\vec{U}_{cat}\| \|\vec{I}_{cat}\|}$$

#### B. Similarity Fasilitas ($Sim_{fac}$)
Perhitungan kecocokan fasilitas yang diminta menggunakan Jaccard Similarity:
$$Sim_{fac}(\vec{U}_{fac}, \vec{I}_{fac}) = \frac{|\vec{U}_{fac} \cap \vec{I}_{fac}|}{|\vec{U}_{fac} \cup \vec{I}_{fac}|}$$

#### C. Distance Decay Score ($Sim_{dist}$)
Perhitungan jarak geografis menggunakan formula Haversine/Geodesic ($d_{km}$), lalu di-decay menggunakan fungsi eksponensial:
$$d_{km} = 2R \cdot \arcsin\left(\sqrt{\sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta \lambda}{2}\right)}\right)$$

$$Sim_{dist}(d_{km}) = \exp\left(-\lambda \cdot \max(0, d_{km} - d_{threshold})\right)$$
*Dimana $R = 6371\text{ km}$, $\lambda = 0,015$, dan $d_{threshold} = 5\text{ km}$.*

#### D. Rating & Sentimen Score ($Sim_{opinion}$)
$$Sim_{opinion} = \begin{cases} 
0.5 \cdot rating\_norm + 0.5 \cdot \left(\frac{sentiment\_score + 1}{2}\right), & \text{jika ulasan diproses} \\
0.5, & \text{jika } review\_status = not\_processed
\end{cases}$$

#### E. Penalty Quality Score ($Penalty_{quality}$)
destinasi yang memiliki masalah kualitas data diberikan penalti proporsional:
$$Penalty_{quality} = \alpha \cdot (100 - completeness\_score) + \beta \cdot \mathbb{I}(status = unknown) + \gamma \cdot warning\_count$$
*Dimana $\alpha = 0,001$, $\beta = 0,1$, $\gamma = 0,02$.*

### 5.3 Formulasi Skor Akhir Rekomendasi ($Score_{final}$)

$$Score_{final} = w_1 \cdot Sim_{cat} + w_2 \cdot Sim_{reg} + w_3 \cdot Sim_{fac} + w_4 \cdot Sim_{dist} + w_5 \cdot Sim_{opinion} - Penalty_{quality}$$

*Konfigurasi Bobot Default (Configurable)*:
$w_1 = 0,35$, $w_2 = 0,20$, $w_3 = 0,15$, $w_4 = 0,15$, $w_5 = 0,15$.

### 5.4 Algoritma Penanganan *Cold-Start*
Bagi pengguna baru tanpa input preferensi lengkap:
1. **Fallback Level 1**: Jika pengguna hanya menentukan Wilayah, $w_{reg}$ dinaikkan menjadi $0.60$ dan tempat teratas diurutkan berdasarkan $completeness\_score$ dan $rating\_normalized$.
2. **Fallback Level 2**: Jika tidak ada input preferensi sama sekali, sistem mengembalikan destinasi dengan *overall_completeness_score* tertinggi yang berstatus `open` di seluruh Lampung.

### 5.5 Spesifikasi Logika *Explainability Engine* (*Reason Codes*)
Setiap item rekomendasi wajib menyertakan daftar `reasons` berdasarkan aturan ambang batas (*threshold*):

```python
reasons = []
if Sim_cat > 0.8: reasons.append("category_match")
if Sim_reg == 1.0: reasons.append("region_match")
if Sim_fac >= 0.5: reasons.append("facility_match")
if d_km <= 25.0: reasons.append("nearby_location")
if sentiment_score_mean > 0.3: reasons.append("positive_sentiment")
if operational_status == "open": reasons.append("verified_open")
if price_status == "verified_current": reasons.append("price_verified")
if completeness_score >= 85.0: reasons.append("high_data_quality")
```

---

## 6. Spesifikasi Teknis Model Analisis Sentimen (NLP)

### 6.1 Preprocessing Teks Ulasan
1. **Case Folding & Cleansing**: Mengubah teks ke huruf kecil (*lowercasing*), meremove URL, mention, emoji, dan karakter non-alphanumeric.
2. **Normalisasi Istilah Lokal**: Mengganti kata tidak baku / gaul ulasan wisata (e.g., `"bgt"` $\rightarrow$ `"banget"`, `"gokil"` $\rightarrow$ `"bagus"`, `"jlek"` $\rightarrow$ `"jelek"`).
3. **Stopword Removal**: Menghapus kata hubung tanpa menghilangkan kata negasi (e.g., kata `"tidak"`, `"bukan"`, `"kurang"` tetap dipertahankan).

### 6.2 Arsitektur Model & Evaluasi
- **Baseline Model**: Feature Extraction `TF-IDF` (ngram range 1-2) + Classifier `LogisticRegression` / `LinearSVC`.
- **Advanced Model**: Fine-tuned `IndoBERT` (`indobenchmark/indobert-base-p1`).
- **Kelas Output**: `positive` (label 2), `neutral` (label 1), `negative` (label 0).
- **Target Metrik Evaluation**: $\text{Macro } F1\text{-}Score \ge 0.75$ pada dataset ulasan terverifikasi.

---

## 7. Spesifikasi API Contracts (FastAPI Serving)

### 7.1 POST /api/v1/recommendations

#### Request Schema (JSON)
```json
{
  "categories": ["pantai", "alam"],
  "regions": ["Kabupaten Pesawaran"],
  "latitude": -5.45,
  "longitude": 105.25,
  "max_distance_km": 50.0,
  "budget_max_idr": 100000.0,
  "required_facilities": ["parking", "toilet"],
  "limit": 10
}
```

#### Response Schema (JSON - 200 OK)
```json
{
  "dataset_version": "consolidated-enrichment-master-full-v1",
  "model_version": "content-based-v1.0",
  "execution_time_ms": 42.18,
  "total_items": 10,
  "items": [
    {
      "canonical_id": "can_00055c1c8161",
      "name": "Pantai Sari Ringging",
      "city_or_regency": "Kabupaten Pesawaran",
      "primary_category": "pantai",
      "latitude": -5.5612,
      "longitude": 105.2631,
      "final_score": 0.8924,
      "distance_km": 14.23,
      "price_status": "unavailable",
      "price_min_idr": null,
      "price_max_idr": null,
      "operational_status": "open",
      "completeness_score": 92.5,
      "reasons": [
        "category_match",
        "region_match",
        "facility_match",
        "nearby_location",
        "verified_open"
      ]
    }
  ]
}
```

### 7.2 GET /api/v1/attractions/{canonical_id}

#### Response Schema (JSON - 200 OK)
```json
{
  "canonical_id": "can_00055c1c8161",
  "name": "Pantai Sari Ringging",
  "city_or_regency": "Kabupaten Pesawaran",
  "primary_category": "pantai",
  "latitude": -5.5612,
  "longitude": 105.2631,
  "address": "Jl. Way Ratai, Desa Sidodadi, Pesawaran",
  "phone": "+628123456789",
  "official_website": null,
  "operational_status": "open",
  "operational_confidence": 1.0,
  "opening_hours": {
    "is_open_24_hours": false,
    "status": "available"
  },
  "facilities": ["parking", "toilet", "eatery", "worship"],
  "review_summary": {
    "coverage_status": "scraped",
    "review_count": 142,
    "rating_mean": 4.5,
    "sentiment_score_mean": 0.78,
    "sentiment_confidence": 0.91
  },
  "price_summary": {
    "status": "unavailable",
    "min_price": null,
    "max_price": null
  },
  "quality": {
    "completeness_score": 92.5,
    "warning_count": 1,
    "warnings": ["external_price_not_verified"]
  }
}
```

### 7.3 Response Error Schema Standard (HTTP 400 / 422 / 500)
```json
{
  "error_code": "INVALID_INPUT_COORDINATES",
  "message": "Latitude must be between -6.0 and -3.5 for Lampung region.",
  "timestamp": "2026-07-29T06:10:00Z"
}
```

---

## 8. Kebutuhan Non-Fungsional & Quality Gates

### 8.1 Spesifikasi Determinisme (*Zero Drift Requirement*)
1. **Two-Run Determinism**: Eksekusi pengolahan matriks fitur dan inferensi model 2x berturut-turut pada dataset frozen yang sama **WAJIB MENGAHSILKAN HASH CHECKSUM CHECKSUM SAMA PARITAS**.
2. **Determinism Verification Script**: `python scratch/run_two_run_determinism.py` wajib menghasilkan `Matching: True`.

### 8.2 Spesifikasi Latensi Performa (*Performance Latency*)
- **Recommendation Inference Time**: Maximum $< 500\text{ ms}$ untuk memproses scoring 3.130 destinasi wisata per request.
- **Memory Footprint**: Memory usage $<< 2\text{ GB}$ RAM saat memuat matriks fitur 3.130 baris pada service FastAPI.

### 8.3 Quality Gates Automated Testing (Pytest)
Setiap rilis modul *Recommender* dan *API* wajib lolos seluruh test suite Pytest:
- **Scaling Tests**: `python -m pytest tests/test_consolidated_master_scaling.py` (14 Pass).
- **Full Suite**: `python -m pytest tests/ -v` (201 Pass, 0 Fail, 0 Skip).

---

## 9. Lingkungan Eksekusi & Dependensi Perangkat Lunak

```toml
[tool.poetry.dependencies]
python = "^3.13"
pandas = "^2.2.0"
numpy = "^1.26.0"
scipy = "^1.12.0"
scikit-learn = "^1.4.0"
pyarrow = "^15.0.0"
fastapi = "^0.110.0"
pydantic = "^2.6.0"
uvicorn = "^0.28.0"
pytest = "^8.0.0"
```

---

*Dokumen Software Requirements Specification (SRS) ini telah dibekukan sebagai standar acuan teknis eksekusi pengembangan modul Data Engineering, Feature Matrix, Recommendation ML Model, dan API Serving.*
