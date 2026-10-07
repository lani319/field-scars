#!/usr/bin/env python3
"""Find byte-order-mark and encoding problems that only show up as baffling errors somewhere else.

Rules
  PS_NEEDS_BOM   .ps1/.psm1/.psd1 with non-ASCII text but no BOM. Windows PowerShell 5.1 reads such a file in
                 the legacy ANSI code page; multi-byte characters swallow the next quote and the parser reports
                 nonsense ("missing terminator", "unexpected token") on unrelated lines.
  PS_BOM_COMMENTS  the same, but the non-ASCII text is only in comments: it parses today and breaks the day
                 someone puts non-ASCII text in a string. Reported as a warning; --fix adds the BOM.
  MUST_NOT_BOM   UTF-8 BOM in files whose readers choke on it: shell scripts and anything starting with a
                 shebang, .json, .env files, nginx configs.
  NOT_UTF8       text that does not decode as UTF-8 (and has no UTF-16 BOM) - usually saved in a legacy code
                 page by an old editor. Reported as a warning.

    python encoding_check.py              # every tracked file
    python encoding_check.py a.ps1 b.json # just these
    python encoding_check.py --fix        # add / strip BOMs (never re-encodes NOT_UTF8 files)
    python encoding_check.py --strict     # warnings fail too

Exit code: 0 = clean, 1 = problems. Standard library only; Python 3.9+.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

UTF8_BOM = b"\xef\xbb\xbf"
UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")
PS_SUFFIXES = {".ps1", ".psm1", ".psd1"}
NO_BOM_SUFFIXES = {".sh", ".bash", ".zsh", ".json", ".env"}


def is_binary(data: bytes) -> bool:
    return b"\0" in data[:8000] and not data.startswith(UTF16_BOMS)


def must_not_have_bom(path: Path, body: bytes) -> bool:
    name = path.name.lower()
    if path.suffix.lower() in NO_BOM_SUFFIXES or name.startswith(".env"):
        return True
    if name == "nginx.conf" or (path.suffix.lower() == ".conf" and "nginx" in (p.lower() for p in path.parts)):
        return True
    return body.startswith(b"#!")


def strip_ps_comments(text: str) -> str:
    """Remove <# block #> and # line comments (approximate: a # inside a quoted string also starts a comment)."""
    text = re.sub(r"<#.*?#>", "", text, flags=re.S)
    return "\n".join(re.sub(r"(^|\s)#.*$", "", line) for line in text.splitlines())


def check(path: Path, data: bytes) -> tuple[str, str] | None:
    """Return (rule, message) or None."""
    if not data or is_binary(data):
        return None
    if data.startswith(UTF16_BOMS):
        return None  # UTF-16 with BOM is unambiguous; PowerShell reads it fine
    has_bom = data.startswith(UTF8_BOM)
    body = data[3:] if has_bom else data
    try:
        body.decode("utf-8")
    except UnicodeDecodeError:
        return ("NOT_UTF8", "not valid UTF-8 - probably a legacy code page; re-save as UTF-8 deliberately")
    if path.suffix.lower() in PS_SUFFIXES and not has_bom and any(b > 0x7F for b in body):
        if not any(ord(c) > 0x7F for c in strip_ps_comments(body.decode("utf-8"))):
            return (
                "PS_BOM_COMMENTS",
                "non-ASCII only in comments - parses today, breaks once a quoted string gets non-ASCII text",
            )
        return ("PS_NEEDS_BOM", "non-ASCII text without BOM - Windows PowerShell 5.1 will mis-read it")
    if has_bom and must_not_have_bom(path, body):
        return ("MUST_NOT_BOM", "UTF-8 BOM in a file whose reader rejects or mis-parses it")
    return None


def tracked(root: Path) -> list[Path]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True).stdout
    return [root / p for p in out.decode("utf-8").split("\0") if p]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="*", type=Path)
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args(argv)
    files = a.paths or tracked(Path.cwd())
    errors = warnings = 0
    for f in files:
        if not f.is_file():
            continue
        data = f.read_bytes()
        hit = check(f, data)
        if not hit:
            continue
        rule, msg = hit
        fixed = ""
        if a.fix and rule in ("PS_NEEDS_BOM", "PS_BOM_COMMENTS"):
            f.write_bytes(UTF8_BOM + data)
            fixed = "  [fixed: BOM added]"
        elif a.fix and rule == "MUST_NOT_BOM":
            f.write_bytes(data[3:])
            fixed = "  [fixed: BOM removed]"
        print(f"{rule:13} {f}: {msg}{fixed}")
        if fixed:
            continue
        if rule in ("NOT_UTF8", "PS_BOM_COMMENTS"):
            warnings += 1
        else:
            errors += 1
    print(f"encoding_check: {len(files)} file(s), {errors} error(s), {warnings} warning(s)")
    return 1 if errors or (a.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
