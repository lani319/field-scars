---
name: windows-repo-hygiene
description: Prevents and diagnoses the quiet file-level failures of Windows and mixed-OS repositories - line endings flipping a whole file, scripted replacements that match nothing, PowerShell 5.1 mis-reading non-ASCII scripts, BOMs breaking JSON/shell/nginx, and letter-case renames that pass locally but fail on CI. Use before rewriting files with a script, before committing on Windows, when a one-line change shows a whole-file diff, when PowerShell reports parse errors on lines that look fine, when Korean/CJK text turns to mojibake, or when a build fails only on a clean checkout. Triggers also on "줄바꿈", "CRLF", "EOL", "BOM", "인코딩 깨짐", "대소문자", "diff 가 파일 전체".
---

# Windows repo hygiene

These failures share one property: **nothing errors at the moment of the mistake.** The diff balloons later, the
parser complains about a different line, the build breaks on someone else's machine. So the skill is mostly about
running a cheap mechanical check at the right moment instead of trusting that "it looked fine".

Scripts live in `scripts/` next to this file. All are standard-library Python 3.9+, work from any directory inside
the target repository, and exit non-zero when they find something - safe to chain in hooks and CI.

| Script | Catches |
|---|---|
| `eol_check.py` | a changed file whose line-ending style differs from HEAD (`--fix` restores it, `--scan` rates the repo) |
| `safe_replace.py` | scripted replacements that would match nothing, flip EOL, or drop a BOM - all-or-nothing batch |
| `encoding_check.py` | non-ASCII `.ps1` without BOM; BOM in JSON / shell / `.env` / nginx; non-UTF-8 text |
| `case_check.py` | case-only path collisions, index-vs-disk casing drift, JS/TS imports with the wrong casing |

## When to act

**Starting work in an unfamiliar repo on Windows** - run `python scripts/eol_check.py --scan` once. If it prints
`RISK` (both LF and CRLF committed, no `.gitattributes`), every rewrite you make can flip a file; keep the rest of
this skill in mind for the whole session.

**About to edit files with a script** (bulk rename, codemod, version bump) - prefer the editor/Edit tool for a few
edits: it preserves bytes. For scripted edits use `safe_replace.py` with a JSON spec instead of an inline
`str.replace` script. If you must write your own script:

- read and write **bytes** (`read_bytes`/`write_bytes`). `read_text()` translates CRLF to `\n` on read, so
  `newline=""` on the write side cannot save you - the information is already gone;
- `assert old in data` **for every replacement**, and write only after all of them passed. A batch where only some
  replacements are asserted leaks exactly through the unasserted ones;
- never pass code containing backslashes through a shell heredoc or a PowerShell string; write it with a file tool.

**Before committing** - run, in order:

```
python scripts/eol_check.py          # or --staged inside a pre-commit hook
python scripts/encoding_check.py
python scripts/case_check.py
```

Then look at `git diff --stat`: a file you touched in two places should not show hundreds of changed lines.

**Something is already broken** - match the symptom:

| Symptom | Likely cause | Check |
|---|---|---|
| one-line change, whole-file diff | EOL flipped by a rewrite tool | `eol_check.py`, then `--fix` |
| `git diff -w` is small but `git diff` is huge | same | same |
| a scripted edit "ran fine" but the change is missing | `\n` pattern vs CRLF file; no assert | `git diff` the file; redo with `safe_replace.py` |
| PowerShell: "missing terminator", "unexpected token" on a line that looks correct | non-ASCII `.ps1` saved without BOM, read as ANSI | `encoding_check.py`, `--fix` |
| `Unexpected token ﻿` / JSON parse error at position 0 / `#!` script "not found" | BOM where none is allowed | `encoding_check.py`, `--fix` |
| Korean/CJK text shows as mojibake in a PowerShell API test, but ASCII fields match | the client decoded the response in the ANSI code page - the data is fine | decode the raw bytes as UTF-8 before comparing (see references/encoding.md) |
| CI/clean checkout: "differs only in casing", module not found; local build green | case-only rename not applied on disk, or an import with wrong casing hidden by a build cache | `case_check.py`; delete incremental build caches and rebuild |

## Rules of thumb

- Treat a green local build after a rename on Windows as unproven until a cache-free build passes.
- Normalising line endings (`.gitattributes` + renormalise) is the real cure, but do it in a **commit of its own**:
  it touches every affected file, splits `git blame`, and anything that deploys from that branch receives it.
- Do not "fix" mojibake in data before proving the bytes are wrong. Console and HTTP-client decoding lie far more
  often than databases do.
- When you add a check like these to a repository, prove it can go red: plant the failure once and watch the
  script catch it.

## References

- `references/line-endings.md` - why `read_text` is the culprit, `.gitattributes` migration, hook setup
- `references/encoding.md` - PowerShell 5.1 code pages, BOM rules per file type, decoding API responses
- `references/letter-case.md` - case-only renames on case-insensitive file systems, build caches
- `references/shell-quoting.md` - heredoc and PowerShell quoting traps for agents that drive a shell
