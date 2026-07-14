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
    from unittest.mock import patch
    
    class MockResponse:
        def __init__(self, text, status_code=200):
            self.text = text
            self.status_code = status_code
            self.url = "https://travel.detik.com/domestik/d-7301072/pantai-mutun-pantai-pasir-putih-terpopuler-di-pesawaran-lampung"
            self.headers = {"Content-Type": "text/html"}
            
    mock_text = "Harga tiket masuk Pantai Mutun terbaru 2026 adalah Rp35.000. Parkir motor Rp5.000. parkir mobil Rp10.000."
    
    with patch("requests.get", return_value=MockResponse(mock_text)):
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


# --- 17 New Tests for Clean-Room and Verification Constraints ---

def get_mock_response_for_canary(c_id, status_code=200):
    from src.enrichment.external_price_verifier import REAL_PUBLIC_SOURCES
    df_queue = pd.read_csv("data/enrichment/price/research/external_price_verification_queue.csv")
    name = df_queue[df_queue["canonical_id"] == c_id].iloc[0]["name"]
    res_list = REAL_PUBLIC_SOURCES.get(c_id, [])
    if res_list:
        body = res_list[0]["body"]
        url = res_list[0]["url"]
    else:
        body = "dummy body"
        url = "https://example.com"
        
    class MockResponse:
        def __init__(self):
            self.text = f"Welcome to {name}. Excerpt: {body}"
            self.status_code = status_code
            self.url = url
            self.headers = {"Content-Type": "text/html"}
            
    return MockResponse()

def test_fresh_run_starts_empty_manifest(restore_price_data_after_test, tmp_path):
    manifest_dir = tmp_path / "price_clean_run"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    m_file = manifest_dir / "external/external_verification_manifest.json"
    m_file.parent.mkdir(parents=True, exist_ok=True)
    with open(m_file, "w") as f:
        json.dump({"places": {"can_151f3bbf542d": {"processed": True, "status": "completed_verified"}}}, f)
        
    res = run_external_price_verification(
        queue_path="data/enrichment/price/research/external_price_verification_queue.csv",
        canonical_id="can_151f3bbf542d",
        fixture_mode=True,
        fixture_dir="tests/fixtures/external_price",
        fresh_run=True,
        output_dir=str(manifest_dir)
    )
    assert res["stats"]["completed_count"] == 11

def test_source_classification_wikipedia(restore_price_data_after_test):
    from unittest.mock import patch
    mock_resp = get_mock_response_for_canary("can_1fef284e7d10")
    with patch("requests.get", return_value=mock_resp):
        res = run_external_price_verification(
            queue_path="data/enrichment/price/research/external_price_verification_queue.csv",
            canonical_id="can_1fef284e7d10",
            fixture_mode=False,
            force=True
        )
    df_src = pd.read_csv("reports/external_price_source_quality.csv")
    row = df_src[df_src["source_url"].str.contains("wikipedia.org")].iloc[0]
    assert row["source_type"] == "reference"
    assert not row["is_official"]
    assert not row["is_government"]

def test_source_classification_detik(restore_price_data_after_test):
    from unittest.mock import patch
    mock_resp = get_mock_response_for_canary("can_151f3bbf542d")
    with patch("requests.get", return_value=mock_resp):
        res = run_external_price_verification(
            queue_path="data/enrichment/price/research/external_price_verification_queue.csv",
            canonical_id="can_151f3bbf542d",
            fixture_mode=False,
            force=True
        )
    df_src = pd.read_csv("reports/external_price_source_quality.csv")
    row = df_src[df_src["source_url"].str.contains("detik.com")].iloc[0]
    assert row["source_type"] == "news_media"

def test_source_classification_trip(restore_price_data_after_test):
    from unittest.mock import patch
    mock_resp = get_mock_response_for_canary("can_1f6b9f3c2ceb")
    with patch("requests.get", return_value=mock_resp):
        res = run_external_price_verification(
            queue_path="data/enrichment/price/research/external_price_verification_queue.csv",
            canonical_id="can_1f6b9f3c2ceb",
            fixture_mode=False,
            force=True
        )
    df_src = pd.read_csv("reports/external_price_source_quality.csv")
    row = df_src[df_src["source_url"].str.contains("trip.com")].iloc[0]
    assert row["source_type"] == "travel_marketplace"

