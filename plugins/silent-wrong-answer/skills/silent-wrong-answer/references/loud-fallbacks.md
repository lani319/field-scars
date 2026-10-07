# Making silent paths loud

The goal is not to remove defaults - they are often right - but to make it impossible to use one without anyone
being able to tell.

## Carry the source with the value

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Resolved:
    value: float
    source: str  # "line setting", "plant setting", "global default"


def resolve_cycle_time(line: str, settings: dict, plant: dict, default: float) -> Resolved:
    if line in settings:
        return Resolved(settings[line], "line setting")
    if "cycle_time" in plant:
        return Resolved(plant["cycle_time"], "plant setting")
    return Resolved(default, "global default")
```

Show `source` in logs, API responses (a `meta` field) and, where users make decisions on it, in the UI
("37 min - line setting" vs "480 min - default").

## Fail where "missing" is a bug

```python
def require(mapping: dict, key: str, what: str):
    try:
        return mapping[key]
    except KeyError:
        raise LookupError(f"{what}: no value for {key!r} (no fallback on purpose)") from None
```

Reserve `get(key, default)` for places where the default is genuinely the intended behaviour, and say so in a
comment.

## Count what fell through

When a fallback is legitimate but should be rare, count it and report the count with the result:

```python
fallbacks = Counter()
...
fallbacks[resolved.source] += 1
...
log.info("cycle time sources: %s", dict(fallbacks))  # {'line setting': 41, 'global default': 3}
```

A sudden jump in the default count is the earliest warning you will get.

## Pass meaningful library defaults explicitly

```python
allocate(items, weights=weights)  # not allocate(items) relying on weight=1
```

If a call site truly wants the default, write it out (`weights=None  # equal weights intended`). A reviewer can then
see the decision.

## Share scope definitions

```python
def in_scope(row) -> bool:  # used by the screen query AND the engine
    return row.status in ACTIVE and row.effective_process == row.process_filter
```

Two copies of a filter drift; one function cannot.

## Pin the consumer in tests

```python
def test_line_setting_changes_result(engine, fixture):
    base = engine.run(fixture).total_people
    fixture.settings["L1"] = 10.0
    assert engine.run(fixture).total_people != base  # the setting is actually consumed
```

A test on the loader alone stays green when the wire to the consumer is cut.
