---
name: silent-wrong-answer
description: Hunts results that are wrong without any error - a dashboard total that is plausible but off, a report that quietly uses a default instead of the configured value, a sum that double-counts after a join, a setting that is saved but never read, an edit that "applied" but changed nothing. Use when a number "looks off", when two screens or reports disagree, when a fix changed nothing visible, when reviewing new calculation/aggregation/config code before shipping, or when the user says "숫자가 이상해", "값이 안 맞아", "왜 이 값이 나오지", "설정했는데 반영이 안 돼", "silent wrong answer". Not for crashes and stack traces - those announce themselves.
---

# Silent wrong answer

A crash tells you where to look. A wrong number does not: the code ran, the output is the right shape, and it is
close enough to believe. Reading the output harder will not reveal it, and reading the code first invites the most
plausible story - which, in practice, is often the wrong one.

The method: **get a second, independent answer, make the two disagree on demand, then walk the known traps.**

## 1. Pin the claim

Before touching code, write down in one line each:

- **Which value**, exactly where (screen, report row, API field, query), for which inputs.
- **Observed** value and **expected** value, and **why** it is expected (a spreadsheet? last month? a colleague's
  count? "it should be roughly...")
- **Since when** - always, after a deploy, after a data load, only for some inputs.

If "expected" has no source, the first job is to get one. "Looks off" is a lead, not a defect.

## 2. Build an oracle and a red signal

An oracle computes the same value **by a different path** that shares as little as possible with the suspect path:

| Oracle | Good for |
|---|---|
| a direct query against the source data | aggregates, filters, joins |
| a hand calculation on a tiny fixture (3-5 rows you made up) | formulas, allocation, rounding |
| the previous version / the other branch on the same input | regressions |
| a second implementation in a spreadsheet or a notebook | business rules |
| an independent report the business already trusts | end-to-end totals |

Then produce both results as tables and compare them mechanically:

```
python scripts/reconcile.py diff suspect.csv oracle.csv --key <id columns> [--tol 0.01]
```

`DUPLICATE` lines mean a key appears more than once - the most common silent multiplier. `ONLY LEFT/RIGHT` means the
two paths disagree on *which rows are in scope* - a boundary problem, not an arithmetic one. `MISMATCH` with a
constant ratio across rows points at units or a default; scattered mismatches point at rules or joins.

Done when you have **one command that shows the disagreement** and you have run it. If the two agree, the defect is
not where you thought, or the expectation was wrong - go back to step 1 with the user before changing anything.

## 3. Walk the trap catalogue

With the red signal in hand, test traps one at a time, cheapest first. Each has a quick probe in
`references/traps.md`. The ones seen most often in practice:

1. **A default stood in for the real value.** Missing key -> fallback; `x or 1`; a config default nobody sees.
   Probe: log *which source* every input came from, not just its value.
2. **Two definitions of "the same set".** The caller filters one way, the engine another (status, date boundary,
   effective vs nominal category). Probe: count rows at each stage with the same key.
3. **Grain / fan-out.** A parent-level number repeated on every child row and then summed; a join that multiplies.
   Probe: `reconcile.py grain detail.csv --group <parent key>`.
4. **Presence mistaken for value.** "Field exists" treated as "has a value"; 0 vs null vs empty string vs missing.
5. **Asymmetric validation.** One parameter of a pair is checked, its partner is not.
6. **Free-form input passing silently.** Units in strings ("30 min"), several values where one is expected, an
   LLM's or user's invented value accepted as-is.
7. **Units and time zones.** Minutes vs hours; a naive timestamp "converted" and moved across midnight.
8. **Configured but not consumed.** The setting is saved and loaded, but nothing reads it - or the UI never calls the
   endpoint that would use it.
9. **Stale runtime.** The process serving requests predates your change; a cache or incremental build hides it.
10. **An edit that did not happen.** A scripted replace matched nothing; an optional parameter was never wired.
11. **Lossy bulk paths.** Batch loaders truncating strings, dropping fractional seconds, coercing types.
12. **Display, not data.** Rounding in the view, or mojibake from client-side decoding, mistaken for stored values.

## 4. Report before fixing

When you find the cause, say what it is, how far it reaches (which other screens/reports use the same path), and
what the fix would change - **then** fix, unless the user already asked you to. A silent wrong answer usually has
been feeding decisions; the user needs to know which past numbers were affected, and that is often more important
than the patch.

## 5. Fix so it cannot be silent again

- Add a regression test **at the consumer**, not just the loader: assert the final number for a fixture, so a future
  fallback or a dropped wire turns it red.
- Make the silent path loud: a missing value raises or is logged with its source; a fallback is visible in the output
  (`value (default)`); a filter boundary is shared code, not two copies.
- Re-run the step 2 command against the original case and show it agreeing.

## Review mode

When reviewing new calculation, aggregation or configuration code (no reported bug yet), skip steps 1-2 and run the
catalogue as a checklist against the diff. For each trap, either name the line that is safe or name the risk. Report
risks; do not silently fix them.

## Anti-patterns

- **Running to the plausible cause.** A familiar error code, a known flaky component, "it's probably the network".
  Without the red signal, a plausible cause is a guess. See `references/case-studies.md` for misdiagnoses that looked
  convincing.
- **Comparing against the same path.** Re-running the suspect query with a tweak is not an oracle.
- **Fixing the first discrepancy and stopping.** Silent errors cluster; re-run the full comparison after each fix.
- **Trusting green tests.** They are only evidence inside what they cover; a missing wire is often outside it.

## References

- `references/traps.md` - each trap with symptoms, a probe, and the durable fix
- `references/case-studies.md` - anonymised real incidents, including misdiagnoses
- `references/loud-fallbacks.md` - code patterns that make defaults and fallbacks visible
