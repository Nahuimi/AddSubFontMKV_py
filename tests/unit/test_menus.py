"""交互菜单行为测试：日志阅读暂停与流程返回值。"""

from __future__ import annotations

import asfmkv.ui.menus as menus


class _FakeApp:
    """只提供 run_subset_workflow 早退路径所需的最小状态。"""

    def __init__(self, config):
        self.config = config
        self.extlist = list(config.extlist)


def test_run_subset_workflow_returns_false_when_cancelled(config, monkeypatch):
    """用户在路径输入阶段取消时返回 False，调用方不应暂停。"""
    monkeypatch.setattr(menus, "prompt_input_path", lambda *a, **k: ("", [], False, [], False, True))
    monkeypatch.setattr(menus, "clear_screen", lambda: None)

    assert menus.run_subset_workflow(_FakeApp(config), 1) is False


def test_run_subset_workflow_returns_true_and_pauses_after_run(config, monkeypatch):
    """正常执行后返回 True，菜单层据此等待回车，避免日志被清屏。"""
    monkeypatch.setattr(menus, "prompt_input_path", lambda *a, **k: ("x", [], False, [], False, False))
    monkeypatch.setattr(menus, "clear_screen", lambda: None)

    app = _FakeApp(config)
    assert menus.run_subset_workflow(app, 1) is True


def test_font_subset_menu_waits_after_workflow(config, monkeypatch):
    """font_subset_menu 在流程结束后必须等待回车，日志才不会被立刻清屏。"""
    calls = {"waited": 0, "picked": 0}

    def fake_choice(prompt, keys):
        calls["picked"] += 1
        # 第一次按 A(1) 进入子集化；第二次按 L（按键串第 19 位）回到上级菜单
        return 1 if calls["picked"] == 1 else keys.index("L") + 1

    monkeypatch.setattr(menus, "clear_screen", lambda: None)
    monkeypatch.setattr(menus, "prompt_choice", fake_choice)
    monkeypatch.setattr(menus, "run_subset_workflow", lambda app, work: calls.update(ran=work) or True)
    monkeypatch.setattr(menus, "wait_enter", lambda *a, **k: calls.__setitem__("waited", calls["waited"] + 1))

    class _App:
        instead_ff = False
        no_mkvmerge = False
        extlist = list(config.extlist)

        def __init__(self, cfg):
            self.config = cfg

    menus.font_subset_menu(_App(config))
    assert calls["ran"] == 1
    assert calls["waited"] == 1


def test_font_subset_menu_toggles_match_strict(config, monkeypatch):
    """[7] 严格字幕匹配 的开关曾因比较 work == 22（不可达）而失效。"""
    choices = iter([9, 19])  # 第一次按 [7]，第二次按 [L] 返回上级菜单
    monkeypatch.setattr(menus, "clear_screen", lambda: None)
    monkeypatch.setattr(menus, "prompt_choice", lambda prompt, keys: next(choices))

    class _App:
        instead_ff = False
        no_mkvmerge = False

        def __init__(self, cfg):
            self.config = cfg

        def set_config(self, **kwargs):
            self.config = self.config.with_overrides(**kwargs)

    app = _App(config)
    assert app.config.match_strict is True
    menus.font_subset_menu(app)
    assert app.config.match_strict is False
