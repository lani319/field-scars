# Trap catalogue

Each entry: what it looks like from outside, a probe that confirms or rules it out in minutes, and the fix that
keeps it from coming back. Probe one trap at a time against your red signal.

---

## 1. A default stood in for the real value

**Looks like**: a whole category of results is uniformly off; changing the "real" setting does nothing; the value
equals a round number (1, 0, 100, 480, the documented default).

**Where it hides**: `config.get(key, DEFAULT)`, `value or 1`, `?? 0`, ORM column defaults, library parameters with
defaults (weights default to 1, timeouts, rounding modes), "if not found, use the global setting" chains.

**Probe**: print the **source** of each input next to its value (`takt=480 (global default)` vs
`takt=37 (line setting)`). Temporarily make the fallback raise - if the run now fails, it was being used.

**Fix**: fallbacks report themselves (see loud-fallbacks.md). Chains of precedence are written down in one place and
tested with a fixture where each level is missing in turn.

## 2. Two definitions of "the same set"

**Looks like**: totals differ between two screens by a stable amount; `reconcile.py diff` shows `ONLY LEFT` /
`ONLY RIGHT` keys.

**Where it hides**: the caller filters on a nominal category while the engine uses an effective/derived one; one side
uses `<= end_date`, the other `< end_date + 1 day`; status lists that drifted apart; soft-deleted rows included on one
side.

**Probe**: count rows at every stage with the same key list; diff the key sets, not just the totals.

**Fix**: one function defines the scope; both paths call it. A test feeds a row that sits exactly on each boundary.

## 3. Grain and fan-out

**Looks like**: totals are inflated by a factor that varies per entity (2x for one order, 7x for another); averages
look fine but sums do not.

**Where it hides**: a parent-level number (order total, operation time) copied onto every detail row and then
`SUM`med; a join to a table that has several rows per key; a view that someone extended with a new join.

**Probe**: `reconcile.py grain detail.csv --group <parent key>` flags columns that are constant within every group.
For joins: `SELECT key, COUNT(*) ... GROUP BY key HAVING COUNT(*) > 1` on the joined side.

**Fix**: aggregate at the right grain first, then join. Name columns by grain (`order_total` vs `line_amount`).
Assert uniqueness of join keys in tests or in the query.

## 4. Presence mistaken for value

**Looks like**: some rows silently take the "has value" branch with an empty value; edits appear saved but revert;
zero rows disappear from averages.

**Where it hides**: `"field" in obj` or `hasattr` used as "has a value"; `if x:` treating 0 as missing; null vs empty
string vs missing key handled by different layers; UI grids that write back `undefined` into a row object.

**Probe**: build a fixture with each state - missing, null, empty string, 0, real value - and push it through.

**Fix**: one explicit helper decides "has a value"; the states that mean different things stay distinct.

## 5. Asymmetric validation

**Looks like**: one parameter rejects bad input loudly, its partner accepts anything.

**Where it hides**: `merge_from` validated but `merge_into` not; start date checked, end date not; the ID checked
for existence, the scope it belongs to not.

**Probe**: list every parameter of the entry point; for each, feed an invalid value. Any that pass silently are the
finding.

**Fix**: validate parameters together; test the matrix.

## 6. Free-form input passing silently

**Looks like**: results are wrong only for certain phrasings or users; nothing errors.

**Where it hides**: `"30 min"` parsed as 30 hours or as 0; `"3, 5"` truncated to 3; values produced by an LLM or a
form that are invented, out of range, or in the wrong unit, and accepted because they parse.

**Probe**: feed unit strings, ranges, lists, and plausible-but-nonexistent identifiers. Check the parsed value, not
just "no exception".

**Fix**: parse deterministically, reject what does not parse, check ranges and existence. When a model produces
parameters, treat them like user input.

## 7. Units and time zones

**Looks like**: off by a constant factor (60, 1000, 3600) or by exactly one day near midnight.

**Where it hides**: minutes vs hours vs seconds across an API boundary; milliseconds vs seconds in timestamps; a naive
local timestamp treated as UTC and "converted".

**Probe**: the ratio column in `reconcile.py diff` totals; test a timestamp at 00:30 and 23:30 local time.

**Fix**: units in names (`duration_min`), one module that owns date/time conversion, explicit time zones at the
boundaries.

## 8. Configured but not consumed

**Looks like**: "I changed the setting and nothing happened."

**Where it hides**: a loader reads the setting but no caller asks for it; the resolver function exists but is never
called; the backend endpoint that applies it is never called by the UI.

**Probe**: search for every *call* of the getter, not its definition. Change the setting to an absurd value and see
whether any output moves.

**Fix**: a test that changes the setting and asserts the **final output** changes - pinning the consumer, not the
loader.

## 9. Stale runtime

**Looks like**: the fix is in the code, tests pass, the screen still shows the old result.

**Where it hides**: a long-running worker started before the change; auto-reload stuck behind a blocking call; a
second process bound to the same port answering instead; build caches; browser or CDN caches.

**Probe**: check the start time of the process that actually serves the request; add a version/commit field to a
health endpoint and read it; stop the service - if requests still succeed, something else is answering.

**Fix**: expose the running version; verify against it before verifying behaviour.

## 10. An edit that did not happen

**Looks like**: the change "was applied", builds and tests are green, the behaviour is unchanged.

**Where it hides**: scripted text replacement that matched nothing (line endings, whitespace); an optional parameter
or property that the change was supposed to pass but did not - types accept its absence.

**Probe**: `git diff` and grep for the new wiring at every call site you intended to change.

**Fix**: assert each scripted replacement; make essential parameters required instead of optional.

## 11. Lossy bulk paths

**Looks like**: data loaded in bulk differs subtly from data written one row at a time - truncated text, timestamps
rounded to the second, numbers rounded, NULL turned into empty string.

**Where it hides**: "fast" batch insert modes that size buffers from the first row or bind types without precision;
CSV round-trips; spreadsheet imports guessing types.

**Probe**: round-trip a fixture with long strings, fractional seconds, extreme numbers and NULLs through the bulk path
and compare byte for byte.

**Fix**: declare input sizes and precisions explicitly; add a round-trip test to the loader.

## 12. Display, not data

**Looks like**: the screen value differs from the stored value, or text looks corrupted.

**Where it hides**: rounding or truncation in formatting; a column showing a different field than its header says;
an HTTP client or console decoding UTF-8 as a legacy code page.

**Probe**: read the raw stored value and the raw response bytes before suspecting storage.

**Fix**: format in one place; decode explicitly; label columns from the same source the data comes from.
