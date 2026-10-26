"""Prevent private runtime state and third-party captures entering judge bundles."""
import pytest

from tools.package_submission import include_path


@pytest.mark.parametrize("name", [
    ".env", "backend/.env.production", ".aws/credentials", "data/runs/abc/state.json",
    "data/circuitsleuth.db-wal", "deploy/credentials.local.json", "frontend/node_modules/x/index.js",
    "research/pipeline-improvements/data/deeppcb/00041200_test.jpg", "../secret", "/etc/passwd",
])
def test_sensitive_and_restricted_files_are_excluded(name):
    assert not include_path(name)


def test_original_synthetic_data_and_research_results_remain_available():
    assert include_path("data/demo/scenario_01_clear_defects/reference.png")
    assert include_path("research/pipeline-improvements/results/deeppcb-smoke.json")
    assert include_path(".env.example")


def test_cloud_build_context_is_minimal():
    assert include_path("deploy/Dockerfile", runtime=True)
    assert include_path("backend/requirements.lock.txt", runtime=True)
    assert not include_path("research/pipeline-improvements/REPORT.md", runtime=True)
    assert not include_path("output/inspection/report.json", runtime=True)
