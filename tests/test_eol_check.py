from __future__ import annotations

import eol_check
from conftest import commit, git


def test_flip_is_found_and_fixed(repo, capsys):
    commit(repo, {"a.txt": b"one\r\ntwo\r\n", "b.txt": b"x\n"})
    (repo / "a.txt").write_bytes(b"one\nTWO\n")  # a rewrite tool turned CRLF into LF
    assert eol_check.main([]) == 1
    assert "a.txt: HEAD=crlf -> now=lf" in capsys.readouterr().out
    assert eol_check.main(["--fix"]) == 0
    assert (repo / "a.txt").read_bytes() == b"one\r\nTWO\r\n"  # style restored, edit kept
    assert eol_check.main([]) == 0


def test_real_edit_in_same_style_is_clean(repo):
    commit(repo, {"a.txt": b"one\r\ntwo\r\n"})
    (repo / "a.txt").write_bytes(b"one\r\nthree\r\n")
    assert eol_check.main([]) == 0


def test_partial_flip_to_mixed(repo, capsys):
    commit(repo, {"a.txt": b"1\n2\n3\n"})
    (repo / "a.txt").write_bytes(b"1\n2\r\n3\n")
    assert eol_check.main([]) == 1
    assert "now=mixed" in capsys.readouterr().out
    assert eol_check.main(["--fix"]) == 0
    assert (repo / "a.txt").read_bytes() == b"1\n2\n3\n"


def test_staged_mode_reads_index(repo):
    commit(repo, {"a.txt": b"a\r\nb\r\n"})
    (repo / "a.txt").write_bytes(b"a\nb\nc\n")
    assert eol_check.main(["--staged"]) == 0  # nothing staged yet
    git(repo, "add", "a.txt")
    assert eol_check.main(["--staged"]) == 1


def test_mixed_head_is_not_auto_fixed(repo):
    commit(repo, {"a.txt": b"a\r\nb\n"})
    (repo / "a.txt").write_bytes(b"a\nb\n")
    assert eol_check.main(["--fix"]) == 1
    assert (repo / "a.txt").read_bytes() == b"a\nb\n"


def test_binary_ignored(repo):
    commit(repo, {"img.bin": b"\0\r\n\0"})
    (repo / "img.bin").write_bytes(b"\0\n\0")
    assert eol_check.main([]) == 0


def test_scan_flags_unprotected_mixed_repo(repo, capsys):
    commit(repo, {"a.txt": b"a\r\n", "b.txt": b"b\n"})
    assert eol_check.main(["--scan"]) == 1
    assert "RISK" in capsys.readouterr().out
    commit(repo, {".gitattributes": b"* text=auto\n"})
    assert eol_check.main(["--scan"]) == 0


def test_scan_ignores_gitattributes_that_do_not_normalise(repo, capsys):
    # an LFS-only .gitattributes exists but leaves text files byte-for-byte
    commit(repo, {".gitattributes": b"*.mp4 filter=lfs -text\n", "a.txt": b"a\r\n", "b.txt": b"b\n"})
    assert eol_check.main(["--scan"]) == 1
    assert "RISK" in capsys.readouterr().out
    commit(repo, {".gitattributes": b"*.txt text=auto\n"})
    assert eol_check.main(["--scan"]) == 0
