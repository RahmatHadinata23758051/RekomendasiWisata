import os
import json
import hashlib
import pandas as pd
import numpy as np

# Fixed Canonical Vocabulary Definitions
CATEGORIES_VOCAB = [
    'agrotourism', 'beach', 'camping', 'culture', 'education', 'family', 'forest',
    'hill', 'history', 'island', 'lake', 'mountain', 'museum', 'nature',
    'other', 'park', 'recreation', 'religious', 'river', 'waterfall', 'waterpark'
]

REGIONS_VOCAB = [
    'Kabupaten Lampung Barat', 'Kabupaten Lampung Selatan', 'Kabupaten Lampung Tengah',
    'Kabupaten Lampung Timur', 'Kabupaten Lampung Utara', 'Kabupaten Mesuji',
    'Kabupaten Pesawaran', 'Kabupaten Pesisir Barat', 'Kabupaten Pringsewu',
    'Kabupaten Tanggamus', 'Kabupaten Tulang Bawang', 'Kabupaten Tulang Bawang Barat',
    'Kabupaten Way Kanan', 'Kota Bandar Lampung', 'Kota Metro'
]

FACILITIES_VOCAB = [
    'has_parking', 'has_toilet', 'has_food', 'has_prayer_room', 'has_wheelchair_access',
    'has_guide', 'has_lodging', 'has_camping', 'has_wifi', 'has_transport'
]

def resolve_master_path():
    candidate_paths = [
        "Data/consolidated/attractions_enrichment_master_full.parquet",
        "Scraping/data/enrichment/consolidated/attractions_enrichment_master_full.parquet",
        "data/enrichment/consolidated/attractions_enrichment_master_full.parquet"
    ]
    for p in candidate_paths:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(f"Master parquet dataset not found in any expected paths: {candidate_paths}")

def resolve_facilities_path():
    candidate_paths = [
        "Data/relations/facilities_full.parquet",
        "Scraping/data/enrichment/metadata/relations/facilities_full.parquet",
        "data/enrichment/metadata/relations/facilities_full.parquet"
    ]
    for p in candidate_paths:
        if os.path.exists(p):
            return p
    return None

