# field-scars

[한국어](README.ko.md)

Agent skills distilled from incidents in a production system - the kind of failure that does not raise an error,
so you only find it later, in someone else's diff, build or report. Each skill ships with small standard-library
scripts that turn the lesson into a check that goes red.

| Plugin | What it catches |
|---|---|
| **windows-repo-hygiene** | line endings flipping a whole file, scripted edits that match nothing, PowerShell 5.1 mis-reading non-ASCII scripts, BOMs breaking JSON/shell/nginx, letter-case renames that pass locally and fail on CI |
| **silent-wrong-answer** | results that are plausible but wrong: defaults standing in for real values, double counting after joins, settings saved but never read, stale processes, lossy bulk loads - with an oracle-diff tool and a 12-trap catalogue |

## Install (Claude Code)

```
claude plugin marketplace add lani319/field-scars
claude plugin install windows-repo-hygiene@field-scars
claude plugin install silent-wrong-answer@field-scars
```

Or inside a session: `/plugin marketplace add lani319/field-scars`, then `/plugin`.

The skills trigger on their own when the situation matches (a whole-file diff, "this number looks off", a PowerShell
parse error on a line that looks fine...). You can also name them: "use silent-wrong-answer on this total".

## Use with Codex or other agents

Clone the repository and point your `AGENTS.md` at the skill files:

```
For line-ending, BOM, encoding or letter-case problems, follow plugins/windows-repo-hygiene/skills/windows-repo-hygiene/SKILL.md.
When a result looks wrong without an error, follow plugins/silent-wrong-answer/skills/silent-wrong-answer/SKILL.md.
```

## Use the scripts directly

They need only Python 3.9+ and git, and exit non-zero on findings, so they fit pre-commit hooks and CI.

```
python plugins/windows-repo-hygiene/skills/windows-repo-hygiene/scripts/eol_check.py --scan   # is this repo at risk?
python .../eol_check.py --staged          # pre-commit: did a file's line endings flip?
python .../encoding_check.py              # BOM / encoding problems in tracked files
python .../case_check.py                  # case collisions, disk drift, wrongly-cased imports
python .../safe_replace.py edits.json     # all-or-nothing replacements that keep EOL and BOM

python plugins/silent-wrong-answer/skills/silent-wrong-answer/scripts/reconcile.py diff suspect.csv oracle.csv --key id
python .../reconcile.py grain detail.csv --group order_id   # parent values repeated on child rows
```

First run on the 3,600-file repository these lessons came from: `eol_check --scan` flagged 2,798 LF and 294 CRLF files
kept byte-for-byte (its `.gitattributes` only configured LFS), and `encoding_check` found a deployment script with
non-ASCII comments and no BOM - harmless today, broken the day someone adds a non-ASCII string.

## Develop

```
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt   # or .venv/bin/pip
python tools/gate.py        # ruff + pytest (+ clean-room checks when configured)
```

## License

MIT
