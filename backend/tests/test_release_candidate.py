from pathlib import Path

from oryven import __version__
from oryven.api import create_app
from oryven.release_info import BUILD_TARGET, RELEASE_CHANNEL, VERSION
from fastapi.testclient import TestClient


def test_release_metadata_single_source_of_truth():
    assert VERSION == "0.19.1"
    assert __version__ == VERSION
    assert RELEASE_CHANNEL == "production-activation"
    assert BUILD_TARGET == "windows-desktop"


def test_health_reports_release_candidate(tmp_path, monkeypatch):
    monkeypatch.setenv("ORYVEN_DATA_DIR", str(tmp_path))
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == VERSION
        assert data["release_channel"] == RELEASE_CHANNEL
        assert data["build_target"] == BUILD_TARGET


def test_windows_release_files_are_version_aligned():
    root = Path(__file__).resolve().parents[2]
    for rel in [
        "web/package.json",
        "web/src-tauri/Cargo.toml",
        "web/src-tauri/tauri.conf.json",
        "scripts/build-release-windows.ps1",
    ]:
        assert VERSION in (root / rel).read_text(encoding="utf-8")
