# Model Directory — Recommendation & Sentiment Machine Learning Engine

Direktori ini berisi arsitektur, modul *feature engineering*, eksperimen algoritma, evaluasi performa, dan REST API serving untuk sistem **Recommendation Traveller Lampung**.

## Struktur Direktori Modul

```
Model/
├── ARCHITECTURE.md             # Dokumen Cetak Biru Arsitektur Model & Benchmark Plan
├── README.md                   # Panduan Modul Model (File Ini)
├── feature_engineering/        # Pipeline Transformasi Vektor Fitur & Matriks ML
├── recommender/                # Algoritma Rekomendasi & Evaluasi Benchmark
│   ├── baselines/              # Algoritma Baseline 1 & 2
│   ├── candidates/             # Algoritma Candidate 3 & 4 (Hybrid Scoring)
│   └── evaluation/             # Evaluator (Precision@K, Recall@K, nDCG@K, Coverage)
├── sentiment/                  # Pipeline NLP Analisis Sentimen Ulasan
│   ├── preprocessing/          # Preprocessing & Normalisasi Teks Bahasa Indonesia
│   ├── models/                 # Model TF-IDF, Logistic Regression & IndoBERT
│   └── evaluation/             # Evaluator Sentimen (Accuracy, Macro F1-Score)
└── api/                        # FastAPI Service & Pydantic Contracts
```
