# Product Requirements Document (PRD)
# Recommendation Traveller Lampung

| Informasi Metadata | Keterangan |
| :--- | :--- |
| **Nama Produk** | Recommendation Traveller Lampung |
| **Jenis Produk** | Sistem Rekomendasi Destinasi Wisata Terstruktur |
| **Versi Dokumen** | 1.0 (Baseline Clean-Room) |
| **Status Dokumen** | Active Baseline |
| **Tanggal** | 29 Juli 2026 |
| **Cakupan Wilayah** | Provinsi Lampung (15 Kabupaten/Kota) |
| **Fase Aktif** | Data Engineering & Recommender-Ready Dataset Scaling |
| **Release Data Terakhir** | `consolidated-enrichment-master-full-v1` (Commit: `0a228ea4151c34349d0f54e8701b759db7ba160e`) |
| **Fokus Utama** | Consolidating Data Pipeline, Feature Engineering & Recommendation ML Model |

---

## 1. Ringkasan Eksekutif

**Recommendation Traveller Lampung** adalah sistem rekomendasi destinasi wisata berbasis data terverifikasi yang dirancang untuk memberikan rekomendasi perjalanan yang terpersonalisasi, transparan, dan terukur. Sistem ini menghitung tingkat kecocokan tempat wisata berdasarkan preferensi pengguna, fasilitas, jarak geografis, analisis sentimen ulasan, kondisi operasional, serta pertimbangan biaya.

Proyek ini dibangun dengan **pendekatan berbasis data (Data-First Approach)**. Informasi dari berbagai sumber (Google Maps, OpenStreetMap, Ulasan Publik, Sumber Lokal) dikumpulkan, dibersihkan, dideduplikasi, dipetakan ke identitas *canonical*, diperkaya dengan metadata, dan dikonsolidasi ke dalam *Consolidated Enrichment Master Dataset*.

### Status Population Dataset Terverifikasi (`consolidated-enrichment-master-full-v1`):
- **3.130** destinasi wisata terverifikasi (*verified canonical attractions*).
- **3.130** `canonical_id` unik (Zero Duplicate & Zero Join Explosion).
- **99** kolom fitur terstruktur pada master dataset.
- **2.992** tempat wisata dengan metadata terpetakan (*mapped*).
- **172** tempat wisata dengan data ulasan publik terolah.
- **1.141** tempat wisata dengan data jam operasional terstruktur.
- **2.445** tempat wisata dengan data fasilitas teridentifikasi.
- **8** tempat wisata dengan bukti data harga lokal.
- **11** tempat wisata dengan cakupan verifikasi harga eksternal.

Fokus fase berjalan saat ini adalah transformasi *Consolidated Master Dataset* menjadi *Recommender-Ready Dataset*, dilanjutkan dengan pengembangan model *Content-Based Recommendation Engine* dan *Sentiment Analysis Model* untuk teks ulasan pengguna.

---

## 2. Latar Belakang & Permasalahan

### 2.1 Latar Belakang
Provinsi Lampung memiliki potensi pariwisata yang kaya (pantai, pulau, air terjun, taman nasional, wisata budaya, dan rekreasi keluarga). Namun, informasi destinasi wisata masih tersebar di berbagai platform (Google Maps, media sosial, blog, situs pemerintah, marketplace). Setiap sumber menyajikan informasi dengan format, kelengkapan, dan keandalan yang bervariasi.