def build_recommender_dataset(
    master_parquet_path=None,
    facilities_parquet_path=None,
    output_dir="Data/consolidated",
    reports_dir="reports"
):
    """
    Transforms Consolidated Master (3.130 rows x 99 cols) into Recommender-Ready Dataset.
    Enforces Option 1: Hybrid (Structured Lists + Flattened Columns).
    """
    if master_parquet_path is None:
        master_parquet_path = resolve_master_path()
    if facilities_parquet_path is None:
        facilities_parquet_path = resolve_facilities_path()

    print(f"Loading master dataset from: {master_parquet_path}")
    df_master = pd.read_parquet(master_parquet_path)
    n_rows = len(df_master)
    print(f"Loaded {n_rows} rows from Consolidated Master.")

    if n_rows != 3130:
        raise ValueError(f"Expected 3.130 master rows, got {n_rows}")

    # Load extra facility normalization if available
    facility_extra_set = {}
    if facilities_parquet_path and os.path.exists(facilities_parquet_path):
        df_fac = pd.read_parquet(facilities_parquet_path)
        for cid, group in df_fac.groupby("canonical_id"):
            raw_labels = " ".join(group["raw_label"].dropna().astype(str).str.lower())
            facility_extra_set[cid] = raw_labels

    # Prepare arrays
    cat_vectors = []
    reg_vectors = []
    fac_vectors = []

    # Flattened column arrays for NumPy high-performance matrices
    cat_onehot_matrix = np.zeros((n_rows, len(CATEGORIES_VOCAB)), dtype=np.float32)
    reg_onehot_matrix = np.zeros((n_rows, len(REGIONS_VOCAB)), dtype=np.float32)
    fac_multihot_matrix = np.zeros((n_rows, len(FACILITIES_VOCAB)), dtype=np.float32)

    eligible_flags = []
    rating_norms = []
    sentiment_means = []
    sentiment_confs = []
    price_statuses = []
    quality_penalties = []

    for i, (_, row) in enumerate(df_master.iterrows()):
        cid = row["canonical_id"]
        
        # 1. Category One-Hot Encoding
        cat_vec = np.zeros(len(CATEGORIES_VOCAB), dtype=np.float32)
        cat = str(row.get("primary_category", "")).lower().strip()
        if cat in CATEGORIES_VOCAB:
            idx = CATEGORIES_VOCAB.index(cat)
            cat_vec[idx] = 1.0
            cat_onehot_matrix[i, idx] = 1.0
        cat_vectors.append(cat_vec.tolist())

        # 2. Region One-Hot Encoding
        reg_vec = np.zeros(len(REGIONS_VOCAB), dtype=np.float32)
        reg = str(row.get("city_or_regency", "")).strip()
        if reg in REGIONS_VOCAB:
            idx = REGIONS_VOCAB.index(reg)
            reg_vec[idx] = 1.0
            reg_onehot_matrix[i, idx] = 1.0
        reg_vectors.append(reg_vec.tolist())

        # 3. Facility Multi-Hot Binary Encoding
        fac_vec = np.zeros(len(FACILITIES_VOCAB), dtype=np.float32)
        # Check explicit master boolean flags
        for f_idx, f_key in enumerate(FACILITIES_VOCAB[:5]):
            val = row.get(f_key, False)
            if pd.notna(val) and bool(val):
                fac_vec[f_idx] = 1.0

        # Check extra facilities text if present
        extra_text = facility_extra_set.get(cid, "")
        if "guide" in extra_text or "pemandu" in extra_text:
            fac_vec[5] = 1.0
        if "penginapan" in extra_text or "homestay" in extra_text or "hotel" in extra_text or "villa" in extra_text:
            fac_vec[6] = 1.0
        if "camping" in extra_text or "kemah" in extra_text:
            fac_vec[7] = 1.0
        if "wifi" in extra_text or "internet" in extra_text:
            fac_vec[8] = 1.0
        if "parkir" in extra_text or "transport" in extra_text or "angkot" in extra_text:
            fac_vec[9] = 1.0

        fac_multihot_matrix[i, :] = fac_vec
        fac_vectors.append(fac_vec.tolist())

        # 4. Eligibility Flag
        ops_status = str(row.get("operational_status", "unknown")).lower().strip()
        lat = row.get("latitude")
        lng = row.get("longitude")
        is_eligible = (ops_status != "permanently_closed") and pd.notna(lat) and pd.notna(lng)
        eligible_flags.append(bool(is_eligible))

        # 5. Rating Normalized (0.0 to 1.0)
        rev_status = str(row.get("review_coverage_status", "not_processed"))
        mean_rating = row.get("review_rating_mean")
        if rev_status == "scraped" and pd.notna(mean_rating):
            rating_norms.append(float(mean_rating) / 5.0)
        else:
            rating_norms.append(np.nan)

        # 6. Sentiment Values (Placeholder / Integration Layer)
        sentiment_means.append(np.nan)
        sentiment_confs.append(0.0)

        # 7. Price Status Resolution
        p_status = str(row.get("external_verification_status", "unavailable"))
        if p_status not in ["verified_current", "provisional", "historical", "unavailable"]:
            p_status = "unavailable"
        price_statuses.append(p_status)

        # 8. Quality Penalty Calculation
        comp_score = float(row.get("overall_completeness_score", 50.0))
        warn_cnt = int(row.get("quality_warning_count", 0))
        
        # Penalty formula: α*(100-Completeness) + β*Unknown_Status + γ*Warning_Count
        penalty = 0.001 * (100.0 - comp_score) + 0.02 * warn_cnt
        if ops_status == "unknown":
            penalty += 0.10
        if ops_status == "permanently_closed":
            penalty += 1.00
        quality_penalties.append(float(penalty))

    # Build Structured Output DataFrame (Option 1: Hybrid)
    df_features = pd.DataFrame({
        "canonical_id": df_master["canonical_id"],
        "name": df_master["name"],
        "primary_category": df_master["primary_category"],
        "city_or_regency": df_master["city_or_regency"],
        "latitude": df_master["latitude"].astype(np.float64),
        "longitude": df_master["longitude"].astype(np.float64),
        "operational_status": df_master["operational_status"],
        "is_eligible_recommend": eligible_flags,
        "category_vector": cat_vectors,
        "region_vector": reg_vectors,
        "facility_vector": fac_vectors,
        "review_coverage_status": df_master["review_coverage_status"],
        "rating_normalized": rating_norms,
        "sentiment_score_mean": sentiment_means,
        "sentiment_confidence": sentiment_confs,
        "price_status": price_statuses,
        "price_min_idr": df_master["external_price_min"].astype(np.float64),
        "price_max_idr": df_master["external_price_max"].astype(np.float64),
        "overall_completeness_score": df_master["overall_completeness_score"].astype(np.float32),
        "quality_warning_count": df_master["quality_warning_count"].astype(np.int32),
        "quality_penalty_score": quality_penalties
    })

    # Append flattened binary feature columns for fast 2D matrix loading
    for idx, c_name in enumerate(CATEGORIES_VOCAB):
        df_features[f"feat_cat_{c_name}"] = cat_onehot_matrix[:, idx]

    for idx, r_name in enumerate(REGIONS_VOCAB):
        clean_r = r_name.lower().replace(" ", "_")
        df_features[f"feat_reg_{clean_r}"] = reg_onehot_matrix[:, idx]

    for idx, f_name in enumerate(FACILITIES_VOCAB):
        df_features[f"feat_fac_{f_name}"] = fac_multihot_matrix[:, idx]

    # Verification checks
    assert len(df_features) == 3130
    assert df_features["canonical_id"].nunique() == 3130
    assert (df_features["operational_status"] == "permanently_closed").sum() == 4
    assert df_features[df_features["operational_status"] == "permanently_closed"]["is_eligible_recommend"].sum() == 0

    # Ensure output directories exist
    target_dirs = [output_dir, "Scraping/data/enrichment/consolidated"]
    for d in target_dirs:
        os.makedirs(d, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)

    for d in target_dirs:
        out_parquet = os.path.join(d, "recommender_ready_features.parquet")
        out_csv = os.path.join(d, "recommender_ready_features.csv")
        df_features.to_parquet(out_parquet, index=False)
        df_features.to_csv(out_csv, index=False, encoding="utf-8")

    # Generate Checksum & Provenance Manifest
    main_parquet = os.path.join(output_dir, "recommender_ready_features.parquet")
    h_pq = hashlib.sha256()
    with open(main_parquet, "rb") as f:
        while chunk := f.read(8192):
            h_pq.update(chunk)

    manifest = {
        "dataset_name": "recommender_ready_features",
        "dataset_version": "v1.0",
        "source_master_version": "consolidated-enrichment-master-full-v1",
        "total_rows": n_rows,
        "unique_canonical_ids": int(df_features["canonical_id"].nunique()),
        "eligible_recommend_count": int(df_features["is_eligible_recommend"].sum()),
        "ineligible_recommend_count": int((~df_features["is_eligible_recommend"]).sum()),
        "category_vocab_size": len(CATEGORIES_VOCAB),
        "region_vocab_size": len(REGIONS_VOCAB),
        "facility_vocab_size": len(FACILITIES_VOCAB),
        "total_feature_columns": len(df_features.columns),
        "sha256_parquet": h_pq.hexdigest(),
        "generated_at": pd.Timestamp.now().isoformat()
    }

    manifest_path = os.path.join(output_dir, "recommender_ready_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # Write Markdown Audit Report
    report_md_path = os.path.join(reports_dir, "recommender_ready_feature_audit.md")
    report_content = f"""# Recommender-Ready Feature Engineering Audit Report

| Parameter Audit | Value |
| :--- | :--- |
| **Dataset Name** | `recommender_ready_features` |
| **Total Rows** | {n_rows} |
| **Unique Canonical IDs** | {manifest['unique_canonical_ids']} |
| **Eligible Attractions Count** | {manifest['eligible_recommend_count']} |
| **Ineligible (Permanently Closed/No Coord)** | {manifest['ineligible_recommend_count']} |
| **Category Vocab Size** | {manifest['category_vocab_size']} categories |
| **Region Vocab Size** | {manifest['region_vocab_size']} regions |
| **Facility Vocab Size** | {manifest['facility_vocab_size']} facilities |
| **Total Feature Columns** | {manifest['total_feature_columns']} columns |
| **Parquet SHA256** | `{manifest['sha256_parquet']}` |
"""
    with open(report_md_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"Exported Recommender-Ready Features Parquet & Manifest successfully.")
    return df_features

if __name__ == "__main__":
    build_recommender_dataset()
