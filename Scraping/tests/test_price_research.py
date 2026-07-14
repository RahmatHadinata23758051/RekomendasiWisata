import os
import json
import shutil
import pytest
import pandas as pd
import numpy as np
from src.enrichment.price_research import (
    run_price_research,
    get_integrity_checksums,
    compute_sha256,
    PRICE_TYPE_ENTRY,
    PRICE_TYPE_PARKING,
    PRICE_TYPE_ACTIVITY,
    PRICE_TYPE_PACKAGE
)

@pytest.fixture
def restore_price_data_after_test():
    import shutil
    src_dir = "data/enrichment/price"
    backup_dir = "data/enrichment/price_backup_func"
    if os.path.exists(src_dir):
        shutil.copytree(src_dir, backup_dir, dirs_exist_ok=True)
    yield
    if os.path.exists(backup_dir):
        if os.path.exists(src_dir):
            shutil.rmtree(src_dir)
        shutil.copytree(backup_dir, src_dir)
        shutil.rmtree(backup_dir)

# 1. Test input candidate audit structure
def test_task1_input_audit_structure():
    input_path = "data/enrichment/price/validation/research_price_candidates.csv"
    assert os.path.exists(input_path), "research_price_candidates.csv must exist"
    df = pd.read_csv(input_path)
    assert len(df) == 11, "Must contain exactly 11 pilot candidates"
    assert df["canonical_id"].is_unique, "canonical_id must be unique"
    assert df["validation_scope_status"].eq("in_scope").all(), "All must be in_scope"
    assert df["validation_status"].eq("validated").all(), "All must be validated"
    assert df["final_decision"].eq("research").all(), "All final_decision must be research"
    assert not (df["operational_status"] == "permanently_closed").any(), "No closed places allowed"

# 2. Test dry-run query queue generation
def test_task2_run_price_research_dry_run():
    res = run_price_research(
        input_path="data/enrichment/price/validation/research_price_candidates.csv",
        dry_run=True
    )
    assert res["dry_run"] is True
    queries_path = "data/enrichment/price/research/price_research_queries.csv"
    assert os.path.exists(queries_path)
    df_q = pd.read_csv(queries_path)
    assert len(df_q) == 11 * 12, "Each candidate must have exactly 12 query templates"
    assert "query_id" in df_q.columns
    assert "canonical_id" in df_q.columns
    assert "query_type" in df_q.columns
    assert "query_text" in df_q.columns

# 3. Test price research coverage columns
def test_task3_price_research_coverage_columns():
    cov_path = "data/enrichment/price/research/price_research_coverage.csv"
    assert os.path.exists(cov_path)
    df = pd.read_csv(cov_path)
    assert len(df) == 11
    required_cols = [
        "canonical_id", "name", "research_status", "queries_attempted",
        "sources_checked", "accepted_sources", "observations_found",
        "selected_prices", "conflicts_found", "completed_at"
    ]
    for col in required_cols:
        assert col in df.columns, f"Column {col} missing in coverage report"

# 4. Test price research manifest schema
def test_task4_price_research_manifest_schema():
    manifest_path = "data/enrichment/price/research/price_research_manifest.json"
    assert os.path.exists(manifest_path)
    with open(manifest_path, "r") as f:
        data = json.load(f)
    assert "places" in data
    assert "global" in data
    assert len(data["places"]) == 11
    for k, val in data["places"].items():
        assert "canonical_id" in val
        assert "status" in val
        assert "observation_ids" in val
        assert "selected_price_ids" in val

# 5. Test source registry schema
def test_task5_source_registry_schema():
    source_reg_path = "data/enrichment/price/research/price_source_registry.csv"
    assert os.path.exists(source_reg_path)
    df = pd.read_csv(source_reg_path)
    required_cols = [
        "source_id", "canonical_id", "source_url", "source_domain",
        "source_type", "source_title", "publisher_name", "is_official",
        "is_government", "is_social_media", "is_ticketing_partner",
        "accessed_at", "http_status", "content_available", "source_relevance",
        "source_authority", "source_freshness", "source_confidence",
        "content_hash", "research_status", "rejection_reason"
    ]
    for col in required_cols:
        assert col in df.columns, f"Column {col} missing in source registry"