def test_source_classification_government(restore_price_data_after_test):
    from unittest.mock import patch
    from src.enrichment.external_price_verifier import REAL_PUBLIC_SOURCES
    
    test_sources = {
        "can_151f3bbf542d": [
            {"url": "https://pesawaran.go.id/mutun", "source_type": "official_website", "title": "Pantai Mutun", "body": "Harga tiket masuk Pantai Mutun terbaru 2026 adalah Rp35.000.", "is_official": False, "is_government": True, "identity_verification_status": "verified"}
        ]
    }
    class MockResponse:
        def __init__(self):
            self.text = "Welcome to Pantai Mutun. Harga tiket masuk Pantai Mutun terbaru 2026 adalah Rp35.000."
            self.status_code = 200
            self.url = "https://pesawaran.go.id/mutun"
            self.headers = {"Content-Type": "text/html"}

    with patch("src.enrichment.external_price_verifier.REAL_PUBLIC_SOURCES", test_sources):
        with patch("requests.get", return_value=MockResponse()):
            res = run_external_price_verification(
                queue_path="data/enrichment/price/research/external_price_verification_queue.csv",
                canonical_id="can_151f3bbf542d",
                fixture_mode=False,
                force=True
            )
    df_src = pd.read_csv("reports/external_price_source_quality.csv")
    row = df_src[df_src["source_url"].str.contains("go.id")].iloc[0]
    assert row["source_type"] == "government"
    assert row["is_government"]

def test_source_classification_facebook(restore_price_data_after_test):
    from unittest.mock import patch
    from src.enrichment.external_price_verifier import REAL_PUBLIC_SOURCES
    
    test_sources = {
        "can_151f3bbf542d": [
            {"url": "https://facebook.com/pantaimutunofficial", "source_type": "official_website", "title": "Pantai Mutun", "body": "Harga tiket masuk Pantai Mutun terbaru 2026 adalah Rp35.000.", "is_official": True, "is_government": False, "identity_verification_status": "verified"}
        ]
    }
    class MockResponse:
        def __init__(self):
            self.text = "Welcome to Pantai Mutun. Harga tiket masuk Pantai Mutun terbaru 2026 adalah Rp35.000."
            self.status_code = 200
            self.url = "https://facebook.com/pantaimutunofficial"
            self.headers = {"Content-Type": "text/html"}

    with patch("src.enrichment.external_price_verifier.REAL_PUBLIC_SOURCES", test_sources):
        with patch("requests.get", return_value=MockResponse()):
            res = run_external_price_verification(
                queue_path="data/enrichment/price/research/external_price_verification_queue.csv",
                canonical_id="can_151f3bbf542d",
                fixture_mode=False,
                force=True
            )
    df_src = pd.read_csv("reports/external_price_source_quality.csv")
    row = df_src[df_src["source_url"].str.contains("facebook.com")].iloc[0]
    assert row["source_type"] == "official_social_media"

def test_source_classification_instagram(restore_price_data_after_test):
    from unittest.mock import patch
    from src.enrichment.external_price_verifier import REAL_PUBLIC_SOURCES
    
    test_sources = {
        "can_151f3bbf542d": [
            {"url": "https://instagram.com/pantaimutunofficial", "source_type": "official_website", "title": "Pantai Mutun", "body": "Harga tiket masuk Pantai Mutun terbaru 2026 adalah Rp35.000.", "is_official": True, "is_government": False, "identity_verification_status": "verified"}
        ]
    }
    class MockResponse:
        def __init__(self):
            self.text = "Welcome to Pantai Mutun. Harga tiket masuk Pantai Mutun terbaru 2026 adalah Rp35.000."
            self.status_code = 200
            self.url = "https://instagram.com/pantaimutunofficial"
            self.headers = {"Content-Type": "text/html"}

    with patch("src.enrichment.external_price_verifier.REAL_PUBLIC_SOURCES", test_sources):
        with patch("requests.get", return_value=MockResponse()):
            res = run_external_price_verification(
                queue_path="data/enrichment/price/research/external_price_verification_queue.csv",
                canonical_id="can_151f3bbf542d",
                fixture_mode=False,
                force=True
            )
    df_src = pd.read_csv("reports/external_price_source_quality.csv")
    row = df_src[df_src["source_url"].str.contains("instagram.com")].iloc[0]
    assert row["source_type"] == "official_social_media"

