"""Unit and smoke tests for the secure Apify Google Maps batch runner."""
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.apify_runner import ApifyBatchRunner, ApifyRunnerError
import run_apify


class FakeResponse:
    def __init__(self, payload, status_code=200, content=None):
        self._payload = payload
        self.status_code = status_code
        self.content = content
        self.text = json.dumps(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeClient:
    def __init__(self, run_status="SUCCEEDED", fail_auth=False):
        self.calls = []
        self.run_status = run_status
        self.fail_auth = fail_auth

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        if self.fail_auth:
            return FakeResponse({"error": "Invalid token"}, status_code=401)
        if url.endswith("/users/me"):
            return FakeResponse({"data": {"username": "test-user", "email": "test@example.com"}})
        if "/actor-runs/" in url:
            return FakeResponse({"data": {"id": "run-1", "status": self.run_status, "defaultDatasetId": "dataset-1"}})
        if "/datasets/" in url:
            payload = [{"title": "Test Place", "placeId": "ChIJtest123", "location": {"lat": -5.4, "lng": 105.2}}]
            return FakeResponse(payload, content=json.dumps(payload).encode("utf-8"))
        raise AssertionError(f"Unexpected GET URL: {url}")

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        if self.fail_auth:
            return FakeResponse({"error": "Invalid token"}, status_code=401)
        return FakeResponse({"data": {"id": "run-1", "status": "RUNNING"}})

    def close(self):
        pass


def _fixture_root(tmp_path: Path):
    root = tmp_path / "config" / "apify_batches"
    (root / "v1.0" / "batch-01").mkdir(parents=True)
    batch1 = root / "v1.0" / "batch-01" / "discovery-test1.v1.0.json"
    batch2 = root / "v1.0" / "batch-01" / "discovery-test2.v1.0.json"
    batch1.write_text(json.dumps({"language": "id", "locationQuery": "Lampung", "maxImages": 0}))
    batch2.write_text(json.dumps({"language": "id", "locationQuery": "Metro", "maxImages": 0}))
    (root / "index.csv").write_text(
        "version,batch,file,kind,region_id,location_or_ids\n"
        "v1.0,batch-01,v1.0/batch-01/discovery-test1.v1.0.json,discovery,test_region1,Lampung\n"
        "v1.0,batch-01,v1.0/batch-01/discovery-test2.v1.0.json,discovery,test_region2,Metro\n"
    )
    return root, batch1


def test_dry_run_does_not_contact_apify(tmp_path):
    root, _ = _fixture_root(tmp_path)
    client = FakeClient()
    runner = ApifyBatchRunner(root, tmp_path / "out", http_client=client)
    targets = runner.targets(batch="batch-01")
    assert len(targets) == 2
    result = runner.dry_run(targets)
    assert len(result) == 2
    assert result[0]["would_contact_apify"] is False
    assert result[1]["would_contact_apify"] is False
    assert client.calls == []


def test_token_never_required_from_input_or_printed(tmp_path, monkeypatch):
    root, batch = _fixture_root(tmp_path)
    batch.write_text(json.dumps({"token": "do-not-allow"}))
    runner = ApifyBatchRunner(root, tmp_path / "out")
    with pytest.raises(ApifyRunnerError, match="Secret-like"):
        runner.dry_run(runner.targets(file="v1.0/batch-01/discovery-test1.v1.0.json"))
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    with pytest.raises(ApifyRunnerError, match="interactive prompt disabled"):
        runner.token_from_environment_or_prompt(prompt=False)


def test_token_retrieval_env_and_prompt(monkeypatch):
    # 1. From environment
    monkeypatch.setenv("APIFY_TOKEN", "env-secret-token")
    runner = ApifyBatchRunner()
    assert runner.token_from_environment_or_prompt(prompt=False) == "env-secret-token"

    # 2. From prompt
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    with patch("getpass.getpass", return_value="prompted-secret-token"):
        assert runner.token_from_environment_or_prompt(prompt=True) == "prompted-secret-token"

    # 3. Empty input in prompt raises
    with patch("getpass.getpass", return_value="   "):
        with pytest.raises(ApifyRunnerError, match="token is required"):
            runner.token_from_environment_or_prompt(prompt=True)


def test_token_verification(tmp_path):
    root, _ = _fixture_root(tmp_path)
    client_ok = FakeClient()
    runner_ok = ApifyBatchRunner(root, tmp_path / "out", http_client=client_ok)
    info = runner_ok.verify_token("valid-token")
    assert info["username"] == "test-user"
    assert info["email"] == "test@example.com"

    client_bad = FakeClient(fail_auth=True)
    runner_bad = ApifyBatchRunner(root, tmp_path / "out", http_client=client_bad)
    with pytest.raises(ApifyRunnerError, match="request failed"):
        runner_bad.verify_token("invalid-token")


def test_mock_run_writes_metadata_checksum_and_imports(tmp_path):
    root, _ = _fixture_root(tmp_path)
    client = FakeClient()
    imported = []

    class FakeImporter:
        def import_dataset(self, path):
            imported.append(path)
            return {"valid_count": 1, "failed_count": 0, "is_skipped": False}

    runner = ApifyBatchRunner(
        root, tmp_path / "out", http_client=client,
        importer_factory=FakeImporter, poll_interval=0
    )
    spec, path = runner.targets(file="v1.0/batch-01/discovery-test1.v1.0.json")[0]
    result = runner.run_file(spec, path, "secret-token", import_after=True)

    places = Path(result["places_path"])
    assert places.exists()
    dataset_records = json.loads(places.read_text(encoding="utf-8"))
    assert dataset_records[0]["title"] == "Test Place"
    assert dataset_records[0]["placeId"] == "ChIJtest123"

    run_json = places.parent / "run.json"
    assert run_json.exists()
    run_meta = json.loads(run_json.read_text(encoding="utf-8"))
    assert run_meta["actor"] == "compass/crawler-google-places"
    assert run_meta["run_id"] == "run-1"
    assert run_meta["dataset_id"] == "dataset-1"
    assert run_meta["status"] == "SUCCEEDED"

    checksum_file = places.parent / "checksums.sha256"
    assert checksum_file.exists()
    checksum_line = checksum_file.read_text(encoding="utf-8").strip()
    sha256_hash, filename = checksum_line.split()
    assert filename == "places.json"
    expected_hash = hashlib.sha256(places.read_bytes()).hexdigest()
    assert sha256_hash == expected_hash
    assert run_meta["places_sha256"] == expected_hash

    # Importer invoked
    assert imported == [str(places)]
    assert result["imported"]["valid_count"] == 1

    # Token hygiene: secret-token should never appear in files or metadata
    assert "secret-token" not in run_json.read_text()
    assert "secret-token" not in checksum_file.read_text()


def test_mock_run_without_import(tmp_path):
    root, _ = _fixture_root(tmp_path)
    client = FakeClient()
    runner = ApifyBatchRunner(root, tmp_path / "out", http_client=client, poll_interval=0)
    spec, path = runner.targets(file="v1.0/batch-01/discovery-test1.v1.0.json")[0]
    result = runner.run_file(spec, path, "secret-token", import_after=False)
    assert result["imported"] is None
    assert Path(result["places_path"]).exists()


def test_mock_run_failed_status(tmp_path):
    root, _ = _fixture_root(tmp_path)
    client = FakeClient(run_status="FAILED")
    runner = ApifyBatchRunner(root, tmp_path / "out", http_client=client, poll_interval=0)
    spec, path = runner.targets(file="v1.0/batch-01/discovery-test1.v1.0.json")[0]
    with pytest.raises(ApifyRunnerError, match="ended with status FAILED"):
        runner.run_file(spec, path, "secret-token")


def test_file_must_be_indexed(tmp_path):
    root, _ = _fixture_root(tmp_path)
    runner = ApifyBatchRunner(root, tmp_path / "out")
    with pytest.raises(ApifyRunnerError, match="authoritative"):
        runner.targets(file="v1.0/batch-01/not-indexed.json")


def test_batch_resolution(tmp_path):
    root, _ = _fixture_root(tmp_path)
    runner = ApifyBatchRunner(root, tmp_path / "out")
    targets = runner.targets(batch="batch-01")
    assert len(targets) == 2
    assert {spec.region_id for spec, _ in targets} == {"test_region1", "test_region2"}


def test_all_real_v1_batches_dry_run_clean():
    """Smoke test over all actual versioned batch JSON files committed in the repo."""
    scraping_root = Path(__file__).resolve().parent.parent
    batches_root = scraping_root / "config" / "apify_batches"
    runner = ApifyBatchRunner(
        batches_root=batches_root,
        output_root=scraping_root / "data" / "raw" / "apify" / "google_maps",
    )
    all_specs = runner.list_batches()
    assert len(all_specs) == 47  # Exact count in index.csv
    targets = [(spec, runner.resolve_file(spec.file)[1]) for spec in all_specs]
    planned = runner.dry_run(targets)
    assert len(planned) == 47
    for p in planned:
        assert p["actor"] == "compass/crawler-google-places"
        assert p["would_contact_apify"] is False
        assert len(p["input_keys"]) > 0


def test_cli_main_dry_run_and_list(capsys):
    scraping_root = Path(__file__).resolve().parent.parent
    batches_root = str(scraping_root / "config" / "apify_batches")

    # 1. List batches
    rc = run_apify.main(["--list-batches", "--batches-root", batches_root])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Authoritative index contains 47 file(s)" in captured.out

    # 2. Dry-run canary file
    rc = run_apify.main([
        "--dry-run",
        "--file",
        "v1.0/batch-01-canary/discovery-bandar_lampung-canary.v1.0.json",
        "--batches-root",
        batches_root,
    ])
    assert rc == 0
    captured = capsys.readouterr()
    assert "[DRY RUN] 1 target(s) validated successfully" in captured.out
    assert "compass/crawler-google-places" in captured.out


def test_token_from_file_valid(tmp_path):
    token_file = tmp_path / ".apify-tokens"
    token_file.write_text(
        "# Account tokens for Apify\n"
        "token-account-0\n"
        "\n"
        "   token-account-1   \n"
        "# Comment line\n"
        "token-account-2\n",
        encoding="utf-8",
    )

    # Default index 0
    assert ApifyBatchRunner.token_from_file(token_file) == "token-account-0"
    # Explicit indices
    assert ApifyBatchRunner.token_from_file(token_file, token_index=0) == "token-account-0"
    assert ApifyBatchRunner.token_from_file(token_file, token_index=1) == "token-account-1"
    assert ApifyBatchRunner.token_from_file(token_file, token_index=2) == "token-account-2"


def test_token_from_file_errors(tmp_path):
    token_file = tmp_path / ".apify-tokens"
    token_file.write_text("token-alpha\ntoken-beta\n", encoding="utf-8")

    # Negative index
    with pytest.raises(ApifyRunnerError, match="out of range"):
        ApifyBatchRunner.token_from_file(token_file, token_index=-1)

    # Index equal to length
    with pytest.raises(ApifyRunnerError, match="out of range \\(file contains 2 token\\(s\\)\\)"):
        ApifyBatchRunner.token_from_file(token_file, token_index=2)

    # Non-existent file
    with pytest.raises(ApifyRunnerError, match="Token file not found"):
        ApifyBatchRunner.token_from_file(tmp_path / "non-existent")

    # Empty file
    empty_file = tmp_path / "empty-tokens"
    empty_file.write_text("\n   \n# comment\n", encoding="utf-8")
    with pytest.raises(ApifyRunnerError, match="No valid tokens found"):
        ApifyBatchRunner.token_from_file(empty_file)


def test_token_from_environment_or_prompt_with_file(tmp_path, monkeypatch):
    token_file = tmp_path / ".apify-tokens"
    token_file.write_text("file-token-0\nfile-token-1\n", encoding="utf-8")

    runner = ApifyBatchRunner()

    # Token file takes precedence over environment variable
    monkeypatch.setenv("APIFY_TOKEN", "env-secret-token")
    assert runner.token_from_environment_or_prompt(token_file=token_file, token_index=0) == "file-token-0"
    assert runner.token_from_environment_or_prompt(token_file=token_file, token_index=1) == "file-token-1"

    # Token index without token file raises error
    with pytest.raises(ApifyRunnerError, match="--token-index requires --token-file"):
        runner.token_from_environment_or_prompt(token_file=None, token_index=1)


def test_cli_main_verify_token_with_token_file(tmp_path, capsys, monkeypatch):
    token_file = tmp_path / ".apify-tokens"
    token_file.write_text("tok-user-0\ntok-user-1\n", encoding="utf-8")

    class CapturingClient(FakeClient):
        def __init__(self):
            super().__init__()
            self.verified_tokens = []

        def get(self, url, **kwargs):
            return super().get(url, **kwargs)

    client = CapturingClient()
    monkeypatch.setattr("src.apify_runner.httpx.Client", lambda *args, **kwargs: client)

    rc = run_apify.main([
        "--verify-token",
        "--token-file",
        str(token_file),
        "--token-index",
        "1",
    ])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Token verified successfully. User: test-user" in captured.out
    # Token value must never be printed to stdout or stderr
    assert "tok-user-0" not in captured.out
    assert "tok-user-1" not in captured.out
    assert "tok-user" not in captured.err


def test_cli_main_token_file_missing_fails_safely(tmp_path, capsys):
    rc = run_apify.main([
        "--verify-token",
        "--token-file",
        str(tmp_path / "does_not_exist"),
    ])
    assert rc == 1
    captured = capsys.readouterr()
    assert "Error: Token file not found" in captured.err


def test_cli_typer_run_apify_token_file(tmp_path, monkeypatch):
    from typer.testing import CliRunner
    from src.cli import app

    token_file = tmp_path / ".apify-tokens"
    token_file.write_text("typer-tok-0\ntyper-tok-1\n", encoding="utf-8")

    client = FakeClient()
    monkeypatch.setattr("src.apify_runner.httpx.Client", lambda *args, **kwargs: client)

    runner = CliRunner()
    result = runner.invoke(app, [
        "run-apify",
        "--verify-token",
        "--token-file",
        str(token_file),
        "--token-index",
        "1",
    ])
    assert result.exit_code == 0
    assert "Token verified successfully" in result.output
    # Secret must never be in CLI output
    assert "typer-tok" not in result.output

