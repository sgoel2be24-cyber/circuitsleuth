"""Shared pytest fixtures: temp data dir, demo scenarios, toolbelt factory."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT))

from tools.generate_dataset import SCENARIO_IDS, build_scenario, write_scenario  # noqa: E402


@pytest.fixture(scope="session")
def demo_dir(tmp_path_factory):
    """Generate a fresh synthetic demo set for the test session."""
    d = tmp_path_factory.mktemp("demo")
    for sid in SCENARIO_IDS:
        write_scenario(d, sid)
    return d


@pytest.fixture(scope="session")
def scenario_paths(demo_dir):
    return {sid: demo_dir / sid for sid in SCENARIO_IDS}


def make_state(scenario_dir: Path, budget: int = 12) -> dict:
    view2 = scenario_dir / "view2.png"
    return {
        "id": "test_" + scenario_dir.name,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "status": "created",
        "source": "demo",
        "scenario_id": scenario_dir.name,
        "config": {"max_tool_calls": budget, "max_iterations": 24,
                   "require_independent_view_for_confirm": False},
        "images": {
            "reference": str(scenario_dir / "reference.png"),
            "test": str(scenario_dir / "test.png"),
            "view2": str(view2) if view2.exists() else None,
        },
        "candidates": {},
        "tool_calls_used": 0,
        "iterations": 0,
        "review_requests": [],
        "events": [],
    }


@pytest.fixture()
def run_inspection_fixture():
    from app.agent.orchestrator import run_inspection

    def _run(state: dict) -> dict:
        return asyncio.run(run_inspection(state))

    return _run
