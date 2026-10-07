"""Clean-room check: no file in this repository shares text with a reference code base.

Compares every text file here against the files under each directory in ``FIELDSCARS_COMPARE_DIRS``
(os.pathsep-separated; kept outside the repository). A file fails when it is identical to a reference file,
or when any run of 8 consecutive meaningful lines matches.

    FIELDSCARS_COMPARE_DIRS=/path/a:/path/b python tools/check_no_copy.py
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = {".ps1", ".sh", ".py", ".js", ".css", ".html", ".md", ".yaml", ".yml", ".json", ".txt", ".toml"}
SKIP = {".git", ".venv", "node_modules", "__pycache__", "build", "out"}
WINDOW = 8


def _files(base: Path) -> list[Path]:
    return [
        p
        for p in base.rglob("*")
        if p.is_file() and p.suffix.lower() in EXT and not any(s in SKIP for s in p.relative_to(base).parts)
    ]


def _lines(p: Path) -> list[str]:
    try:
        text = p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    out = []
    for ln in text.splitlines():
        s = re.sub(r"\s+", " ", ln).strip()
        if len(s) >= 12 and not re.fullmatch(r"[\W_]+", s):  # skip blank, short and punctuation-only lines
            out.append(s)
    return out


def _shingles(lines: list[str]) -> set[str]:
    return {hashlib.sha1("\n".join(lines[i : i + WINDOW]).encode()).hexdigest() for i in range(len(lines) - WINDOW + 1)}


def main() -> int:
    dirs = [Path(d) for d in os.environ.get("FIELDSCARS_COMPARE_DIRS", "").split(os.pathsep) if d.strip()]
    if not dirs:
        print("check_no_copy: FIELDSCARS_COMPARE_DIRS not set — skipped")
        return 0
    ref_hash: dict[str, Path] = {}
    ref_sh: dict[str, Path] = {}
    for d in dirs:
        for f in _files(d):
            ref_hash[hashlib.sha1(f.read_bytes()).hexdigest()] = f
            for s in _shingles(_lines(f)):
                ref_sh[s] = f
    bad = 0
    for f in _files(ROOT):
        rel = f.relative_to(ROOT)
        h = hashlib.sha1(f.read_bytes()).hexdigest()
        if h in ref_hash:
            print(f"IDENTICAL  {rel}  ==  {ref_hash[h]}")
            bad += 1
            continue
        hits = {ref_sh[s] for s in _shingles(_lines(f)) if s in ref_sh}
        if hits:
            print(f"OVERLAP    {rel}  ~  {', '.join(str(h) for h in sorted(hits))}")
            bad += 1
    print(f"check_no_copy: {len(_files(ROOT))} files, {bad} problem(s) against {len(ref_hash)} reference files")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
