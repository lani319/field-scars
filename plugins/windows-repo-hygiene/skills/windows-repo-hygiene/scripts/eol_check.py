#!/usr/bin/env python3
"""Catch line-ending flips before they turn a one-line change into a whole-file diff.

A repository without ``.gitattributes`` (and with ``core.autocrlf=false``) keeps whatever bytes you commit.
If a tool rewrites a CRLF file as LF - or the other way round - every line changes, and the real edit
disappears inside the noise. This script compares each changed file's line-ending style with the style
it had at HEAD.

    python eol_check.py              # changed files in the working tree (staged + unstaged) vs HEAD
    python eol_check.py --staged     # only what is staged (use as a pre-commit hook)
    python eol_check.py --fix        # rewrite flipped files back to their HEAD style (content kept)
    python eol_check.py --scan       # inventory: how mixed is this repository, and is it protected?

Exit code: 0 = clean, 1 = flips found (or not fixable), 2 = usage / git error.
Standard library only; Python 3.9+.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):  # Windows consoles default to a legacy code page
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SNIFF = 8000  # bytes inspected for NUL to decide "binary"


def git(*args: str, cwd: Path | None = None, ok_codes: tuple[int, ...] = (0,)) -> bytes:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True)
    if r.returncode not in ok_codes:
        sys.stderr.write(r.stderr.decode("utf-8", "replace"))
        raise SystemExit(2)
    return r.stdout


def style(data: bytes) -> str:
    """'lf' | 'crlf' | 'mixed' | 'none' (no line breaks at all)."""
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    if crlf and lf:
        return "mixed"
    return "crlf" if crlf else "lf" if lf else "none"


def is_binary(data: bytes) -> bool:
    return b"\0" in data[:SNIFF]


def convert(data: bytes, target: str) -> bytes:
    flat = data.replace(b"\r\n", b"\n")
    return flat.replace(b"\n", b"\r\n") if target == "crlf" else flat


@dataclass(frozen=True)
class Finding:
    path: str
    head: str
    now: str

    @property
    def fixable(self) -> bool:
        return self.head in ("lf", "crlf")


def changed_paths(root: Path, staged: bool) -> list[str]:
    args = ["diff", "--name-only", "-z", "--diff-filter=M"]
    args += ["--cached", "HEAD"] if staged else ["HEAD"]
    return [p for p in git(*args, cwd=root).decode("utf-8").split("\0") if p]


def head_blob(root: Path, path: str) -> bytes | None:
    r = subprocess.run(["git", "show", f"HEAD:{path}"], cwd=root, capture_output=True)
    return r.stdout if r.returncode == 0 else None


def current_bytes(root: Path, path: str, staged: bool) -> bytes | None:
    if staged:
        r = subprocess.run(["git", "show", f":{path}"], cwd=root, capture_output=True)
        return r.stdout if r.returncode == 0 else None
    p = root / path
    return p.read_bytes() if p.is_file() else None


def find(root: Path, staged: bool) -> list[Finding]:
    out: list[Finding] = []
    for path in changed_paths(root, staged):
        old, new = head_blob(root, path), current_bytes(root, path, staged)
        if old is None or new is None or is_binary(old) or is_binary(new):
            continue
        h, n = style(old), style(new)
        if h != n and h != "none" and n != "none":
            out.append(Finding(path, h, n))
    return out


def text_attr(root: Path, paths: list[str]) -> dict[str, str]:
    """git's effective `text` attribute per path: 'set', 'unset', 'auto' or 'unspecified'."""
    if not paths:
        return {}
    r = subprocess.run(
        ["git", "check-attr", "-z", "--stdin", "text"], cwd=root, input="\0".join(paths).encode(), capture_output=True
    )
    parts = r.stdout.decode("utf-8").split("\0")
    return {parts[i]: parts[i + 2] for i in range(0, len(parts) - 2, 3)}


def scan(root: Path) -> int:
    paths = [p for p in git("ls-files", "-z", cwd=root).decode("utf-8").split("\0") if p]
    styles: dict[str, str] = {}
    for p in paths:
        f = root / p
        if f.is_file():
            data = f.read_bytes()
            if not is_binary(data):
                styles[p] = style(data)
    autocrlf = git("config", "--get", "core.autocrlf", cwd=root, ok_codes=(0, 1)).decode().strip() or "(unset)"
    attrs = text_attr(root, list(styles))
    # A file is normalised on commit when its `text` attribute is set/auto, or (unspecified) autocrlf is on.
    on = autocrlf in ("true", "input")
    loose = {
        p: s
        for p, s in styles.items()
        if not (attrs.get(p) in ("set", "auto") or (attrs.get(p) == "unspecified" and on))
    }
    by_style = Counter(styles.values())
    by_loose = Counter(loose.values())
    print(f"text files: lf={by_style['lf']} crlf={by_style['crlf']} mixed={by_style['mixed']} none={by_style['none']}")
    print(f"core.autocrlf={autocrlf}  .gitattributes={'present' if (root / '.gitattributes').is_file() else 'absent'}")
    print(f"not normalised by git: {len(loose)} of {len(styles)} text files")
    for p in [p for p, s in styles.items() if s == "mixed"][:20]:
        print(f"  mixed inside one file: {p}")
    if by_loose["lf"] and by_loose["crlf"]:
        print(f"RISK: {by_loose['lf']} LF and {by_loose['crlf']} CRLF files are kept byte-for-byte - any rewrite tool")
        print("      can flip one. Run this script (no flags) before every commit, or normalise with .gitattributes")
        print("      (`* text=auto`) in a commit of its own.")
        return 1
    print("ok: unnormalised files share one line-ending style")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--staged", action="store_true", help="check the index instead of the working tree")
    ap.add_argument("--fix", action="store_true", help="restore the HEAD line-ending style in the working tree")
    ap.add_argument("--scan", action="store_true", help="report the repository's line-ending mix and protection")
    ap.add_argument("--root", type=Path, default=None, help="repository root (default: current repo)")
    a = ap.parse_args(argv)
    root = a.root or Path(git("rev-parse", "--show-toplevel").decode().strip())

    if a.scan:
        return scan(root)

    found = find(root, a.staged)
    if not found:
        print("eol_check: no line-ending flips")
        return 0
    print(f"eol_check: {len(found)} file(s) changed line-ending style - their diff will be the whole file:")
    for f in found:
        print(f"  {f.path}: HEAD={f.head} -> now={f.now}")
    if not a.fix:
        print("\nIf this was an accident: python eol_check.py --fix")
        print("If you meant to normalise line endings: commit that alone, never mixed with a real change.")
        return 1
    stuck = []
    for f in found:
        if not f.fixable:
            stuck.append(f.path)
            continue
        p = root / f.path
        p.write_bytes(convert(p.read_bytes(), f.head))
        print(f"  restored {f.head}: {f.path}")
    if a.staged:
        print("Fixed in the working tree - run `git add` again for these files.")
    if stuck:
        print("HEAD itself was mixed, so the original style is ambiguous - decide by hand: " + ", ".join(stuck))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