def test_source_classification_default(restore_price_data_after_test):
    from unittest.mock import patch
    from src.enrichment.external_price_verifier import REAL_PUBLIC_SOURCES
    
    test_sources = {
        "can_151f3bbf542d": [
            {"url": "https://www.mutunbeachresort.com/prices", "source_type": "general", "title": "Pantai Mutun", "body": "Harga tiket masuk Pantai Mutun terbaru 2026 adalah Rp35.000.", "is_official": True, "is_government": False, "identity_verification_status": "verified"}
        ]
    }
    class MockResponse:
        def __init__(self):
            self.text = "Welcome to Pantai Mutun. Harga tiket masuk Pantai Mutun terbaru 2026 adalah Rp35.000."
            self.status_code = 200
            self.url = "https://www.mutunbeachresort.com/prices"
            self.headers = {"Content-Type": "text/html"}

    with patch("src.enrichment.external_price_verifier.REAL_PUBLIC_SOURCES", test_sources):
        with patch("requests.get", return_value=MockResponse()):
            res = run_external_price_verification(
                queue_path="data/enrichment/price/research/external_price_verification_queue.csv",
                canonical_id="can_151f3bbf542d",
                fixture_mode=False,
                force=True
            )
    df_src = pd.read_csv("reports/external_price_source_quality.csv")
    row = df_src[df_src["source_url"].str.contains("mutunbeachresort.com")].iloc[0]
    assert row["source_type"] == "official_website"

def test_wikipedia_temporal_status_restriction(restore_price_data_after_test):
    from unittest.mock import patch
    mock_resp = get_mock_response_for_canary("can_1fef284e7d10")
    mock_resp.text += " terbaru 2026"
    with patch("requests.get", return_value=mock_resp):
        res = run_external_price_verification(
            queue_path="data/enrichment/price/research/external_price_verification_queue.csv",
            canonical_id="can_1fef284e7d10",
            fixture_mode=False,
            force=True
        )
    df_obs = pd.read_csv("data/enrichment/price/external/external_price_observations.csv")
    wiki_obs = df_obs[df_obs["source_url"].str.contains("wikipedia.org")]
    assert len(wiki_obs) > 0
    assert (wiki_obs["temporal_status"] == "recent_external_unverified").all()

def test_detik_temporal_status_restriction(restore_price_data_after_test):
    from unittest.mock import patch
    mock_resp = get_mock_response_for_canary("can_151f3bbf542d")
    with patch("requests.get", return_value=mock_resp):
        res = run_external_price_verification(
            queue_path="data/enrichment/price/research/external_price_verification_queue.csv",
            canonical_id="can_151f3bbf542d",
            fixture_mode=False,
            force=True
        )
    df_obs = pd.read_csv("data/enrichment/price/external/external_price_observations.csv")
    detik_obs = df_obs[df_obs["source_url"].str.contains("detik.com")]
    assert len(detik_obs) > 0
    assert (detik_obs["temporal_status"] == "recent_external_unverified").all()

def test_trip_temporal_status_restriction(restore_price_data_after_test):
    from unittest.mock import patch
    mock_resp = get_mock_response_for_canary("can_1f6b9f3c2ceb")
    with patch("requests.get", return_value=mock_resp):
        res = run_external_price_verification(
            queue_path="data/enrichment/price/research/external_price_verification_queue.csv",
            canonical_id="can_1f6b9f3c2ceb",
            fixture_mode=False,
            force=True
        )
    df_obs = pd.read_csv("data/enrichment/price/external/external_price_observations.csv")
    trip_obs = df_obs[df_obs["source_url"].str.contains("trip.com")]
    assert len(trip_obs) > 0
    assert (trip_obs["temporal_status"] == "recent_external_unverified").all()

def test_exact_excerpt_requirement_failed(restore_price_data_after_test):
    from unittest.mock import patch
    class MockResponse:
        def __init__(self):
            self.text = "Welcome to Pantai Mutun. The ticket price is different."
            self.status_code = 200
            self.url = "https://travel.detik.com/domestik/d-7301072/pantai-mutun-pantai-pasir-putih-terpopuler-di-pesawaran-lampung"
            self.headers = {"Content-Type": "text/html"}

    with patch("requests.get", return_value=MockResponse()):
        res = run_external_price_verification(
            queue_path="data/enrichment/price/research/external_price_verification_queue.csv",
            canonical_id="can_151f3bbf542d",
            fixture_mode=False,
            force=True
        )
    df_obs = pd.read_csv("data/enrichment/price/external/external_price_observations.csv")
    detik_obs = df_obs[df_obs["source_url"].str.contains("detik.com")]
    assert len(detik_obs) == 0

