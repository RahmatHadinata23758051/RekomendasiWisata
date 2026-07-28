# Cetak Biru Arsitektur Model & Rencana Pengujian Performa (Benchmark Plan)
# Recommendation Traveller Lampung

| Informasi Arsitektur | Keterangan Teknis |
| :--- | :--- |
| **Nama Dokumen** | Cetak Biru Arsitektur Model ML & Benchmarking Plan |
| **Modul Terkait** | `Model/` (`feature_engineering/`, `recommender/`, `sentiment/`, `api/`) |
| **Versi Spesifikasi** | 1.0 (Pre-Implementation Baseline Architecture) |
| **Status** | Approved Blueprint |
| **Tanggal** | 29 Juli 2026 |
| **Dataset Sumber** | `Data/consolidated/attractions_enrichment_master_full.parquet` (3.130 records) |
| **Fokus Utama** | Desain Dataset, Preprocessing, Algoritma Pembanding & Evaluasi Performa |

---

## 1. Pendahuluan & Filosofi Perancangan Arsitektur

Dokumen ini mendefinisikan **arsitektur teknis menyeluruh** untuk pengembangan *Machine Learning Engine* sistem **Recommendation Traveller Lampung** sebelum penulisan kode *training/inference* dilakukan. 

### Prinsip Utama Perancangan:
1. **Model-Agnostic & Multi-Algorithm Comparison**: Sistem dirancang agar dapat membandingkan beberapa pendekatan algoritma (*Baseline* vs *Candidate Models*) secara adil (*head-to-head benchmarking*) berdasarkan metrik performa objektif.
2. **Reproduosibilitas & Zero Data Leakage**: Seluruh pengolahan fitur menggunakan dataset terisolasi berbasis *frozen dataset* (`consolidated-enrichment-master-full-v1`) dengan *random seed* ter-lock.
3. **Pemisahan Modul Secara Ketat**: Preprocessing, Feature Matrix, Engine Rekomendasi, NLP Sentimen, dan Service API diisolasi pada direktori masing-masing untuk memudahkan pengujian.

---

## 2. Visualisasi Pipeline Arsitektur Sistem ML (End-to-End Diagram)

Berikut adalah diagram alur visualisasi sistem dari pengolahan dataset mentah hingga penyajian rekomendasi melalui REST API:

```mermaid
flowchart TD
    subgraph Data_Layer ["1. Layer Data & Feature Engineering"]
        A1["Input Frozen Master Dataset<br>attractions_enrichment_master_full.parquet<br>(3.130 rows x 99 cols)"] --> A2["Feature Matrix Builder<br>Model/feature_engineering/builder.py"]
        A2 --> A3["Vector Encoders<br>- One-Hot Category (21d)<br>- One-Hot Region (15d)<br>- Multi-Hot Facility (10d)<br>- Geodesic Distance Normalizer"]
        A3 --> A4[("Recommender-Ready Feature Matrix<br>recommender_ready_features.parquet")]
    end

    subgraph Sentiment_Layer ["2. Layer NLP Sentimen Ulasan"]
        B1["Raw Review Texts"] --> B2["NLP Text Preprocessor<br>- Cleansing & Lowercasing<br>- Indonesian Term Normalizer<br>- Negation Preserver"]
        B2 --> B3["Sentiment Classifiers<br>- Baseline 1: Lexicon VADER<br>- Baseline 2: TF-IDF + Logistic Reg<br>- Candidate 3: IndoBERT Fine-Tuned"]
        B3 --> B4["Sentiment Aggregator<br>- Score: -1.0 s/d +1.0<br>- Confidence Thresholding"]
        B4 --> A4
    end

    subgraph Recommendation_Layer ["3. Layer Engine Rekomendasi ML"]
        U1["User Request Preferences<br>(Category, Region, Facility, Budget, Lat/Long)"] --> C1["User Profile Vectorizer"]
        A4 --> C2["Item Feature Matrix Integrator"]
        C1 & C2 --> C3["Head-to-Head Algorithm Comparison Engine"]
        
        C3 --> C4a["Baseline 1:<br>Simple Cosine Similarity"]
        C3 --> C4b["Baseline 2:<br>Weighted Multi-Metric"]
        C3 --> C4c["Candidate 3:<br>TF-IDF + Quality Penalty"]
        C3 --> C4d["Candidate 4:<br>Hybrid Multi-Objective Engine"]

        C4d --> C5["Score Evaluator & Penalty Adjuster<br>- Geodesic Distance Decay<br>- Quality Penalty Adjustment"]
        C5 --> C6["Eligibility Filter<br>(Mask Permanently Closed)"]
        C6 --> C7["Cold-Start Handler<br>(Fallback Rules)"]
        C7 --> C8["Explainability Engine<br>(Reason Code Generator)"]
    end

    subgraph Serving_Layer ["4. Layer Model Serving API"]
        C8 --> D1["FastAPI Recommendation Server<br>POST /api/v1/recommendations"]
        D1 --> D2["JSON Response Payload<br>- Top-N Ranked Items<br>- Match Scores & Reason Codes<br>- Execution Latency (ms)"]
    end

    style A4 fill:#1f77b4,stroke:#333,stroke-width:2px,color:#fff
    style C4d fill:#2ca02c,stroke:#333,stroke-width:2px,color:#fff
    style D1 fill:#ff7f0e,stroke:#333,stroke-width:2px,color:#fff
```

