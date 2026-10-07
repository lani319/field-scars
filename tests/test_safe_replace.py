from __future__ import annotations

import json

import safe_replace


def spec(tmp_path, edits):
    p = tmp_path / "edits.json"
    p.write_text(json.dumps(edits), encoding="utf-8")
    return p


def test_lf_pattern_matches_crlf_file_and_keeps_crlf(tmp_path):
    f = tmp_path / "a.ts"
    f.write_bytes(b"function a() {\r\n  return 1;\r\n}\r\n")
    s = spec(tmp_path, [{"file": "a.ts", "old": "{\n  return 1;", "new": "{\n  return 2;"}])
    assert safe_replace.main([str(s), "--base", str(tmp_path)]) == 0
    assert f.read_bytes() == b"function a() {\r\n  return 2;\r\n}\r\n"


def test_bom_preserved(tmp_path):
    f = tmp_path / "a.ps1"
    f.write_bytes(b"\xef\xbb\xbfWrite-Host '\xed\x95\x9c'\r\n")
    s = spec(tmp_path, [{"file": "a.ps1", "old": "Write-Host", "new": "Write-Output"}])
    assert safe_replace.main([str(s), "--base", str(tmp_path)]) == 0
    assert f.read_bytes() == b"\xef\xbb\xbfWrite-Output '\xed\x95\x9c'\r\n"


def test_batch_is_all_or_nothing(tmp_path, capsys):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_bytes(b"alpha\n")
    b.write_bytes(b"beta\n")
    s = spec(
        tmp_path, [{"file": "a.txt", "old": "alpha", "new": "ALPHA"}, {"file": "b.txt", "old": "gamma", "new": "x"}]
    )
    assert safe_replace.main([str(s), "--base", str(tmp_path)]) == 1
    assert "found 0 match(es)" in capsys.readouterr().out
    assert a.read_bytes() == b"alpha\n"  # first edit was valid but must not be written


def test_count_is_exact(tmp_path):
    f = tmp_path / "a.txt"
    f.write_bytes(b"x x x\n")
    assert (
        safe_replace.main([str(spec(tmp_path, [{"file": "a.txt", "old": "x", "new": "y"}])), "--base", str(tmp_path)])
        == 1
    )
    s = spec(tmp_path, [{"file": "a.txt", "old": "x", "new": "y", "count": 3}])
    assert safe_replace.main([str(s), "--base", str(tmp_path)]) == 0
    assert f.read_bytes() == b"y y y\n"


def test_sequential_edits_on_same_file(tmp_path):
    f = tmp_path / "a.txt"
    f.write_bytes(b"v1\n")
    s = spec(tmp_path, [{"file": "a.txt", "old": "v1", "new": "v2"}, {"file": "a.txt", "old": "v2", "new": "v3"}])
    assert safe_replace.main([str(s), "--base", str(tmp_path)]) == 0
    assert f.read_bytes() == b"v3\n"


def test_dry_run_writes_nothing(tmp_path):
    f = tmp_path / "a.txt"
    f.write_bytes(b"a\n")
    s = spec(tmp_path, [{"file": "a.txt", "old": "a", "new": "b"}])
    assert safe_replace.main([str(s), "--base", str(tmp_path), "--dry-run"]) == 0
    assert f.read_bytes() == b"a\n"


def test_mixed_file_needs_unambiguous_spelling(tmp_path):
    f = tmp_path / "a.txt"
    f.write_bytes(b"a\r\nb\nc\n")
    s = spec(tmp_path, [{"file": "a.txt", "old": "b\nc", "new": "B\nC"}])
    assert safe_replace.main([str(s), "--base", str(tmp_path)]) == 0
    assert f.read_bytes() == b"a\r\nB\nC\n"


def test_non_utf8_fails(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"\xc7\xd1\xb1\xdb\n")  # legacy code page bytes
    s = spec(tmp_path, [{"file": "a.txt", "old": "x", "new": "y"}])
    assert safe_replace.main([str(s), "--base", str(tmp_path)]) == 1