def test_exact_excerpt_requirement_passed(restore_price_data_after_test):
    from unittest.mock import patch
    mock_resp = get_mock_response_for_canary("can_151f3bbf542d")
    with patch("requests.get", return_value=mock_resp):
        res = run_external_price_verification(
            queue_path="data/enrichment/price/research/external_price_verification_queue.csv",
            canonical_id="can_151f3bbf542d",
            fixture_mode=False,
            force=True
        )
    df_obs = pd.read_csv("data/enrichment/price/external/external_price_observations.csv")
    detik_obs = df_obs[df_obs["source_url"].str.contains("detik.com")]
    assert len(detik_obs) == 3

def test_price_text_found_failed(restore_price_data_after_test):
    from unittest.mock import patch
    class MockResponse:
        def __init__(self):
            self.text = "Welcome to Pantai Mutun. Harga tiket masuk Pantai Mutun terbaru 2026 adalah Rp10.000."
            self.status_code = 200
            self.url = "https://travel.detik.com/domestik/d-7301072/pantai-mutun-pantai-pasir-putih-terpopuler-di-pesawaran-lampung"
            self.headers = {"Content-Type": "text/html"}

    with patch("requests.get", return_value=MockResponse()):
        res = run_external_price_verification(
            queue_path="data/enrichment/price/research/external_price_verification_queue.csv",
            canonical_id="can_151f3bbf542d",
            fixture_mode=False,
            force=True
        )
    df_obs = pd.read_csv("data/enrichment/price/external/external_price_observations.csv")
    detik_obs = df_obs[df_obs["source_url"].str.contains("detik.com")]
    assert len(detik_obs) == 0

def test_identity_text_found_failed(restore_price_data_after_test):
    from unittest.mock import patch
    class MockResponse:
        def __init__(self):
            self.text = "Welcome to Pantai. Excerpt: Harga tiket masuk Pantai Mutun terbaru 2026 adalah Rp35.000. Parkir motor Rp5.000. parkir mobil Rp10.000."
            self.status_code = 200
            self.url = "https://travel.detik.com/domestik/d-7301072/pantai-mutun-pantai-pasir-putih-terpopuler-di-pesawaran-lampung"
            self.headers = {"Content-Type": "text/html"}
            
    mock_resp = MockResponse()
    mock_resp.text = mock_resp.text.replace("Mutun", "Other")

    with patch("requests.get", return_value=mock_resp):
        res = run_external_price_verification(
            queue_path="data/enrichment/price/research/external_price_verification_queue.csv",
            canonical_id="can_151f3bbf542d",
            fixture_mode=False,
            force=True
        )
    df_obs = pd.read_csv("data/enrichment/price/external/external_price_observations.csv")
    detik_obs = df_obs[df_obs["source_url"].str.contains("detik.com")]
    assert len(detik_obs) == 0

def test_retrievability_audit_generated(restore_price_data_after_test):
    from unittest.mock import patch
    mock_resp = get_mock_response_for_canary("can_151f3bbf542d")
    with patch("requests.get", return_value=mock_resp):
        run_external_price_verification(
            queue_path="data/enrichment/price/research/external_price_verification_queue.csv",
            canonical_id="can_151f3bbf542d",
            fixture_mode=False,
            force=True
        )
    audit_file = "reports/external_source_retrievability_audit.csv"
    assert os.path.exists(audit_file)
    df_audit = pd.read_csv(audit_file)
    assert len(df_audit) > 0
    assert "source_id" in df_audit.columns
    assert "http_status" in df_audit.columns

def test_custom_final_output_path(restore_price_data_after_test, tmp_path):
    from unittest.mock import patch
    mock_resp = get_mock_response_for_canary("can_151f3bbf542d")
    custom_output = tmp_path / "custom_verified_prices.csv"
    with patch("requests.get", return_value=mock_resp):
        run_external_price_verification(
            queue_path="data/enrichment/price/research/external_price_verification_queue.csv",
            canonical_id="can_151f3bbf542d",
            fixture_mode=False,
            force=True,
            final_output=str(custom_output)
        )
    assert os.path.exists(custom_output)
    df_prices = pd.read_csv(custom_output)
    assert len(df_prices) == 3