### 2.2 Permasalahan Utama
1. **Informasi Terfragmentasi & Tersebar**: Data wisata belum terintegrasi dalam satu skema yang terstandarisasi.
2. **Duplikasi Data Tempat Wisata**: Tempat yang sama muncul berulang kali dengan variasi nama, alamat, atau koordinat yang berbeda.
3. **Metadata Tidak Lengkap & Inkonsisten**: Banyak tempat tidak memiliki data jam operasional, nomor kontak, aksesibilitas, atau daftar fasilitas yang pasti.
4. **Verifikasi Harga yang Rumit**: Informasi harga berasal dari ulasan lama, caption media sosial, atau blog yang tidak dapat dipastikan keakuratannya (*unverified / historical*).
5. **Ulasan Publik Belum Terstruktur**: Teks ulasan mengandung *insight* penting mengenai kebersihan, pelayanan, dan akses jalan, namun belum diolah menjadi skor sentimen numerik terukur.
6. **Rekomendasi Bersifat Generik & Tanpa Transparansi**: Sistem pencarian umumnya hanya menampilkan tempat populer tanpa menyesuaikan preferensi individual dan tanpa memberikan alasan rekomendasi (*explainability*).
7. **Risiko Misinterpretasi Data**:
   - Harga tidak tersedia sering disalahartikan sebagai *gratis (free)*.
   - Jam buka tidak tercatat sering disalahartikan sebagai *tutup*.
   - Tidak ada ulasan disalahartikan sebagai tempat wisata *berkualitas buruk*.

---

## 3. Visi & Tujuan Produk

### 3.1 Visi Produk
Membangun fondasi data pariwisata terstruktur dan mesin rekomendasi berbasis *Machine Learning* yang akurat, transparan, serta dapat diandalkan untuk destinasi wisata di Provinsi Lampung.

### 3.2 Tujuan Utama (Fase Data & ML)
1. **Pembangunan Recommender-Ready Dataset**: Menyusun matriks fitur terstandarisasi (vektor numerik & kategorikal) dari 3.130 *canonical attractions*.
2. **Pengembangan Content-Based Recommendation Engine**: Membangun algoritma rekomendasi baseline yang menghitung *cosine similarity* dan *weighted score* antara profil pengguna dan profil tempat wisata.
3. **Pengembangan Model Analisis Sentimen NLP**: Mengklasifikasikan teks ulasan pengunjung ke dalam sentimen Positif, Netral, dan Negatif untuk memperkaya bobot kualitas tempat.
4. **Implementasi Explainable Recommendation**: Menghasilkan *reason codes* pada setiap output rekomendasi untuk memberikan transparansi kepada pengguna.
5. **Penegakan Tata Kelola Data (Data Governance)**: Memastikan penanganan *Semantic Null*, preservasi *provenance*, serta pencegahan *data leakage* dan duplikasi secara ketat.

### 3.3 Prinsip Rekayasa: Anti-AI Slop & Critical Realism
1. **Zero AI Slop**: Seluruh kode, dokumen arsitektur, dan pelaporan wajib ditulis secara padat, berbasis bukti teknis empiris, tanpa kalimat basa-basi, filler, klaim hiperbolis, atau implementasi palsu/mocking yang menyamarkan kegagalan.
2. **Critical Realism & Anti-Sycophancy**: AI Agent dan pengembang **WAJIB berani berkata TIDAK** atau membantah arahan yang secara teknis tidak realistis, melanggar determinisme data, atau berisiko tinggi merusak kualitas sistem. Kejujuran teknis dan kebenaran realistis harus selalu diprioritaskan dibanding persetujuan pasif.

---

## 4. Ruang Lingkup Proyek (Project Scope)

### 4.1 Dalam Ruang Lingkup (In-Scope)
- **Data Engineering & Governance**:
  - Ingesti, pembersihan, deduplikasi, dan *canonicalization* data 3.130 tempat wisata di 15 Kabupaten/Kota Lampung.
  - Penegakan *Semantic Nulls* (`observed`, `inferred`, `missing`, `unknown`, `false`, `zero`, `not_applicable`, `unresolved`).
  - Pembuatan *Recommender-Ready Dataset* (vektor fitur kategorikal, spasial, fasilitas, harga, dan sentimen).