# 6. Test price observations schema
def test_task6_price_observations_schema():
    obs_path = "data/enrichment/price/research/price_observations.csv"
    assert os.path.exists(obs_path)
    df = pd.read_csv(obs_path)
    required_cols = [
        "price_observation_id", "canonical_id", "name", "price_type",
        "price_subtype", "audience_type", "visitor_origin", "day_type",
        "season_type", "package_name", "activity_name", "amount",
        "amount_min", "amount_max", "currency", "unit", "is_free",
        "is_starting_from", "is_estimated", "raw_price_text",
        "valid_from", "valid_until", "observed_at", "source_id"
    ]
    for col in required_cols:
        assert col in df.columns, f"Column {col} missing in price observations"

# 7. Test price observations currency standard
def test_task7_price_observations_currency():
    obs_path = "data/enrichment/price/research/price_observations.csv"
    df = pd.read_csv(obs_path)
    assert (df["currency"] == "IDR").all(), "All currencies must be normalized to IDR"

# 8. Test price conflicts schema
def test_task8_price_conflicts_schema():
    conflict_path = "data/enrichment/price/research/price_conflicts.csv"
    assert os.path.exists(conflict_path)
    df = pd.read_csv(conflict_path)
    if len(df) > 0:
        required_cols = [
            "conflict_id", "canonical_id", "price_type", "observation_id_a",
            "observation_id_b", "value_a", "value_b", "source_a", "source_b",
            "date_a", "date_b", "conflict_type", "resolution_status",
            "selected_observation_id", "resolution_reason", "requires_manual_review"
        ]
        for col in required_cols:
            assert col in df.columns

# 9. Test final prices schema
def test_task9_final_prices_schema():
    prices_path = "data/enrichment/price/final/prices.csv"
    assert os.path.exists(prices_path)
    df = pd.read_csv(prices_path)
    required_cols = [
        "price_id", "canonical_id", "name", "price_type", "price_subtype",
        "audience_type", "visitor_origin", "day_type", "season_type",
        "package_name", "amount", "amount_min", "amount_max", "currency",
        "unit", "is_free", "is_starting_from", "selected_observation_id",
        "source_id", "source_url", "source_type", "source_authority",
        "valid_from", "valid_until", "observed_at", "verification_status",
        "confidence", "selection_reason", "price_version"
    ]
    for col in required_cols:
        assert col in df.columns

# 10. Test unresolved queue structure
def test_task10_unresolved_queue_structure():
    unresolved_path = "data/enrichment/price/research/unresolved_price_candidates.csv"
    assert os.path.exists(unresolved_path)
    df = pd.read_csv(unresolved_path)
    assert len(df) == 3, "Exactly 3 candidates must be unresolved"
    required_cols = [
        "canonical_id", "name", "original_priority", "unresolved_reason",
        "requires_manual_review", "scraped_price_value", "notes"
    ]
    for col in required_cols:
        assert col in df.columns

# 11. Test manifest accuracy totals
def test_task11_manifest_accuracy_totals():
    manifest_path = "data/enrichment/price/research/price_research_manifest.json"
    with open(manifest_path, "r") as f:
        data = json.load(f)
    g = data["global"]
    assert g["input_count"] == 11
    assert g["completed_count"] == 11
    assert g["unresolved_count"] == 3
    assert g["failed_count"] == 0

# 12. Test source quality report
def test_task12_source_quality_report():
    quality_path = "reports/price_research_source_quality.csv"
    assert os.path.exists(quality_path)
    df = pd.read_csv(quality_path)
    assert "source_id" in df.columns
    assert "source_domain" in df.columns
    assert "observations_extracted" in df.columns
    assert df["observations_extracted"].sum() > 0

# 13. Test price type distribution report
def test_task13_price_type_distribution_report():
    dist_path = "reports/price_research_price_type_distribution.csv"
    assert os.path.exists(dist_path)
    df = pd.read_csv(dist_path)
    assert "price_type" in df.columns
    assert "count" in df.columns
    assert len(df) > 0

