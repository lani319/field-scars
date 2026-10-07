"""Run every check that must pass before a commit: ruff, pytest, clean-room and leak checks.

python tools/gate.py            # leak/copy checks are skipped when their env vars are unset
python tools/gate.py --strict   # …and fail instead of skipping
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(name: str, args: list[str]) -> bool:
    print(f"-- {name}")
    ok = subprocess.run(args, cwd=ROOT).returncode == 0
    print(f"   {'ok' if ok else 'FAILED'}")
    return ok


def main() -> int:
    strict = "--strict" in sys.argv
    py = sys.executable
    results = [
        run("ruff check", [py, "-m", "ruff", "check", "."]),
        run("ruff format", [py, "-m", "ruff", "format", "--check", "."]),
        run("pytest", [py, "-m", "pytest", "-q"]),
    ]
    for var, script in (
        ("FIELDSCARS_COMPARE_DIRS", "check_no_copy.py"),
        ("FIELDSCARS_DENYLIST", "check_domain_leak.py"),
    ):
        if strict and not os.environ.get(var):
            print(f"-- {script}\n   FAILED: {var} is not set (--strict)")
            results.append(False)
            continue
        results.append(run(script, [py, f"tools/{script}"]))
    print("gate: " + ("green" if all(results) else "RED"))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
