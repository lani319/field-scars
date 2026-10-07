# Line endings

## How a repository gets into the dangerous state

Git only normalises line endings if told to - by `.gitattributes` (`* text=auto`) or `core.autocrlf`. Many
repositories have neither: files were committed from different editors and machines, so some are LF and some CRLF,
and git faithfully keeps each one as it is. That is stable until a tool rewrites a file in the *other* style. Then
every line differs, `git diff` shows the whole file, and the two real lines you changed are invisible in review and
in `git blame`.

`eol_check.py --scan` tells you whether a repository is in this state.

## The usual culprit is the read, not the write

```python
text = Path(p).read_text(encoding="utf-8")  # CRLF is translated to "\n" HERE
Path(p).write_text(text.replace(a, b), newline="")  # too late: there is no "\r" left to keep
```

Python opens text files in universal-newline mode, so `\r\n` becomes `\n` while reading. Whatever you do on the
write side, a CRLF file comes back LF. The same happens in many other runtimes that read "text".

Safe pattern:

```python
data = Path(p).read_bytes()
assert old_bytes in data, f"{p}: anchor not found"
Path(p).write_bytes(data.replace(old_bytes, new_bytes))
```

...where `old_bytes` must itself use the file's line endings. `safe_replace.py` does that conversion for you.

A second, quieter failure: if the pattern contains `\n` and the file is CRLF, `replace` matches nothing and raises
nothing. Without an assert the script reports success and the edit is simply missing - and if the missing piece is
an optional parameter or a config key, type checks, tests and builds all stay green.

Editor and agent "edit" tools that patch in place generally preserve line endings; whole-file rewrite paths
(formatters, codemods, "write the file again" scripts) are where flips come from.

## Hooks

Pre-commit (plain git hook, `.git/hooks/pre-commit`):

```sh
#!/bin/sh
python path/to/eol_check.py --staged || exit 1
```

With the `pre-commit` framework, add a `local` hook with `entry: python path/to/eol_check.py --staged`,
`language: system`, `pass_filenames: false`.

## Normalising for good

1. Agree on the policy, e.g. `* text=auto eol=lf` plus explicit `*.ps1 text eol=crlf`, `*.bat text eol=crlf`, and
   `binary` for media.
2. In a branch with no other changes: add `.gitattributes`, run `git add --renormalize .`, commit as
   "normalise line endings" and nothing else.
3. Tell everyone to re-checkout after pulling. Optionally list the commit in `.git-blame-ignore-revs`.

Until that happens, keep `eol_check.py` in the pre-commit path.