- **Machine Learning & Analytics**:
  - *Content-Based Filtering Recommendation Engine* (Cosine similarity, weighted scoring, geospatial distance decay).
  - *Cold-Start Handler* untuk pengguna baru tanpa riwayat interaksi.
  - *Sentiment Analysis Model* untuk ekstraksi opini dari teks ulasan.
  - Generasi *Explanation Engine / Reason Codes* (e.g., `category_match`, `facility_match`, `nearby_location`, `positive_sentiment`).
- **Model Serving & API Interface**:
  - RESTful API (FastAPI) untuk *serving model inference*, rekomendasi *top-N*, detail destinasi, dan pencarian spasial/fasilitas.
  - Penyiapan skema API contract yang siap dikonsumsi oleh service eksternal di masa depan.

### 4.2 Di Luar Ruang Lingkup Fase Ini (Out-of-Scope)
- Pengembangan antarmuka web / aplikasi frontend pengguna akhir.
- Sistem transaksi, pemesanan tiket, booking hotel, atau pembayaran digital.
- Model *Collaborative Filtering* berbasis riwayat transaksi pengguna berskala besar (dipertimbangkan setelah data interaksi terkumpul).
- Fitur *Dynamic Pricing* atau pembaruan harga tiket secara *real-time*.

---

## 5. Target Pengguna & Persona Usaha

| Persona Pengguna | Deskripsi & Kebutuhan Data/ML |
| :--- | :--- |
| **Wisatawan Berdasarkan Preferensi Aktivitas** | Membutuhkan rekomendasi destinasi yang cocok dengan kategori favorit (Pantai, Alam, Budaya, Rekreasi Keluarga) dan fasilitas spesifik. |
| **Wisatawan Berdasarkan Batasan Budget** | Membutuhkan kejelasan ketersediaan data harga tiket/parkir dan filter tempat wisata sesuai rentang biaya. |
| **Wisatawan Berbasis Lokasi (Terdekat)** | Membutuhkan rekomendasi tempat wisata dalam radius tertentu dari posisi koordinat saat ini (*geospatial proximity*). |
| **Data Engineer & ML Engineer (Internal)** | Membutuhkan dataset terverifikasi, pipeline yang *deterministic* dan *resumable*, serta API *contract* yang konsisten untuk evaluasi model. |

---

## 6. Tata Kelola & Spesifikasi Data

### 6.1 Arsitektur Layer Pengolahan Data
```
Raw Data Layer (Apify Google Maps, OpenStreetMap, Local Sources)
       │
       ▼
Normalized & Deduplicated Records
       │
       ▼
Canonical Attractions (3.130 Verified Places, Primary Key: canonical_id)
       │
       ▼
Enrichment Master (Metadata, Reviews, Opening Hours, Facilities, Prices)
       │
       ▼
Consolidated Enrichment Master Dataset (3.130 rows x 99 columns)
       │
       ▼
Recommender-Ready Dataset (Feature Matrix Vectorized for ML)
       │
       ├── Content-Based Recommendation Engine
       └── NLP Sentiment Analysis Model
```

### 6.2 Standar Identitas Canonical (`canonical_id`)
- Setiap tempat wisata memiliki tepat 1 (satu) **`canonical_id`** unik.
- `canonical_id` adalah *primary key* tunggal untuk semua relasi data (ulasan, jam buka, fasilitas, harga).
- **Aturan Relasi**: *Join* data berdasarkan nama tempat tanpa `canonical_id` dilarang keras.

### 6.3 Penegakan *Semantic Nulls*
Untuk mencegah misinterpretasi data pada model rekomendasi, sistem membedakan status *null* secara tegas:

