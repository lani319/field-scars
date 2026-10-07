from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for skill in ("windows-repo-hygiene", "silent-wrong-answer"):
    sys.path.insert(0, str(ROOT / "plugins" / skill / "skills" / skill / "scripts"))


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty git repository with autocrlf off (bytes in == bytes committed), as the cwd."""
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "core.autocrlf", "false")
    git(tmp_path, "config", "user.name", "t")
    git(tmp_path, "config", "user.email", "t@example.com")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def commit(repo: Path, files: dict[str, bytes]) -> None:
    for name, data in files.items():
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "c")
