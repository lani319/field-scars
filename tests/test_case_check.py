from __future__ import annotations

import case_check
from conftest import commit, git


def test_import_casing_mismatch(repo, capsys):
    commit(
        repo,
        {
            "src/searchPanel/index.tsx": b"export const P = 1;\n",
            "src/grid/Table.tsx": b"export const T = 1;\n",
            "src/App.tsx": (
                b"import { P } from './SearchPanel';\n"
                b"import { T } from './grid/Table';\n"
                b"const L = import('./grid/table');\n"
                b"import x from '../outside';\n"
            ),
        },
    )
    assert case_check.main(["--no-disk"]) == 1
    out = capsys.readouterr().out
    assert "src/App.tsx:1: imports './SearchPanel' but the tracked file is 'src/searchPanel/index.tsx'" in out
    assert "src/App.tsx:3: imports './grid/table'" in out
    assert ":2:" not in out and ":4:" not in out  # correct import and unresolved import are not reported


def test_collision_in_index(repo, capsys):
    commit(repo, {"src/grid/a.ts": b"a\n"})
    # a case-insensitive disk cannot hold both folders, so add the colliding path to the index directly
    sha = git(repo, "rev-parse", "HEAD:src/grid/a.ts").strip()
    git(repo, "update-index", "--add", "--cacheinfo", f"100644,{sha},src/Grid/b.ts")
    assert case_check.main(["--no-disk"]) == 1
    assert "src/Grid <-> src/grid" in capsys.readouterr().out


def test_disk_casing_drift(repo, capsys):
    commit(repo, {"lib/Util.py": b"x = 1\n"})
    (repo / "lib" / "Util.py").rename(repo / "lib" / "util.py")  # what a pull of a case-only rename leaves behind
    assert case_check.main([]) == 1
    assert "index has 'lib/Util.py', disk has 'lib/util.py'" in capsys.readouterr().out


def test_clean_repo(repo):
    commit(repo, {"src/A.ts": b"import { b } from './b';\n", "src/b.ts": b"export const b = 1;\n"})
    assert case_check.main([]) == 0
