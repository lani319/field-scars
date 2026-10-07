from __future__ import annotations

import json

import reconcile


def write(path, text):
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_diff_agrees_within_tolerance(tmp_path):
    a = write(tmp_path / "a.csv", 'id,amount\n1,10.0\n2,"1,000.5"\n')
    b = write(tmp_path / "b.json", json.dumps([{"id": 1, "amount": 10.001}, {"id": 2, "amount": 1000.5}]))
    assert reconcile.main(["diff", a, b, "--key", "id", "--tol", "0.01"]) == 0
    assert reconcile.main(["diff", a, b, "--key", "id"]) == 1


def test_diff_reports_scope_duplicates_and_mismatch(tmp_path, capsys):
    a = write(tmp_path / "a.csv", "id,amount,label\n1,10,x\n2,20,y\n2,20,y\n3,30,z\n")
    b = write(tmp_path / "b.jsonl", '{"id": 1, "amount": 10, "label": "x"}\n{"id": 2, "amount": 25}\n{"id": 4}\n')
    assert reconcile.main(["diff", a, b, "--key", "id"]) == 1
    out = capsys.readouterr().out
    assert "DUPLICATE" in out and "('2',) appears 2 times" in out
    assert "ONLY LEFT  ('3',)" in out
    assert "ONLY RIGHT ('4',)" in out
    assert "('2',) amount: left='20' right='25'  (delta +5)" in out
    assert "label" in out  # 'y' vs missing


def test_diff_composite_key_and_missing_key_column(tmp_path, capsys):
    a = write(tmp_path / "a.csv", "line,step,m\nA,1,5\nA,2,6\n")
    b = write(tmp_path / "b.csv", "line,step,m\nA,2,6\nA,1,5\n")
    assert reconcile.main(["diff", a, b, "--key", "line,step"]) == 0
    assert reconcile.main(["diff", a, b, "--key", "nope"]) == 2
    assert "not found" in capsys.readouterr().out


def test_grain_flags_parent_value_repeated_on_children(tmp_path, capsys):
    f = write(
        tmp_path / "d.csv",
        "order,item,qty,order_total\nA,x,1,100\nA,y,2,100\nA,z,3,100\nB,x,5,40\nB,y,1,40\nC,x,1,7\n",
    )
    assert reconcile.main(["grain", f, "--group", "order"]) == 1
    out = capsys.readouterr().out
    assert "REPEATED   order_total" in out
    assert "SUM over rows = 380, SUM once per group = 140" in out
    assert "qty" not in out.split("REPEATED")[1].split("\n")[0]


def test_grain_row_level_value_is_clean(tmp_path):
    f = write(tmp_path / "d.csv", "order,qty\nA,1\nA,2\nB,3\nB,4\n")
    assert reconcile.main(["grain", f, "--group", "order"]) == 0
    assert reconcile.main(["grain", f, "--group", "order", "--value", "qty"]) == 0
