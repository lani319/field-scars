# Letter case on case-insensitive file systems

Windows (NTFS by default) and macOS (APFS by default) are case-insensitive but case-preserving. Git sets
`core.ignorecase=true` there. Linux - and therefore most CI runners and production build servers - is case-sensitive.

## How it breaks

1. Someone creates `components/searchPanel/` while every import says `./SearchPanel/...`. On their machine the import
   resolves (case-insensitive), so everything works.
2. Or someone renames `grid` to `Grid` correctly, but on your machine `git pull` updates the index without renaming
   the folder on disk. Your working tree now disagrees with the repository.
3. An incremental build cache (TypeScript `.tsbuildinfo`, bundler caches) remembers the old resolution and keeps the
   local build green even after the casing goes wrong.
4. A clean checkout on a case-sensitive machine fails: "module not found", or TypeScript's "file name differs from
   already included file name only in casing".

## Checks

`case_check.py` uses the git index as the truth, because that is what a fresh checkout receives:

- `COLLISION`: two tracked paths differing only by case. On Linux they are two folders; on Windows one of them
  silently wins. Decide which is right and move everything there.
- `DISK`: your disk casing differs from the index. Rename on disk to match.
- `IMPORT`: a relative import's casing differs from the tracked file. Fix the import (or the file name), then run a
  build **with caches deleted** to prove it.

## Renaming only the case

Git on a case-insensitive file system may treat `git mv grid Grid` as a no-op or error. Use two steps:

```
git mv grid grid_tmp
git mv grid_tmp Grid
```

Teammates who pull the rename on Windows/macOS may need to rename the folder on disk themselves; `case_check.py`
reports it as `DISK`.

## Conventions that prevent it

- Pick one casing rule per folder type (for example PascalCase component folders) and write it down.
- Run a cache-free build in CI, and before trusting a local green build after any rename.
- Avoid creating a path that differs from an existing one only by case.