| Status Semantic | Makna Operasional | Penanganan pada Model ML |
| :--- | :--- | :--- |
| `observed` | Data ditemukan dan terverifikasi dari sumber resmi. | Digunakan penuh pada vektor fitur. |
| `inferred` | Data diperoleh melalui aturan inferensi logis. | Digunakan dengan bobot konfidensi lebih rendah. |
| `missing` | Data tidak tersedia pada sumber data. | Ditampilkan sebagai keterbatasan data, tidak dihukum ekstrim. |
| `unknown` | Kondisi operasional/informasi tidak dapat dipastikan. | Diberi penalti kualitas (*quality penalty*). |
| `false` | Informasi secara eksplisit tidak ada / tidak tersedia. | Bernilai numerik `0` pada vektor fitur. |
| `zero` | Nilai numerik valid sebesar `0` (e.g., Tiket Masuk Rp 0 / Gratis). | Bernilai numerik `0.0` (Free). |
| `not_applicable` | Field tidak relevan untuk kategori destinasi tersebut. | Dikecualikan dari perhitungan skor. |
| `unresolved` | Bukti data tidak mencukupi untuk membuat keputusan. | Tidak dipromosikan ke status terverifikasi. |

### 6.4 Aturan Penanganan Data Harga (*Pricing Rules*)
1. Data harga *missing / unavailable* **TIDAK BOLEH** dianggap sebagai *Gratis (Rp 0)*.
2. Data harga *historis* tidak boleh dipromosikan sebagai *Verified Current*.
3. Biaya parkir atau sewa alat tidak boleh dikelirukan sebagai tiket masuk destinasi.
4. Status `completed_no_price` dan `completed_unresolved` wajib mempertahankan nilai min/max harga sebagai `NaN/null`.

---

## 7. Spesifikasi Recommender-Ready Dataset

*Recommender-Ready Dataset* adalah matriks fitur bernilai numerik dan kategorikal yang siap dikonsumsi langsung oleh *Recommendation Engine*.

### 7.1 Kelompok Fitur Utama

| Kelompok Fitur | Nama Fitur / Kolom | Tipe Data & Format |
| :--- | :--- | :--- |
| **Identitas & Spasial** | `canonical_id`, `latitude`, `longitude`, `region_code` | String, Float, One-Hot Vector |
| **Kategori Destinasi** | `primary_category`, `category_group` | Categorical / Multi-Hot Vector (21 Kategori) |
| **Wilayah Administrative** | `city_or_regency` | One-Hot Vector (15 Kabupaten/Kota) |
| **Fasilitas** | `has_parking`, `has_toilet`, `has_eatery`, `has_prayer_room`, `has_wheelchair_access`, `has_lodging` | Binary (0 / 1) |
| **Operasional** | `operational_status` (`open`, `temporarily_closed`, `permanently_closed`, `unknown`) | Categorical & Eligibility Mask |
| **Ulasan & Rating** | `review_coverage_status`, `review_count`, `rating_mean`, `rating_median` | Float & Status Code |
| **Sentimen Ulasan** | `sentiment_score_mean`, `sentiment_positive_ratio`, `sentiment_confidence` | Float (Range -1.0 s/d +1.0) |
| **Harga Tiket** | `price_status`, `price_min`, `price_max`, `is_free_verified` | Categorical, Float, Binary |
| **Kualitas Data** | `overall_completeness_score`, `quality_warning_count`, `identity_confidence` | Float (0 - 100), Integer, Float |

### 7.2 Aturan Eligibility Rekomendasi
Tempat wisata dianggap **Eligible** masuk ke dalam perhitungan rekomendasi jika:
1. Berstatus `verified canonical attraction`.
2. **TIDAK** berstatus `permanently_closed`.
3. Memiliki koordinat geografis yang valid (apabila menggunakan filter jarak).

*Catatan*: Tempat wisata **tidak boleh digugurkan** hanya karena belum memiliki data ulasan atau data harga. Tempat tersebut tetap memenuhi syarat rekomendasi dengan penyesuaian bobot kelengkapan data.

---

## 8. Spesifikasi Model Rekomendasi (*Content-Based Engine*)

### 8.1 Pendekatan Model
Menggunakan **Content-Based Filtering** berbasis perkalian bobot kecocokan fitur (*weighted feature compatibility*) dan *Cosine Similarity* antara Vektor Preferensi Pengguna ($U$) dan Vektor Fitur Destinasi ($I$).

