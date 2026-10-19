"""文件系统与子进程工具测试。"""

from __future__ import annotations

import os

from asfmkv.utils.fs import ensure_directory, get_file_list, sanitize_filename, unique_path
from asfmkv.utils.proc import run


def test_sanitize_filename():
    assert sanitize_filename('a/b:c*d"e<f>g|h') == "a_b_c_d_e_f_g_h"


def test_unique_path(tmp_path):
    target = tmp_path / "f.txt"
    target.write_text("x", encoding="utf-8")
    assert unique_path(str(target)).endswith("f#1.txt")
    (tmp_path / "f#1.txt").write_text("x", encoding="utf-8")
    assert unique_path(str(target)).endswith("f#2.txt")


def test_ensure_directory(tmp_path):
    target = tmp_path / "a" / "b"
    assert ensure_directory(str(target)) is True
    assert os.path.isdir(target)
    assert ensure_directory(str(target)) is True


def test_get_file_list(tmp_path):
    (tmp_path / "a.ass").write_text("x", encoding="utf-8")
    (tmp_path / "b.mkv").write_text("x", encoding="utf-8")
    found = get_file_list(str(tmp_path), ["ass"])
    assert [name for name, _ in found] == ["a"]


def test_run_echo_returns_completed_process():
    proc = run(["python", "-c", "print('hello')"])
    assert proc.returncode == 0
    assert "hello" in proc.stdout


def test_run_missing_executable_returns_127():
    proc = run(["asfmkv-no-such-tool-xyz", "-V"])
    assert proc.returncode == 127
    assert proc.stdout == ""
