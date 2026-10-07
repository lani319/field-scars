#!/usr/bin/env python3
"""Compare a suspect result with an independent oracle, and spot values that will be double-counted.

Two subcommands:

  diff   Line up two tables by key and report every disagreement - keys missing on either side, duplicate keys
         (a join fan-out is the classic silent multiplier), and values that differ beyond a tolerance.

             python reconcile.py diff screen.csv oracle.csv --key order_id
             python reconcile.py diff a.json b.jsonl --key line,step --cols minutes,people --tol 0.01

  grain  Find columns whose value repeats on every row of a group - a header-level number copied onto each
         detail row. Summing such a column over rows multiplies it by the group size.

             python reconcile.py grain detail.csv --group order_id
             python reconcile.py grain detail.csv --group order_id --value order_total

Inputs: CSV (UTF-8, BOM tolerated), JSON (a list of objects) or JSON Lines, chosen by extension.
Exit code: 0 = agree / no repeated values, 1 = differences found, 2 = bad input.
Standard library only; Python 3.9+.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

Row = dict[str, str]
MAX_SHOWN = 20


def load(path: Path, encoding: str) -> list[Row]:
    suffix = path.suffix.lower()
    text = path.read_text(encoding=encoding)
    if suffix == ".csv":
        return [dict(r) for r in csv.DictReader(text.splitlines())]
    if suffix in (".jsonl", ".ndjson"):
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    elif suffix == ".json":
        rows = json.loads(text)
    else:
        raise ValueError(f"{path}: use .csv, .json or .jsonl")
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise ValueError(f"{path}: expected a list of objects")
    return [{k: "" if v is None else str(v) for k, v in r.items()} for r in rows]


def number(s: str) -> float | None:
    try:
        v = float(s.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None
    return v if math.isfinite(v) else None


def same(a: str, b: str, tol: float, rel: float) -> bool:
    x, y = number(a), number(b)
    if x is None or y is None:
        return a.strip() == b.strip()
    return abs(x - y) <= max(tol, rel * max(abs(x), abs(y)))


def index(rows: list[Row], key: list[str], label: str) -> tuple[dict[tuple, Row], dict[tuple, int]]:
    out: dict[tuple, Row] = {}
    counts: dict[tuple, int] = defaultdict(int)
    for r in rows:
        missing = [k for k in key if k not in r]
        if missing:
            raise ValueError(f"{label}: key column(s) {missing} not found; columns are {sorted(r)}")
        k = tuple(r[c].strip() for c in key)
        counts[k] += 1
        out.setdefault(k, r)
    return out, {k: n for k, n in counts.items() if n > 1}


def cmd_diff(a: argparse.Namespace) -> int:
    key = a.key.split(",")
    left, right = load(a.left, a.encoding), load(a.right, a.encoding)
    li, ldup = index(left, key, str(a.left))
    ri, rdup = index(right, key, str(a.right))
    if a.cols:
        cols = a.cols.split(",")
    else:
        lcols = set(left[0]) if left else set()
        rcols = set(right[0]) if right else set()
        cols = sorted((lcols & rcols) - set(key))
        dropped = sorted((lcols ^ rcols) - set(key))
        if dropped:
            print(f"note: columns only on one side are not compared: {dropped}")
    problems = 0

    for label, dup in ((a.left, ldup), (a.right, rdup)):
        for k, n in list(dup.items())[:MAX_SHOWN]:
            print(f"DUPLICATE  {label}: key {k} appears {n} times (fan-out? only the first row is compared)")
        problems += len(dup)
    only_l = [k for k in li if k not in ri]
    only_r = [k for k in ri if k not in li]
    for k in only_l[:MAX_SHOWN]:
        print(f"ONLY LEFT  {k}")
    for k in only_r[:MAX_SHOWN]:
        print(f"ONLY RIGHT {k}")
    problems += len(only_l) + len(only_r)

    totals: dict[str, list[float]] = {c: [0.0, 0.0] for c in cols}
    diffs = 0
    for k in li.keys() & ri.keys():
        for c in cols:
            x, y = li[k].get(c, ""), ri[k].get(c, "")
            nx, ny = number(x), number(y)
            if nx is not None and ny is not None:
                totals[c][0] += nx
                totals[c][1] += ny
            if not same(x, y, a.tol, a.rel):
                if diffs < MAX_SHOWN:
                    delta = f"  (delta {ny - nx:+g})" if nx is not None and ny is not None else ""
                    print(f"MISMATCH   {k} {c}: left={x!r} right={y!r}{delta}")
                diffs += 1
    problems += diffs

    print(f"\nrows: left={len(left)} right={len(right)} matched keys={len(li.keys() & ri.keys())}")
    for c, (sx, sy) in totals.items():
        if sx or sy:
            ratio = f"  ratio {sx / sy:.4g}" if sy else ""
            print(f"total {c}: left={sx:g} right={sy:g}{ratio}")
    print(f"reconcile: {problems} difference(s)" + (" - more than shown" if problems > MAX_SHOWN else ""))
    return 1 if problems else 0


def cmd_grain(a: argparse.Namespace) -> int:
    rows = load(a.file, a.encoding)
    group = a.group.split(",")
    if not rows:
        print("grain: no rows")
        return 0
    cols = [a.value] if a.value else [c for c in rows[0] if c not in group]
    groups: dict[tuple, list[Row]] = defaultdict(list)
    for r in rows:
        groups[tuple(r.get(g, "") for g in group)].append(r)
    multi = {k: v for k, v in groups.items() if len(v) > 1}
    if not multi:
        print(f"grain: every {group} group has a single row - nothing can repeat")
        return 0
    flagged = 0
    for c in cols:
        constant = varying = 0
        for members in multi.values():
            values = {m.get(c, "") for m in members}
            if len(values) == 1:
                constant += 1
            else:
                varying += 1
        nums = [number(r.get(c, "")) for r in rows]
        numeric = sum(v is not None for v in nums) >= 0.9 * len(rows)
        if numeric and constant and not varying:
            inflated = sum(sum(number(m.get(c, "")) or 0 for m in v) for v in multi.values())
            true_sum = sum(number(v[0].get(c, "")) or 0 for v in multi.values())
            print(
                f"REPEATED   {c}: identical on every row of all {constant} multi-row groups - a group-level value. "
                f"SUM over rows = {inflated:g}, SUM once per group = {true_sum:g}"
            )
            flagged += 1
        elif a.value:
            print(f"{c}: constant in {constant} group(s), varies in {varying} - looks like a row-level value")
    print(f"grain: {len(multi)} multi-row group(s) checked, {flagged} repeated column(s)")
    return 1 if flagged else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--encoding", default="utf-8-sig")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("diff", help="compare two tables by key")
    d.add_argument("left", type=Path)
    d.add_argument("right", type=Path)
    d.add_argument("--key", required=True, help="comma-separated key column(s)")
    d.add_argument("--cols", help="comma-separated columns to compare (default: all shared)")
    d.add_argument("--tol", type=float, default=1e-9, help="absolute tolerance for numbers")
    d.add_argument("--rel", type=float, default=0.0, help="relative tolerance for numbers, e.g. 0.001")
    g = sub.add_parser("grain", help="find group-level values repeated on detail rows")
    g.add_argument("file", type=Path)
    g.add_argument("--group", required=True, help="comma-separated column(s) identifying the parent entity")
    g.add_argument("--value", help="check only this column")
    a = ap.parse_args(argv)
    try:
        return cmd_diff(a) if a.cmd == "diff" else cmd_grain(a)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
