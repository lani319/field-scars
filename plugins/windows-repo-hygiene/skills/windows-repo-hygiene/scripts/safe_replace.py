#!/usr/bin/env python3
"""Replace exact text in files without flipping line endings, losing a BOM, or silently matching nothing.

Ad-hoc ``content.replace(old, new)`` scripts fail quietly in three ways on Windows repositories:

* ``old`` is written with ``\\n`` but the file is CRLF - nothing matches, no error, the edit is simply absent;
* ``Path.read_text()`` already turned CRLF into ``\\n``, so writing the result back flips the whole file;
* a UTF-8 BOM is dropped (or added) on the way through.

This tool reads bytes, matches ``old`` in the file's own line-ending style, requires an exact number of
matches, and writes nothing unless every replacement in the batch succeeded.

Replacements come from a JSON file so that no shell ever touches the text (heredocs and PowerShell both
mangle backslashes and quotes)::

    [
      {"file": "src/app.ts", "old": "a\\nb", "new": "a\\nc", "count": 1},
      {"file": "README.md", "old": "v1.2", "new": "v1.3", "count": 2}
    ]

    python safe_replace.py edits.json            # apply
    python safe_replace.py edits.json --dry-run  # validate only, write nothing

``count`` defaults to 1. Exit code: 0 = all applied, 1 = a replacement did not match as required (nothing
was written), 2 = bad input. Standard library only; Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BOM = b"\xef\xbb\xbf"


@dataclass
class Doc:
    path: Path
    bom: bool
    text: str
    eol: str  # "\r\n", "\n", or "mixed"


def load(path: Path) -> Doc:
    raw = path.read_bytes()
    bom = raw.startswith(BOM)
    text = raw[len(BOM) :].decode("utf-8") if bom else raw.decode("utf-8")
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    eol = "mixed" if crlf and lf else "\r\n" if crlf else "\n"
    return Doc(path, bom, text, eol)


def in_style(s: str, eol: str) -> str:
    flat = s.replace("\r\n", "\n")
    return flat.replace("\n", "\r\n") if eol == "\r\n" else flat


class Mismatch(Exception):
    pass


def apply_one(doc: Doc, old: str, new: str, count: int) -> None:
    if not old:
        raise Mismatch("empty 'old' string")
    if doc.eol == "mixed":
        # The file mixes styles: accept exactly one spelling that yields the required count.
        options = {old, in_style(old, "\n"), in_style(old, "\r\n")}
        hits = [(o, doc.text.count(o)) for o in options]
        good = [o for o, n in hits if n == count]
        if len(good) != 1:
            raise Mismatch(f"mixed line endings; matches per spelling: {[n for _, n in hits]}, need {count}")
        o = good[0]
        doc.text = doc.text.replace(o, in_style(new, "\r\n" if "\r\n" in o else "\n"))
        return
    o, n = in_style(old, doc.eol), in_style(new, doc.eol)
    found = doc.text.count(o)
    if found != count:
        raise Mismatch(f"found {found} match(es), need exactly {count}")
    doc.text = doc.text.replace(o, n)


def run(edits: list[dict], base: Path, dry_run: bool) -> int:
    docs: dict[Path, Doc] = {}
    failures = 0
    for i, e in enumerate(edits, 1):
        try:
            path = (base / e["file"]).resolve()
            old, new, count = e["old"], e["new"], int(e.get("count", 1))
        except (KeyError, TypeError, ValueError) as exc:
            print(f"#{i}: bad entry ({exc})")
            return 2
        try:
            doc = docs.get(path) or load(path)
        except (OSError, UnicodeDecodeError) as exc:
            print(f"#{i} {e['file']}: cannot read as UTF-8 ({exc})")
            failures += 1
            continue
        docs[path] = doc
        try:
            apply_one(doc, old, new, count)
            print(f"#{i} {e['file']}: ok")
        except Mismatch as exc:
            print(f"#{i} {e['file']}: FAILED - {exc}")
            failures += 1
    if failures:
        print(f"safe_replace: {failures} failure(s) - nothing was written")
        return 1
    if dry_run:
        print(f"safe_replace: {len(edits)} replacement(s) would apply to {len(docs)} file(s) (dry run)")
        return 0
    for doc in docs.values():
        doc.path.write_bytes((BOM if doc.bom else b"") + doc.text.encode("utf-8"))
    print(f"safe_replace: {len(edits)} replacement(s) applied to {len(docs)} file(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("spec", type=Path, help="JSON list of {file, old, new, count?}")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--base", type=Path, default=Path.cwd(), help="directory that 'file' paths are relative to")
    a = ap.parse_args(argv)
    try:
        edits = json.loads(a.spec.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read spec: {exc}")
        return 2
    if not isinstance(edits, list):
        print("spec must be a JSON list")
        return 2
    return run(edits, a.base, a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
