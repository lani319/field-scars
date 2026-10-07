from __future__ import annotations

from pathlib import Path

import encoding_check

BOM = b"\xef\xbb\xbf"
KO = "안녕".encode()


def rule(name: str, data: bytes):
    hit = encoding_check.check(Path(name), data)
    return hit[0] if hit else None


def test_powershell_rules():
    assert rule("a.ps1", b"Write-Host '" + KO + b"'") == "PS_NEEDS_BOM"
    assert rule("a.ps1", BOM + b"Write-Host '" + KO + b"'") is None
    assert rule("a.ps1", b"Write-Host 'hi'") is None  # ASCII-only is fine without BOM
    assert rule("a.psm1", b"$x = '" + KO + b"'") == "PS_NEEDS_BOM"
    assert rule("a.ps1", b"\xff\xfe" + "안".encode("utf-16-le")) is None


def test_must_not_bom():
    for name in ("x.json", "run.sh", ".env", ".env.local", "nginx.conf", "conf/nginx/site.conf"):
        assert rule(name, BOM + b"{}") == "MUST_NOT_BOM", name
    assert rule("tool", BOM + b"#!/usr/bin/env python\n") == "MUST_NOT_BOM"
    assert rule("notes.md", BOM + b"# title") is None
    assert rule("app.conf", BOM + b"x=1") is None


def test_not_utf8_and_binary():
    assert rule("a.txt", b"\xc7\xd1\xb1\xdb") == "NOT_UTF8"
    assert rule("a.bin", b"\x00\x01\xc7") is None


def test_fix(tmp_path):
    ps, js = tmp_path / "a.ps1", tmp_path / "a.json"
    ps.write_bytes(b"'" + KO + b"'")
    js.write_bytes(BOM + b"{}")
    assert encoding_check.main([str(ps), str(js), "--fix"]) == 0
    assert ps.read_bytes().startswith(BOM)
    assert js.read_bytes() == b"{}"
    assert encoding_check.main([str(ps), str(js)]) == 0


def test_strict_counts_warnings(tmp_path):
    f = tmp_path / "a.txt"
    f.write_bytes(b"\xc7\xd1")
    assert encoding_check.main([str(f)]) == 0
    assert encoding_check.main([str(f), "--strict"]) == 1


def test_non_ascii_only_in_comments_is_a_warning():
    body = "<#\n  설명\n#>\n# 주석\nWrite-Host 'ok'  # 끝\n".encode()
    assert rule("a.ps1", body) == "PS_BOM_COMMENTS"
    assert rule("a.ps1", body + "Write-Host '값'\n".encode()) == "PS_NEEDS_BOM"
