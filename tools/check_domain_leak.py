"""Leak check: no forbidden identifier (client, product, person, host names) appears in tracked text.

Reads one term per line from the file in ``FIELDSCARS_DENYLIST`` (kept outside the repository; ``#`` starts a
comment). ASCII terms match on word boundaries and ignore case; other terms match as substrings.

    FIELDSCARS_DENYLIST=/path/denylist.txt python tools/check_domain_leak.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _terms(path: Path) -> list[str]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        t = line.split("#", 1)[0].strip()
        if t:
            out.append(t)
    return out


def _pattern(term: str) -> re.Pattern[str]:
    if re.fullmatch(r"[\x20-\x7e]+", term):
        return re.compile(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", re.IGNORECASE)
    return re.compile(re.escape(term))


def _tracked() -> list[Path]:
    """Files git would commit (tracked + untracked, minus ignored)."""
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    return [ROOT / p for p in out.splitlines() if p]


def main() -> int:
    deny = os.environ.get("FIELDSCARS_DENYLIST", "")
    if not deny:
        print("check_domain_leak: FIELDSCARS_DENYLIST not set — skipped")
        return 0
    pats = [(t, _pattern(t)) for t in _terms(Path(deny))]
    bad = 0
    files = _tracked()
    for f in files:
        rel = f.relative_to(ROOT).as_posix()
        for term, pat in pats:
            if pat.search(rel):
                print(f"PATH  {rel}: {term!r}")
                bad += 1
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary (video, images) — names in binaries are covered by the path check
        for no, line in enumerate(text.splitlines(), 1):
            for term, pat in pats:
                if pat.search(line):
                    print(f"TEXT  {rel}:{no}: {term!r}")
                    bad += 1
    print(f"check_domain_leak: {len(files)} files, {len(pats)} terms, {bad} hit(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
