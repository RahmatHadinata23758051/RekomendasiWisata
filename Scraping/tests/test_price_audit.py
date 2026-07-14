import os
import json
import pandas as pd
import pytest
from src.enrichment.price_audit import run_price_audit

def test_run_price_audit():
    # Run the audit on actual paths
    res = run_price_audit(
        observations_path="data/enrichment/price/research/price_observations.csv",
        coverage_path="data/enrichment/price/research/price_research_coverage.csv",
        final_prices_path="data/enrichment/price/final/prices.csv",
        output_dir="data/enrichment/price",
        reports_dir="reports",
        strict=False,
        dry_run=True,
        audit_version="test_price_audit_v1"
    )
    
    assert "stats" in res
    stats = res["stats"]
    assert stats["original_observations"] == 32
    assert stats["valid_observations"] == 29
    assert stats["rejected_observations"] == 3
    assert stats["destinations_with_obs"] == 8
    assert stats["destinations_without_obs"] == 3
    assert stats["queue_count"] == 11
    
    # Check that temporary files/reports were generated
    assert os.path.exists("reports/final_price_pilot_audit_summary.md")
    assert os.path.exists("reports/price_observation_false_positive_audit.csv")
    assert os.path.exists("reports/price_source_semantic_audit.csv")
    assert os.path.exists("reports/price_temporal_audit.csv")
    assert os.path.exists("reports/price_final_selection_audit.csv")
    assert os.path.exists("reports/price_place_final_status.csv")
    assert os.path.exists("reports/price_external_verification_queue.csv")
