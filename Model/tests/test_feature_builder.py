import os
import pytest
import pandas as pd
import numpy as np
from Model.feature_engineering.builder import build_recommender_dataset, CATEGORIES_VOCAB, REGIONS_VOCAB, FACILITIES_VOCAB

def test_feature_builder_output_integrity():
    df_out = build_recommender_dataset(
        master_parquet_path=None,
        output_dir="Data/consolidated",
        reports_dir="reports"
    )

    # 1. Shape and primary key assertions
    assert len(df_out) == 3130
    assert df_out["canonical_id"].nunique() == 3130

    # 2. Vocabulary checks
    assert len(CATEGORIES_VOCAB) == 21
    assert len(REGIONS_VOCAB) == 15
    assert len(FACILITIES_VOCAB) == 10

    # 3. Vector structure assertions (Option 1: Hybrid)
    first_cat_vec = df_out["category_vector"].iloc[0]
    assert len(first_cat_vec) == 21
    assert sum(first_cat_vec) == 1.0 or sum(first_cat_vec) == 0.0

    first_reg_vec = df_out["region_vector"].iloc[0]
    assert len(first_reg_vec) == 15
    assert sum(first_reg_vec) == 1.0 or sum(first_reg_vec) == 0.0

    first_fac_vec = df_out["facility_vector"].iloc[0]
    assert len(first_fac_vec) == 10

    # 4. Eligibility assertions
    closed_rows = df_out[df_out["operational_status"] == "permanently_closed"]
    assert len(closed_rows) == 4
    assert closed_rows["is_eligible_recommend"].sum() == 0

    eligible_count = df_out["is_eligible_recommend"].sum()
    assert eligible_count > 2900

    # 5. Flattened feature column assertions
    cat_feat_cols = [c for c in df_out.columns if c.startswith("feat_cat_")]
    assert len(cat_feat_cols) == 21

    reg_feat_cols = [c for c in df_out.columns if c.startswith("feat_reg_")]
    assert len(reg_feat_cols) == 15

    fac_feat_cols = [c for c in df_out.columns if c.startswith("feat_fac_")]
    assert len(fac_feat_cols) == 10