### 8.2 Perumusan Skor Rekomendasi ($Score_{final}$)

$$Score_{final} = \sum (w_i \cdot Score_i) - Penalty_{quality}$$

Dimana komponen skor meliputi:
- **$Score_{category}$**: Kecocokan kategori wisata pilihan pengguna.
- **$Score_{region}$**: Kesesuaian kabupaten/kota tujuan.
- **$Score_{facility}$**: Jaccard similarity antara fasilitas yang diminta vs fasilitas yang tersedia.
- **$Score_{distance}$**: Function decay berdasarkan jarak geografis (Haversine/Geodesic distance).
- **$Score_{review\_sentiment}$**: Gabungan rating terintegrasi dengan skor sentimen ulasan.
- **$Score_{price}$**: Kesesuaian batas *budget* pengguna terhadap rentang harga destinasi.
- **$Penalty_{quality}$**: Penalti bagi destinasi dengan *operational_status = unknown* atau *identity_confidence* rendah.

### 8.3 Penanganan *Cold-Start*
Bagi pengguna baru tanpa riwayat preferensi eksplisit:
1. Pengguna wajib memasukkan minimal 1 preferensi (Kategori, Wilayah, atau Lokasi Terdekat).
2. Jika tidak ada preferensi yang diinput, sistem memberikan rekomendasi berbasis destinasi dengan *overall_completeness_score* tinggi dan rating/sentimen terbaik di wilayah terpilih.

### 8.4 Transparansi Rekomendasi (*Explainability Engine*)
Setiap output rekomendasi wajib dilengkapi dengan daftar *Reason Codes*:
- `category_match`: Kategori destinasi sesuai dengan minat pengguna.
- `region_match`: Destinasi berada di kabupaten/kota pilihan.
- `facility_match`: Memiliki fasilitas utama yang diminta (e.g., Toilet, Parkir).
- `nearby_location`: Berada dalam radius lokasi pengguna.
- `positive_sentiment`: Memiliki ulasan dengan sentimen positif tinggi.
- `verified_operational`: Jam operasional dan status tempat terverifikasi aktif.

---

## 9. Spesifikasi Model Analisis Sentimen (NLP)

### 9.1 Tujuan Model
Mengolah teks ulasan publik pengunjung destinasi wisata untuk menghasilkan skor sentimen numerik terstandarisasi sebagai fitur input tambahan bagi *Recommendation Engine*.

### 9.2 Pipeline Pengolahan Teks (NLP Pipeline)
1. **Preprocessing**: Case folding, penghapusan karakter khusus/emoji, penghapusan duplikasi ulasan.
2. **Text Normalization**: Normalisasi kata tidak baku / singkatan bahasa ulasan wisata lokal.
3. **Sentiment Classification**: Klasifikasi ke dalam 3 kelas: `positive`, `neutral`, `negative`.
4. **Aggregation**: Penghitungan *sentiment score* agregat per destinasi wisata.

### 9.3 Evaluasi & Metrik Keberhasilan Model Sentimen
- **Model Baseline**: TF-IDF + Logistic Regression / SVM.
- **Model Advanced**: Fine-tuned Transformer Bahasa Indonesia (IndoBERT / Multilingual).
- **Target Performa**: Macro $F1\text{-}Score \ge 0.75$ pada dataset pengujian ulasan terverifikasi.

---

## 10. Kebutuhan Fungsional & Non-Fungsional

### 10.1 Kebutuhan Fungsional (Functional Requirements)