---

## 3. Visualisasi Pipeline Feature Engineering & Vektorasi Fitur

Diagram berikut menggambarkan transformasi terperinci dari 99 kolom *Consolidated Master* menjadi matriks vektor numerik ML:

```mermaid
flowchart LR
    subgraph Master_Columns ["Columns Consolidated Master (99 Cols)"]
        M1["primary_category"]
        M2["city_or_regency"]
        M3["facilities_list"]
        M4["latitude & longitude"]
        M5["review_rating & sentiment"]
        M6["price_status & prices"]
        M7["completeness & warnings"]
    end

    subgraph Transformers ["Transformation & Encoding Modules"]
        T1["One-Hot Categorical Encoder"]
        T2["One-Hot Regional Encoder"]
        T3["Multi-Hot Binary Encoder"]
        T4["Geodesic Proximity Normalizer"]
        T5["Sentiment Integrator"]
        T6["Price Availability Encoder"]
        T7["Quality Penalty Calculator"]
    end

    subgraph Feature_Vectors ["Vectorized Feature Matrix (3.130 Rows)"]
        V1["category_vector (21d)"]
        V2["region_vector (15d)"]
        V3["facility_vector (10d)"]
        V4["spatial_coord_norm"]
        V5["sentiment_score_mean"]
        V6["price_status_flag"]
        V7["quality_penalty_score"]
    end

    M1 --> T1 --> V1
    M2 --> T2 --> V2
    M3 --> T3 --> V3
    M4 --> T4 --> V4
    M5 --> T5 --> V5
    M6 --> T6 --> V6
    M7 --> T7 --> V7

    style Feature_Vectors fill:#4b6584,stroke:#333,color:#fff
```

---

## 4. Visualisasi Algoritma Scoring & Explainability Engine

Diagram berikut menunjukkan bagaimana *Hybrid Multi-Objective Scoring Model* (Candidate 4) menghitung kecocokan destinasi dan meng-generate *Reason Codes*:

```mermaid
graph TD
    subgraph Similarity_Calculation ["Sub-Scoring Engine"]
        S1["Sim_category = Cosine(User_Cat, Item_Cat)"]
        S2["Sim_region = ExactMatch(User_Reg, Item_Reg)"]
        S3["Sim_facility = Jaccard(User_Fac, Item_Fac)"]
        S4["Sim_distance = exp(-λ * max(0, d_km - 5km))"]
        S5["Sim_opinion = 0.5 * Rating + 0.5 * Sentiment"]
    end

    subgraph Weighted_Sum ["Weighted Sum Integrator"]
        W1["Score_raw = (w1*Sim_cat + w2*Sim_reg + w3*Sim_fac + w4*Sim_dist + w5*Sim_opinion)"]
    end

    subgraph Penalty_System ["Quality Penalty Subsystem"]
        P1["Penalty = α*(100-Completeness) + β*Unknown_Status + γ*Warning_Count"]
    end

    subgraph Final_Scoring ["Final Decision Engine"]
        F1["Score_final = Score_raw - Penalty"]
    end

    subgraph Reason_Generator ["Explainability Engine (Reason Codes)"]
        R1{"Kriteria Ambang Batas Threshold"}
        R1 -->|Sim_cat > 0.8| RC1["category_match"]
        R1 -->|Sim_reg == 1.0| RC2["region_match"]
        R1 -->|Sim_fac >= 0.5| RC3["facility_match"]
        R1 -->|d_km <= 25km| RC4["nearby_location"]
        R1 -->|Sentiment > 0.3| RC5["positive_sentiment"]
        R1 -->|Status == open| RC6["verified_open"]
    end

    S1 & S2 & S3 & S4 & S5 --> W1
    W1 & P1 --> F1
    F1 --> R1

    style Final_Scoring fill:#eb3b5a,stroke:#333,color:#fff
    style Reason_Generator fill:#20bf6b,stroke:#333,color:#fff
```

---

## 5. Matriks Algoritma Rekomendasi yang Akan Dibandingkan (*Recommender Benchmarking*)

Untuk menentukan model rekomendasi terbaik, kita akan mengimplementasikan dan membandingkan **4 Algoritma Pembanding**:

