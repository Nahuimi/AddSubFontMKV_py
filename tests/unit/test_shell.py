"""控制台交互层测试：choice 不可用时的文本回退。"""

from __future__ import annotations

import pytest

from asfmkv.platform.shell import Shell


def test_choose_falls_back_to_input(monkeypatch):
    """非 Windows / 缺少 choice 时不能用死循环，应退化为文本输入。"""
    shell = Shell(enabled=False)
    monkeypatch.setattr("builtins.input", lambda prompt="": "b")
    assert shell.choose("请选择: ", "abc") == 2


def test_confirm_falls_back_to_input(monkeypatch):
    shell = Shell(enabled=False)
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    assert shell.confirm() is True
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    assert shell.confirm() is False


def test_eof_exits_instead_of_looping(monkeypatch):
    """标准输入关闭（管道运行菜单）时应退出，而不是让菜单主循环空转。"""

    def _raise(prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", _raise)
    shell = Shell(enabled=False)
    with pytest.raises(SystemExit):
        shell.choose("请选择: ", "ab")
