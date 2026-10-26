"""Package Git-tracked source without credentials, runtime data or external datasets.

Run from a committed checkout. Untracked files are deliberately not included.
The manifest records exactly which source commit and files judges receive.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def include_path(name: str, *, runtime: bool = False) -> bool:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        return False
    if any(part in {".git", ".aws", ".venv", "node_modules", "__pycache__", ".pytest_cache"}
           for part in path.parts):
        return False
    if any(part.startswith(".env") and part != ".env.example" for part in path.parts):
        return False
    if name.endswith((".local.json", ".db", ".db-wal", ".db-shm", ".pyc", ".zip")):
        return False
    if name.startswith(("data/runs/", "backend/data/", "frontend/dist/",
                        "research/pipeline-improvements/data/deeppcb/")):
        return False
    if runtime:
        return path.parts[0] in {"backend", "frontend", "tools", "deploy"} or name in {
            ".dockerignore", "LICENSE", "README.md"}
    return True


def package(destination: Path, *, runtime: bool = False) -> dict:
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    files = [name for name in tracked if name and include_path(name, runtime=runtime)]
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT)
    if dirty:
        raise RuntimeError("Commit tracked changes before packaging; manifest must identify the delivered source.")
    manifest = {
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
        "purpose": "aws-runtime" if runtime else "judge-source",
        "excluded": "secrets, local/runtime data, dependency directories, DeepPCB third-party captures",
        "files": {},
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            source = ROOT / name
            if source.is_symlink():
                raise RuntimeError(f"Refusing symlink in source package: {name}")
            data = source.read_bytes()
            manifest["files"][name] = hashlib.sha256(data).hexdigest()
            entry = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, data)
        archive.writestr("SOURCE_MANIFEST.json", json.dumps(manifest, indent=2) + "\n")
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix(destination.suffix + ".sha256").write_text(f"{digest}  {destination.name}\n")
    return {"archive": str(destination), "sha256": digest, "source_commit": manifest["source_commit"],
            "files": len(files), "purpose": manifest["purpose"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--runtime", action="store_true", help="only container build context")
    args = parser.parse_args()
    print(json.dumps(package(args.out.resolve(), runtime=args.runtime), indent=2))


if __name__ == "__main__":
    main()