| ID Algoritma | Nama Algoritma | Mekanisme & Formulir Matematika | Kelebihan & Alasan Pembandingan |
| :--- | :--- | :--- | :--- |
| **Baseline 1** | **Simple Cosine Similarity** | Membandingkan Vektor Profil Pengguna dan Vektor Fitur Destinasi menggunakan standard Cosine Similarity:<br>$$Sim(\vec{U}, \vec{I}) = \frac{\vec{U} \cdot \vec{I}}{\|\vec{U}\| \|\vec{I}\|}$$ | Algoritma dasar yang cepat dan sederhana sebagai *benchmark* minimal. |
| **Baseline 2** | **Weighted Multi-Metric Similarity** | Menggabungkan Cosine Similarity Kategori ($Sim_{cat}$), Jaccard Similarity Fasilitas ($Sim_{fac}$), dan One-Hot Region Matching ($Sim_{reg}$):<br>$$Score = w_1 Sim_{cat} + w_2 Sim_{reg} + w_3 Sim_{fac}$$ | Memisahkan perhitungan kategorikal dan biner untuk kecocokan fasilitas yang lebih presisi. |
| **Candidate 3** | **TF-IDF Feature Similarity + Quality Penalty** | Membentuk *textual representation* dari destinasi (Kategori + Wilayah + Fasilitas + Status Harga), menghitung TF-IDF Vector Similarity, dan menguranginya dengan Penalti Kualitas:<br>$$Score = Cosine(TFIDF_U, TFIDF_I) - Penalty_{quality}$$ | Mengukur efektifitas pendekatan representasi teks terstruktur vs One-Hot murni. |
| **Candidate 4** | **Hybrid Multi-Objective Scoring (Rekomendasi Utama)** | Mengintegrasikan seluruh aspek (Similarity Kategori/Wilayah/Fasilitas, Geodesic Distance Decay, Integrasi Sentimen Ulasan, dan Quality Penalty):<br>$$Score_{final} = w_1 Sim_{cat} + w_2 Sim_{reg} + w_3 Sim_{fac} + w_4 Sim_{dist} + w_5 Sim_{opinion} - Penalty_{quality}$$ | Algoritma komprehensif yang dirancang khusus sesuai spesifikasi SRS. |

---

## 6. Matriks Algoritma Analisis Sentimen NLP yang Akan Dibandingkan (*Sentiment Benchmarking*)

Untuk pengolahan teks ulasan pengunjung, kita akan mengimplementasikan dan membandingkan **3 Pendekatan Model NLP**:

| ID Algoritma | Nama Model Sentimen | Deskripsi Teknis Pipeline NLP | Target Metrik |
| :--- | :--- | :--- | :--- |
| **Baseline 1** | **Lexicon-Based Analyzer** | Menggunakan kamus kata positif/negatif Bahasa Indonesia (VADER/InaLexicon) untuk menghitung polarity score tanpa pelatihan model. | Memerlukan 0 data latih, cepat, tetapi kurang memahami konteks lokal/gaul. |
| **Baseline 2** | **TF-IDF + Logistic Regression / SVM** | Preprocessing teks ulasan (cleansing, lowercasing, stopword removal) $\rightarrow$ Ekstraksi Fitur TF-IDF (N-gram 1-2) $\rightarrow$ Classifier supervised. | Model Machine Learning klasik yang stabil, efisien, dan ringan diproses. |
| **Candidate 3** | **Fine-Tuned IndoBERT** | Fine-tuning model Transformer pretrained Bahasa Indonesia (`indobenchmark/indobert-base-p1`) pada 3 kelas (`positive`, `neutral`, `negative`). | Menangkap konteks kalimat kompleks, negasi, dan ekspresi ulasan wisata secara mendalam. |

---

## 7. Strategi Evaluasi Performa & Metrik Pengujian (*Evaluation Plan*)

### 7.1 Evaluasi Model Rekomendasi (*Recommender Evaluation Metrics*)
Pengujian performa algoritma rekomendasi dilakukan menggunakan skenario pengujian preferensi (*synthetic/benchmark test cases*) dengan metrik:

1. **Precision@K ($P@K$)**: Persentase destinasi relevan dalam $K$ item rekomendasi teratas.
   $$P@K = \frac{|\text{Item Relevan dalam Top-}K|}{K}$$
2. **Recall@K ($R@K$)**: Persentase destinasi relevan yang berhasil direkomendasikan dari seluruh item relevan.
3. **nDCG@K (Normalized Discounted Cumulative Gain)**: Mengukur kualitas peringkat rekomendasi dengan memberikan bobot lebih tinggi pada item relevan di posisi teratas.
4. **Catalog Coverage**: Persentase total destinasi unik dari 3.130 tempat yang pernah muncul dalam rekomendasi:
   $$Coverage = \frac{|\bigcup_{u \in U} R_u|}{3.130} \times 100\%$$
5. **Regional & Category Diversity**: Mengukur keberagaman variasi kabupaten/kota dan kategori dalam hasil *Top-N*.
6. **Inference Latency (ms)**: Waktu komputasi yang dibutuhkan algoritma untuk menghasilkan rekomendasi dari 3.130 baris data.

### 7.2 Evaluasi Model Sentimen NLP (*Sentiment Evaluation Metrics*)
1. **Accuracy**: Persentase total prediksi sentimen yang benar.
2. **Macro F1-Score**: Rata-rata F1-score lintas 3 kelas (Positif, Netral, Negatif) untuk menangani ketidakseimbangan kelas (*imbalanced data*).
3. **Confusion Matrix**: Matriks visualisasi *True Positive*, *False Positive*, *True Negative*, dan *False Negative*.
