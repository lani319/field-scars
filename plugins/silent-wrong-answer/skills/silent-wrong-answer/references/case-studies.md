# Case studies

Real incidents from a production planning system (simulation, allocation, reporting over a mirrored SQL database and
a locally hosted language model). Names and figures are generalised. Each one was silent: no error, plausible output.

---

### A fallback that looked like source data - twice

A planning screen showed a line-balancing efficiency of 0.2%. The team suspected bad source data and spent time on
the data mirror. The real cause: the line had no configured cycle time, so a global default (capped at a large
"maximum") was used, making every station look almost idle. Months later a similar symptom on another screen was
again blamed on data first - same fallback.

*Lesson*: trap 1. Log the source of every resolved parameter. After the second time, the fallback was made visible in
the output.

### A network error that was a memory problem

Nightly synchronisation jobs failed with a "communication link failure" code - which reads like the network. The
real cause was the database server running out of memory because a model server on the same machine had claimed it;
the database dropped connections under pressure. Network checks all passed and wasted a day.

*Lesson*: an error code names where the failure surfaced, not where it started. Find the signal that goes red with
the bug (here, the database's own memory and allocation-failure counters) before trusting the code's name.

### "The database is down" / "the model is down"

Users reported that queries and the assistant had stopped working. Both dependencies were healthy. A second copy of
the backend had been started by hand on the same port; binding succeeded silently and requests hung.

*Lesson*: trap 9. Stop the service you believe is answering; if requests still get a response, something else is.

### A parent value summed per child

A report summed an operation-level standard time over material rows. The operation time was repeated on every
material row of that operation, so the total grew with the number of materials - 3x for some operations, 20x for
others. Averages looked normal; only totals were wrong.

*Lesson*: trap 3. `reconcile.py grain` flags exactly this shape. The fix was to aggregate per operation first.

### Two definitions of a process

A scenario filtered work by its nominal process; the engine grouped by an *effective* process (after reassignments).
Scenario totals and engine totals disagreed by the reassigned work, with no error anywhere.

*Lesson*: trap 2. The scope definition was moved into one shared function.

### A weight that defaulted to 1

An allocation step accepted optional per-item weights. When a caller omitted them, the library treated every item
as weight 1 - a legal value - so the result was an equal split instead of the intended proportional one.

*Lesson*: trap 1 in its library form. Parameters with meaningful defaults are now passed explicitly, and a test omits
them to prove the call fails or warns.

### The setting nobody read

Administrators could set a per-line cycle time. It was saved and loaded correctly, and the resolver had unit tests -
but no request path called the resolver. Separately, another screen's "apply" action called an endpoint the UI never
actually invoked.

*Lesson*: trap 8. Tests now change the setting and assert the final number changes.

### A read-only screen that could be edited

A shared, read-only view of a board was supposed to disable editing. The property was passed through a scripted
multi-file replacement; in one CRLF file the pattern (written with `\n`) matched nothing. The property was optional,
so types, tests and build stayed green. A user found it by clicking.

*Lesson*: trap 10. Every scripted replacement now asserts its match; the property became required.

### Milliseconds that vanished in bulk load

An incremental sync used "last updated" timestamps as a watermark. The fast bulk-insert mode bound the time column
without fractional precision, so milliseconds were dropped on write. Comparisons against the source then re-read or
skipped rows near the boundary.

*Lesson*: trap 11. Input sizes and precisions are declared explicitly; a round-trip test covers fractional seconds.

### A day lost to time-zone conversion

Timestamps in the database were naive local time. A front-end utility "converted" them as if they were UTC, moving
late-evening records to the next day on screen.

*Lesson*: trap 7. One date/time module owns conversion; naive local values are displayed as-is.

### Verifying against yesterday's code

A fix was verified on screen and "did not work". The worker process serving the screen had started more than a day
earlier; auto-reload had been blocked by a long-running database call holding a lock.

*Lesson*: trap 9. Check the serving process's start time (or a version endpoint) before judging behaviour.

### Garbled text that was never garbled

An API smoke test on Windows posted Korean text and compared the response: mismatch. Database collation, column types
and the driver were all suspected. The HTTP client had decoded the UTF-8 response in the legacy code page; the stored
data was correct.

*Lesson*: trap 12. Decode the raw bytes explicitly before suspecting storage.