# 14. Test temporal report
def test_task14_temporal_report():
    temporal_path = "reports/price_research_temporal.csv"
    assert os.path.exists(temporal_path)
    df = pd.read_csv(temporal_path)
    assert "price_id" in df.columns
    assert "canonical_id" in df.columns
    assert "observed_at" in df.columns

# 15. Test region report
def test_task15_region_report():
    region_path = "reports/price_research_region.csv"
    assert os.path.exists(region_path)
    df = pd.read_csv(region_path)
    assert "region" in df.columns
    assert "total_research_candidates" in df.columns
    assert "entry_ticket_price_count" in df.columns
    assert "average_entry_ticket_price" in df.columns

# 16. Test summary markdown section existence
def test_task16_summary_markdown():
    summary_path = "reports/price_research_summary.md"
    assert os.path.exists(summary_path)
    with open(summary_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "# Price Research Summary Report" in content
    assert "## 1. Metrics & Coverage" in content
    assert "## 2. Price Type Distribution" in content
    assert "## 3. Unresolved Candidates" in content
    assert "## 4. Conflicts Identified & Resolved" in content
    assert "## 5. Region Statistics" in content

# 17. Test integrity checks report
def test_task17_integrity_checks():
    integrity_path = "reports/price_research_integrity.json"
    assert os.path.exists(integrity_path)
    with open(integrity_path, "r") as f:
        data = json.load(f)
    assert "checksums_before" in data
    assert "checksums_after" in data
    assert data["integrity_passed"] is True

# 18. Test resume skip behavior
def test_task18_resume_skip():
    # Running with resume=True should load already completed entries
    res = run_price_research(
        input_path="data/enrichment/price/validation/research_price_candidates.csv",
        resume=True
    )
    # Total candidates remain 11, completed counts match
    assert res["stats"]["completed_count"] == 11

# 19. Test limit parameter limits processing count
def test_task19_limit(restore_price_data_after_test):
    # If we run with force=True (or new manifest) and limit=1, it stops after 1
    res = run_price_research(
        input_path="data/enrichment/price/validation/research_price_candidates.csv",
        limit=1,
        force=True
    )
    assert res["stats"]["completed_count"] == 1

# 20. Test single canonical_id parameter
def test_task20_single_canonical_id(restore_price_data_after_test):
    res = run_price_research(
        input_path="data/enrichment/price/validation/research_price_candidates.csv",
        canonical_id="can_151f3bbf542d",
        force=True
    )
    assert res["stats"]["completed_count"] == 1

# 21. Test invalid input candidate CSV file throws ValueError
def test_task21_invalid_input():
    # Create invalid CSV file
    bad_csv = "data/enrichment/price/validation/bad_candidates.csv"
    df_bad = pd.DataFrame([{"canonical_id": "bad_1"}])
    df_bad.to_csv(bad_csv, index=False)
    with pytest.raises(ValueError):
        run_price_research(input_path=bad_csv)
    if os.path.exists(bad_csv):
        os.remove(bad_csv)

# 22. Test normalization of exact values for Pantai Mutun entry ticket
def test_task22_normalization_exact_values():
    prices_path = "data/enrichment/price/final/prices.csv"
    df = pd.read_csv(prices_path)
    # Pantai Mutun entry ticket should be resolved to 35,000 IDR
    mutun_entry = df[(df["canonical_id"] == "can_151f3bbf542d") & (df["price_type"] == "entry_ticket")]
    assert len(mutun_entry) == 1
    assert mutun_entry.iloc[0]["amount"] == 35000

# 23. Test individual evidence files existence and valid JSON structure
def test_task23_evidence_individual_files():
    evidence_dir = "data/enrichment/price/research/evidence"
    assert os.path.exists(evidence_dir)
    ev_files = os.listdir(evidence_dir)
    assert len(ev_files) > 0
    first_ev = os.path.join(evidence_dir, ev_files[0])
    with open(first_ev, "r") as f:
        data = json.load(f)
    assert "source_id" in data
    assert "canonical_id" in data
    assert "relevant_excerpt" in data
    assert "extracted_structured_fields" in data