| ID | Deskripsi Kebutuhan |
| :--- | :--- |
| **FR-001** | Sistem wajib menyimpan 1 (satu) record terverifikasi per tempat wisata dengan `canonical_id` unik. |
| **FR-002** | Sistem wajib menyediakan transformasi *Consolidated Master* ke *Recommender-Ready Feature Matrix*. |
| **FR-003** | Model wajib mengecualikan tempat wisata berstatus `permanently_closed` dari hasil rekomendasi. |
| **FR-004** | Model rekomendasi wajib menerima input vektor preferensi pengguna (Kategori, Wilayah, Fasilitas, Jarak, Budget). |
| **FR-005** | Model rekomendasi wajib menghitung skor *Content-Based Compatibility* dan menghasilkan *Top-N Recommendation*. |
| **FR-006** | Sistem rekomendasi wajib menyertakan minimal 1 *Reason Code* (*explainability*) pada setiap item hasil rekomendasi. |
| **FR-007** | Model sentimen NLP wajib mengekstraksi kelas sentimen dan probabilitas dari teks ulasan pengunjung. |
| **FR-008** | Sistem wajib memisahkan nilai `missing`, `unknown`, `false`, dan `zero` sesuai aturan *Semantic Null*. |
| **FR-009** | Model wajib menyediakan mekanisme *cold-start recommendation* untuk preferensi minimal. |
| **FR-010** | Sistem wajib menyediakan REST API (FastAPI) untuk inferensi model rekomendasi dan pencarian destinasi. |

### 10.2 Kebutuhan Non-Fungsional (Non-Functional Requirements)

| ID | Kategori | Spesifikasi Kebutuhan |
| :--- | :--- | :--- |
| **NFR-001** | **Determinisme** | Pengolahan feature matrix dan evaluasi model dengan input yang sama wajib menghasilkan output yang identik (*Zero Drift*). |
| **NFR-002** | **Performa Inferensi** | Waktu komputasi rekomendasi *Top-N* dari 3.130 tempat wisata wajib $< 500\text{ ms}$ per request. |
| **NFR-003** | **Reproduosibilitas** | Setiap eksekusi model wajib mencatat versi dataset (*dataset_version*) dan versi model (*model_version*). |
| **NFR-004** | **Integritas Data** | *Frozen Dataset* (`attractions_enrichment_master_full.parquet`) tidak boleh diubah secara langsung oleh proses pelatihan model. |
| **NFR-005** | **Modularitas** | Kode pipeline data, feature engineering, pelatihan model ML, dan API endpoint harus terpisah secara independen. |

---

## 11. Spesifikasi Model Serving API (FastAPI REST Contracts)

### 11.1 Endpoint Rekomendasi Destinasi
- **URL**: `POST /api/v1/recommendations`
- **Request Body**:
```json
{
  "categories": ["pantai", "alam"],
  "regions": ["Kabupaten Pesawaran"],
  "latitude": -5.45,
  "longitude": 105.25,
  "max_distance_km": 50,
  "budget_max": 50000,
  "required_facilities": ["parking", "toilet"],
  "limit": 10
}
```
- **Response Body**:
```json
{
  "dataset_version": "consolidated-enrichment-master-full-v1",
  "model_version": "content-based-v1.0",
  "total_items": 10,
  "items": [
    {
      "canonical_id": "can_00055c1c8161",
      "name": "Pantai Sari Ringging",
      "city_or_regency": "Kabupaten Pesawaran",
      "score": 0.892,
      "distance_km": 14.2,
      "price_status": "observed",
      "operational_status": "open",
      "reasons": [
        "category_match",
        "region_match",
        "facility_match",
        "nearby_location"
      ]
    }
  ]
}
```

### 11.2 Endpoint Detail Destinasi & Nearby
- `GET /api/v1/attractions/{canonical_id}`: Mengembalikan metadata lengkap dan fitur destinasi.
- `GET /api/v1/attractions/{canonical_id}/nearby`: Mengembalikan daftar tempat wisata terdekat berdasarkan koordinat spasial.

---

## 12. Indikator Keberhasilan (KPI & Quality Gates)

### 12.1 Kualitas Data Pipeline (Data Quality Gates)
- **Canonical ID Uniqueness**: 100% (3.130 / 3.130 baris).
- **Duplicate Rate**: 0.0%.
- **Critical Orphan Rate**: 0.0%.
- **Semantic Violation Count**: 0.

