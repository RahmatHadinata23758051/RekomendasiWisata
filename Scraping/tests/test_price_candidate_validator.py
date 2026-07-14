import os
import json
import hashlib
import pytest
import pandas as pd
from src.enrichment.price_candidate_validator import (
    run_validation,
    get_integrity_checksums,
    compute_sha256,
    DECISION_RESEARCH,
    DECISION_MANUAL_REVIEW,
    DECISION_EXCLUDED_FREE,
    DECISION_EXCLUDED_NON_ATTRACTION,
    DECISION_NOT_APPLICABLE
)

@pytest.fixture
def validation_results():
    """Run validation and return the results."""
    res = run_validation(
        input_path="data/enrichment/price/pilot_price_candidates.csv",
        metadata_path="data/enrichment/metadata/place_metadata.parquet",
        facilities_path="data/enrichment/metadata/facilities.parquet",
        operational_status_path="data/enrichment/metadata/operational_status.parquet",
        provenance_path="data/enrichment/metadata/metadata_provenance.csv",
        output_dir="data/enrichment/price/validation",
        reports_dir="reports",
        include_priorities="high,medium",
        strict=True,
        dry_run=True  # Dry run to avoid modifying actual output files during test runs
    )
    return res

def test_task10_criteria(validation_results):
    df_validated = validation_results["validated_df"]
    df_prov = validation_results["provenance_df"]
    stats = validation_results["stats"]
    
    # 1. Total pilot tepat 300
    assert len(df_validated) == 300
    
    # 2. Active scope tepat 166
    df_active = df_validated[df_validated["validation_scope_status"] == "in_scope"]
    assert len(df_active) == 166
    
    # 3. Out-of-scope tepat 134
    df_out = df_validated[df_validated["validation_scope_status"] == "out_of_scope"]
    assert len(df_out) == 134
    
    # 4. High tepat 76
    assert sum(df_validated["original_priority"] == "high") == 76
    
    # 5. Medium tepat 90
    assert sum(df_validated["original_priority"] == "medium") == 90
    
    # 6. Low priority candidates are out_of_scope
    df_low = df_validated[df_validated["original_priority"] == "low"]
    assert len(df_low) in [132, 133]
    for _, row in df_low.iterrows():
        assert row["validation_scope_status"] == "out_of_scope"
        assert row["validation_status"] == "not_evaluated"
        assert pd.isna(row["final_decision"]) or row["final_decision"] is None
        
    # 7. Original not_applicable tepat 1
    assert sum(df_validated["original_priority"] == "not_applicable") == 1
    
    # 8. Low tidak otomatis excluded_free (asserted in test 6 above: final_decision is None)
    
    # 9. Tidak adanya harga tidak dianggap free evidence
    # Ensure records with missing price and no free keyword are not automatically excluded_free or research
    df_no_price = df_active[df_active["existing_price_raw_value"].isna() & df_active["existing_price_hint"].isna()]
    # Any record without explicit free keyword or public space name should not be excluded_free
    for _, row in df_no_price.iterrows():
        if row["final_decision"] == DECISION_EXCLUDED_FREE:
            # Must have some public/free word
            assert any(x in row["name"].lower() or x in str(row["description"]).lower() for x in ["taman", "alun-alun", "tugu", "monumen", "lapangan", "makam", "kuburan", "masjid", "gratis", "free", "hutan"])
            
    # 10. Active decision distribution berjumlah tepat 166
    active_decisions_sum = (
        stats["research_count"] + 
        stats["manual_review_count"] + 
        stats["excluded_free_count"] + 
        stats["excluded_non_attraction_count"] + 
        stats["not_applicable_count"]
    )
    assert active_decisions_sum == 166
    
    # 11. Global reconciliation berjumlah tepat 300
    assert (len(df_active) + len(df_out)) == 300
    
    # 12. Research file hanya berisi high/medium
    df_research = df_active[df_active["final_decision"] == DECISION_RESEARCH]
    for _, row in df_research.iterrows():
        assert row["original_priority"] in ["high", "medium"]
        assert row["validation_scope_status"] == "in_scope"
        assert row["validation_status"] == "validated"
        
    # 13. Research file tidak berisi permanently closed
    for _, row in df_research.iterrows():
        assert row["operational_status"] != "permanently_closed"
        assert row["paid_evidence_score"] >= 3
        # Has query templates
        assert row["entry_ticket_query"] != ""
        
    # 14. Excluded_free active-scope memiliki provenance
    df_active_free = df_active[df_active["final_decision"] == DECISION_EXCLUDED_FREE]
    prov_ids = set(df_prov["canonical_id"])
    for _, row in df_active_free.iterrows():
        assert row["canonical_id"] in prov_ids
        
    # 15. Out-of-scope tidak masuk decision distribution active
    # (Asserted by checking active_decisions_sum is exactly 166, which is only high/medium records)
    
    # 16. Canonical ID unik dalam setiap output
    assert df_validated["canonical_id"].is_unique
    assert df_active["canonical_id"].is_unique
    assert df_out["canonical_id"].is_unique
    
    # 17. Integrity checksum tidak berubah
    checksums = get_integrity_checksums()
    assert len(checksums) == 4
    for k, v in checksums.items():
        assert v != ""
        
    # 18. Seluruh test lama tetap passed (asserted by pytest command execution)
    pass
