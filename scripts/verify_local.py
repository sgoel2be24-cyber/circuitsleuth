r"""Portable local checks; invoke with the project's virtual-environment Python.

Usage: .venv/bin/python scripts/verify_local.py --include-mcp
Windows: .venv\Scripts\python.exe scripts/verify_local.py --include-mcp
Tests use temporary storage. No API server or cloud account is required.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-mcp", action="store_true", help="also exercise all eight tools over stdio")
    args = parser.parse_args()
    npm = shutil.which("npm")
    if npm is None:
        parser.error("npm is required; install Node and run npm ci in frontend first")
    if importlib.util.find_spec("pip") is not None:
        dependency_check = [sys.executable, "-m", "pip", "check"]
    elif uv := shutil.which("uv"):
        dependency_check = [uv, "pip", "check", "--python", sys.executable]
    else:
        parser.error("install pip in the virtual environment to check dependencies")

    with tempfile.TemporaryDirectory(prefix="circuitsleuth-verify-") as temporary:
        env = {**os.environ, "CIRCUITSLEUTH_DATA_DIR": temporary}

        def run(command: list[str], cwd: Path = ROOT) -> None:
            print("Checking:", " ".join(command), flush=True)
            subprocess.run(command, cwd=cwd, env=env, check=True)

        run(dependency_check)
        run([sys.executable, "-c", "import cv2; print('OpenCV', cv2.__version__); "
             "assert cv2.__version__.startswith('5.'), 'OpenCV 5 is required'"])
        run([sys.executable, "-m", "pytest", "backend/tests", "-q"])
        run([npm, "run", "lint"], ROOT / "frontend")
        run([npm, "run", "build"], ROOT / "frontend")
        if args.include_mcp:
            run([sys.executable, "tools/mcp_smoke_test.py"])
    print("Local checks passed. Container and AWS execution were not checked.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from None