### 12.2 Evaluasi Model Rekomendasi
- **Precision@K & Recall@K**: Pengujian ketercapaian preferensi pada *Top-5* dan *Top-10*.
- **Catalog Coverage**: Persentase destinasi dalam katalog yang pernah direkomendasikan.
- **Explainability Coverage**: 100% item hasil rekomendasi memiliki *reason codes*.

### 12.3 Evaluasi Model Sentimen
- **Macro F1-Score**: $\ge 0.75$ pada dataset ulasan pengujian.
- **Confidence Thresholding**: Ulasan dengan konfidensi rendah ditandai sebagai *uncertain*.

---

## 13. Manajemen Risiko & Mitigasi

| Identifikasi Risiko | Tingkat Risiko | Strategi Mitigasi |
| :--- | :--- | :--- |
| **Misinterpretasi Harga Kosong** | Tinggi | Penegakan status `price_status = unavailable`, tidak dikonversi ke Rp 0. |
| **Dominasi Tempat Populer (Popularity Bias)** | Sedang | Penambahan variabel *diversity* dan pembobotan berbasis fitur spesifik daripada sekadar *review count*. |
| **Review Sparsity (Tempat Tanpa Ulasan)** | Sedang | Tempat tanpa ulasan tetap diikutsertakan dengan status `review_coverage_status = not_processed` dan tanpa skor sentimen palsu. |
| **Data Drift pada Sumber Eksternal** | Rendah | Menggunakan *Frozen Dataset* versi ter-tag (`consolidated-enrichment-master-full-v1`) untuk pelatihan model. |

---

## 14. Roadmap & Status Progres Proyek

| Fase | Deskripsi / Sub-Task | Status |
| :--- | :--- | :--- |
| **Fase 1: Data Discovery & Canonicalization** | Verifikasi 3.130 tempat wisata di 15 Kabupaten/Kota | **Selesai** (`discovery-v1-final`) |
| **Fase 2: Enrichment Scaling** | Scaling Metadata Backfill & Verified Price Verification | **Selesai** (`metadata-backfill-scaling-v1`) |
| **Fase 3: Consolidated Master Dataset** | Pembangunan 3.130 Full Consolidated Master Rows | **Selesai** (`consolidated-enrichment-master-full-v1`) |
| **Fase 4: Recommender-Ready Dataset** | Penyiapan Vektor Fitur & Matriks Kategori/Fasilitas/Spasial | **Fase Aktif** |
| **Fase 5: Content-Based Recommendation Model** | Implementasi Algoritma Similarity, Scoring & Reason Engine | **Berikutnya** |
| **Fase 6: Sentiment Analysis NLP Model** | Preprocessing Teks Ulasan, Training Model Sentimen & Agregasi | **Direncanakan** |
| **Fase 7: Offline Model Evaluation** | Pengujian Precision@K, Recall@K, Diversity & Reason Verification | **Backlog** |
| **Fase 8: Model Serving API (FastAPI)** | Pembangunan Endpoint Rekomendasi RESTful & Contract Testing | **Backlog** |

---

## 15. Glosarium

- **Canonical Attraction**: Identitas tunggal yang terverifikasi untuk satu tempat wisata fisik.
- **Canonical ID**: *Primary key* unik lintas seluruh sumber dan layer dataset.
- **Consolidated Enrichment Master**: Dataset utama gabungan dari seluruh layer enrichment (metadata, ulasan, jam operasional, fasilitas, dan harga).
- **Recommender-Ready Dataset**: Matriks fitur terstruktur yang disiapkan khusus untuk algoritma *Machine Learning*.
- **Semantic Null**: Aturan pemisahan makna nilai kosong (`observed`, `inferred`, `missing`, `unknown`, `false`, `zero`, `not_applicable`, `unresolved`).
- **Explainability / Reason Code**: Kode penjelas yang memberikan alasan logis mengapa suatu destinasi direkomendasikan kepada pengguna.

---

