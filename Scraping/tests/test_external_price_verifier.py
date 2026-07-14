import os
import json
import shutil
import stat
import pytest
import pandas as pd
import numpy as np
from src.enrichment.external_price_verifier import (
    run_external_price_verification,
    get_integrity_checksums,
    compute_sha256
)

def remove_readonly(func, path, excinfo):
    os.chmod(path, stat.S_IWRITE)
    func(path)

def clear_external_outputs():
    ext_dir = "data/enrichment/price/external"
    if os.path.exists(ext_dir):
        for f in os.listdir(ext_dir):
            if f != "mock_search_results.json":
                path = os.path.join(ext_dir, f)
                if os.path.isdir(path):
                    try:
                        shutil.rmtree(path, onerror=remove_readonly)
                    except Exception:
                        pass
                else:
                    try:
                        os.chmod(path, stat.S_IWRITE)
                        os.remove(path)
                    except Exception:
                        pass
    ev_dir = "data/enrichment/price/external/evidence"
    if os.path.exists(ev_dir):
        try:
            shutil.rmtree(ev_dir, onerror=remove_readonly)
        except Exception:
            pass
        
    for ext in ["csv", "parquet", "jsonl"]:
        p_path = f"data/enrichment/price/final/prices_external_verified.{ext}"
        if os.path.exists(p_path):
            try:
                os.chmod(p_path, stat.S_IWRITE)
                os.remove(p_path)
            except Exception:
                pass
                
    reports_dir = "reports"
    if os.path.exists(reports_dir):
        for f in os.listdir(reports_dir):
            if f.startswith("external_price_") or f in [
                "local_external_price_comparison.csv",
                "external_price_type_distribution.csv",
                "external_price_conflicts.csv",
                "external_price_unresolved.csv",
                "external_price_verification_place_status.csv",
                "external_price_region_coverage.csv",
                "external_price_category_coverage.csv",
                "external_price_identity_audit.csv",
                "external_price_temporal_distribution.csv"
            ]:
                try:
                    path = os.path.join(reports_dir, f)
                    os.chmod(path, stat.S_IWRITE)
                    os.remove(path)
                except Exception:
                    pass

@pytest.fixture
def restore_price_data_after_test():
    src_dir = "data/enrichment/price"
    backup_dir = "data/enrichment/price_backup_func_ext"
    
    if os.path.exists(src_dir):
        shutil.copytree(src_dir, backup_dir, dirs_exist_ok=True)
        
    clear_external_outputs()
    
    yield
    
    if os.path.exists(backup_dir):
        if os.path.exists(src_dir):
            try:
                shutil.rmtree(src_dir, onerror=remove_readonly)
            except Exception:
                pass
        try:
            shutil.copytree(backup_dir, src_dir, dirs_exist_ok=True)
            shutil.rmtree(backup_dir, onerror=remove_readonly)
        except Exception:
            pass

# 1. Test Input Queue Validation & Schema
def test_input_queue_validation(restore_price_data_after_test):
    queue_path = "data/enrichment/price/research/external_price_verification_queue.csv"
    assert os.path.exists(queue_path)
    df = pd.read_csv(queue_path)
    assert len(df) == 11
    assert df["canonical_id"].is_unique

# 2. Test Dry-Run Execution Mode
def test_dry_run_execution(restore_price_data_after_test):
    res = run_external_price_verification(
        queue_path="data/enrichment/price/research/external_price_verification_queue.csv",
        dry_run=True,
        fixture_mode=True,
        fixture_dir="tests/fixtures/external_price"
    )
    assert "stats" in res
    assert res["stats"]["total_pilot"] == 11

# 3. Test Identity Verification and Score Logic
def test_identity_verification(restore_price_data_after_test):
    # Running Pantai Mutun canary
    res = run_external_price_verification(
        queue_path="data/enrichment/price/research/external_price_verification_queue.csv",
        canonical_id="can_151f3bbf542d",
        force=True,
        fixture_mode=True,
        fixture_dir="tests/fixtures/external_price"
    )
    stats = res["stats"]
    assert stats["completed_count"] == 11
    # Pantai Mutun is simulated_not_verified in fixture mode, so verified_count = 0
    assert stats["verified_count"] == 0
    assert stats["observations_count"] == 3
    # simulated_fixture cannot produce a production selected price
    assert stats["verified_prices_count"] == 0

# 4. Test Resume and Idempotency
def test_resume_idempotency(restore_price_data_after_test):
    # First, run Pantai Mutun (canary 1)
    run_external_price_verification(
        queue_path="data/enrichment/price/research/external_price_verification_queue.csv",
        canonical_id="can_151f3bbf542d",
        force=True,
        fixture_mode=True,
        fixture_dir="tests/fixtures/external_price"
    )
    
    # Second, resume with Camping Area Sonokeling 1 (canary 2)
    res = run_external_price_verification(
        queue_path="data/enrichment/price/research/external_price_verification_queue.csv",
        canonical_id="can_1f6b9f3c2ceb",
        resume=True,
        fixture_mode=True,
        fixture_dir="tests/fixtures/external_price"
    )
    stats = res["stats"]
    assert stats["verified_count"] == 0
    assert stats["provisional_count"] == 0
    assert stats["observations_count"] == 4
    assert stats["verified_prices_count"] == 0

# 5. Task 11: Production mode cannot load mock_search_results.json automatically
def test_production_mode_no_mock_auto_load(restore_price_data_after_test):
    # If run in default production mode (fixture_mode=False) and we don't do real verification (dry run)
    res = run_external_price_verification(
        queue_path="data/enrichment/price/research/external_price_verification_queue.csv",
        dry_run=True,
        fixture_mode=False
    )
    assert res["stats"]["queries_count"] == 242 # 11 * 22

# 6. Task 11: simulated_fixture cannot produce verified_current or official_live_unbounded
def test_simulated_fixture_restrictions(restore_price_data_after_test):
    res = run_external_price_verification(
        queue_path="data/enrichment/price/research/external_price_verification_queue.csv",
        fixture_mode=True,
        fixture_dir="tests/fixtures/external_price"
    )
    # Check that verification_status in global_manifest are not counted as verified/official
    assert res["stats"]["verified_count"] == 0
    assert res["stats"]["official_unbounded_count"] == 0
    assert res["stats"]["verified_prices_count"] == 0
    
    # Check the actual written CSV files
    df_obs = pd.read_csv("data/enrichment/price/external/external_price_observations.csv")
    assert (df_obs["data_origin"] == "simulated_fixture").all()
    assert (df_obs["verification_status"] == "simulated_not_verified").all()
    assert (df_obs["temporal_status"] == "simulated_only").all()
    
    # prices_external_verified.csv must be empty/0 rows
    df_prices = pd.read_csv("data/enrichment/price/final/prices_external_verified.csv")
    assert len(df_prices) == 0

# 7. Task 11: Production selected prices verification and retrievability
def test_production_real_sources_verification(restore_price_data_after_test):
    # Run in real-sources mode for Pantai Mutun
    res = run_external_price_verification(
        queue_path="data/enrichment/price/research/external_price_verification_queue.csv",
        canonical_id="can_151f3bbf542d",
        fixture_mode=False,
        force=True
    )
    assert res["stats"]["verified_prices_count"] == 3
    
    # Check the written files
    df_prices = pd.read_csv("data/enrichment/price/final/prices_external_verified.csv")
    assert len(df_prices) == 3
    assert (df_prices["data_origin"] == "real_public_source").all()
    assert (df_prices["source_url"].str.startswith("http")).all()
    assert df_prices["selection_reason"].notna().all()
