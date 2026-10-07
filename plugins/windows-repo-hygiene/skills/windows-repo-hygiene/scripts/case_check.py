#!/usr/bin/env python3
"""Find letter-case problems that a case-insensitive file system hides until a clean build elsewhere fails.

Checks (the git index is the source of truth - it is what a fresh checkout on Linux/CI receives):
  COLLISION   two tracked paths that differ only by case (``src/Grid/a.ts`` and ``src/grid/b.ts``). On Windows
              and macOS they land in one folder; on Linux they are two.
  DISK        a tracked path whose casing on this disk differs from the index. Typical cause: someone renamed
              ``grid`` -> ``Grid`` and you pulled - git on a case-insensitive file system does not rename the
              folder for you.
  IMPORT      a relative JS/TS import whose casing differs from the tracked file (``./Grid/Table`` vs
              ``grid/Table.tsx``). Builds pass locally, then fail in CI with "file name differs only in casing".
              Incremental build caches can hide this locally - delete them before trusting a green build.

    python case_check.py            # all checks
    python case_check.py --no-disk  # skip the disk walk (e.g. in CI)

Exit code: 0 = clean, 1 = problems. Standard library only; Python 3.9+.
"""

from __future__ import annotations

import argparse
import os
import posixpath
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SOURCE_EXT = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte")
RESOLVE_EXT = ("", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte", ".json", ".css", ".scss")
IMPORT_RE = re.compile(
    r"""(?:\bfrom\s+|\bimport\s*\(\s*|\brequire\s*\(\s*|\bimport\s+)(['"])(\.{1,2}/[^'"]*)\1""",
)


def tracked(root: Path) -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def prefixes(path: str) -> list[str]:
    parts = path.split("/")
    return ["/".join(parts[: i + 1]) for i in range(len(parts))]


def collisions(paths: list[str]) -> list[str]:
    seen: dict[str, set[str]] = defaultdict(set)
    for p in paths:
        for pre in prefixes(p):
            seen[pre.lower()].add(pre)
    return [" <-> ".join(sorted(v)) for v in seen.values() if len(v) > 1]


def disk_mismatches(root: Path, paths: list[str]) -> list[str]:
    listing: dict[str, dict[str, str]] = {}

    def names(d: str) -> dict[str, str]:
        if d not in listing:
            try:
                listing[d] = {n.lower(): n for n in os.listdir(root / d if d else root)}
            except OSError:
                listing[d] = {}
        return listing[d]

    bad: set[str] = set()
    for p in paths:
        parent = ""
        for seg in p.split("/"):
            actual = names(parent).get(seg.lower())
            if actual is None:
                break  # missing on disk (deleted, sparse checkout) - not a casing issue
            if actual != seg:
                shown = posixpath.join(parent, actual)
                bad.add(f"index has {posixpath.join(parent, seg)!r}, disk has {shown!r}")
                break
            parent = posixpath.join(parent, seg) if parent else seg
    return sorted(bad)


def import_mismatches(root: Path, paths: list[str]) -> list[str]:
    exact = set(paths)
    lower = {p.lower(): p for p in paths}
    bad = []
    for src in paths:
        if not src.endswith(SOURCE_EXT):
            continue
        try:
            text = (root / src).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        base = posixpath.dirname(src)
        for no, line in enumerate(text.splitlines(), 1):
            for m in IMPORT_RE.finditer(line):
                spec = m.group(2).split("?")[0]
                target = posixpath.normpath(posixpath.join(base, spec))
                cands = [target + e for e in RESOLVE_EXT] + [f"{target}/index{e}" for e in RESOLVE_EXT[1:]]
                if any(c in exact for c in cands):
                    continue
                hit = next((lower[c.lower()] for c in cands if c.lower() in lower), None)
                if hit:
                    bad.append(f"{src}:{no}: imports {spec!r} but the tracked file is {hit!r}")
    return bad


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--no-disk", action="store_true", help="skip comparing the index with the disk")
    a = ap.parse_args(argv)
    paths = tracked(a.root)
    groups = [("COLLISION", collisions(paths)), ("IMPORT", import_mismatches(a.root, paths))]
    if not a.no_disk:
        groups.append(("DISK", disk_mismatches(a.root, paths)))
    total = 0
    for rule, items in groups:
        for it in items:
            print(f"{rule:9} {it}")
        total += len(items)
    if any(r == "DISK" and items for r, items in groups):
        print("\nFix a DISK mismatch with a two-step rename: git mv x x_tmp && git mv x_tmp X (or ren on disk).")
    print(f"case_check: {len(paths)} tracked path(s), {total} problem(s)")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
