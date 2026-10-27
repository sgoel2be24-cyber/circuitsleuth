"""Verify the whole-state writer lock across separate OS processes."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app import store


def test_writer_lock_rejects_another_process_and_releases_after_error(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "settings", store.settings.__class__(data_dir=tmp_path))
    code = """
from app import store
try:
    with store.mutation_lock('ins_locktest'):
        print('acquired')
except store.InspectionBusyError:
    print('busy')
"""
    env = {**os.environ, "CIRCUITSLEUTH_DATA_DIR": str(tmp_path),
           "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    def attempt():
        result = subprocess.run([sys.executable, "-c", code], env=env,
                                capture_output=True, text=True, timeout=20, check=True)
        return result.stdout.strip()

    with pytest.raises(ValueError):
        with store.mutation_lock("ins_locktest"):
            assert attempt() == "busy"
            raise ValueError("injected failure")
    assert attempt() == "acquired"
