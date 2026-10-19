"""控制台交互封装：choice / cls / pause / title。

非 Windows 或缺少 choice 命令时优雅降级，保证核心逻辑可运行。
所有外部命令一律通过参数列表调用，不拼接 shell 字符串。
"""

from __future__ import annotations

import ctypes
import subprocess
import sys


class Shell:
    """控制台交互的抽象层。"""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled and sys.platform.startswith("win")
        self.no_choice = False

    def choose(self, prompt: str, keys: str) -> int:
        """基于 Windows choice 的按键选择，返回序号（从 1 开始）。

        非 Windows（或 choice 命令缺失）时退化为 ``input()`` 文本选择，
        避免菜单在主循环里反复取不到输入而死循环。
        """
        if not self.enabled:
            return self._input_choice(prompt, keys)
        try:
            # choice 需要直接读写控制台，因此不捕获输出
            return subprocess.run(["choice", "/M", prompt, "/C", keys], check=False).returncode
        except OSError:
            return self._input_choice(prompt, keys)

    def confirm(self, prompt: str = "是否继续") -> bool:
        """Yes/No 确认，Y 为同意。"""
        if not self.enabled:
            return self._input_choice(prompt, "YN") == 1
        try:
            return subprocess.run(["choice", "/M", prompt], check=False).returncode == 1
        except OSError:
            return self._input_choice(prompt, "YN") == 1

    def clear(self) -> None:
        if self.enabled:
            self._cmd_builtin("cls")

    def pause(self) -> None:
        if self.enabled:
            self._cmd_builtin("pause")

    def wait_enter(self, prompt: str = "按回车键返回功能菜单...") -> None:
        """等待用户按回车。

        相比 ``pause``（任意键），这里用 ``input`` 等待回车，
        并确保此前的日志已刷新到终端，避免长日志被立即清屏。
        """
        try:
            input(prompt)
        except (EOFError, KeyboardInterrupt):
            pass

    def title(self, text: str) -> None:
        """设置控制台标题（直接调用 Win32 API，无需 shell 拼接）。"""
        if not self.enabled:
            return
        try:
            ctypes.windll.kernel32.SetConsoleTitleW(text)
        except (AttributeError, OSError):
            pass

    def probe_choice(self) -> bool:
        """检测 choice 命令是否可用，返回 True 表示不可用。"""
        if not self.enabled:
            self.no_choice = True
            return True
        try:
            self.no_choice = subprocess.run(
                ["choice", "/?"], check=False,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0
        except OSError:
            self.no_choice = True
        return self.no_choice

    @staticmethod
    def _cmd_builtin(command: str) -> None:
        """执行 cmd 内置命令（cls / pause），失败时静默忽略。"""
        try:
            subprocess.run(["cmd", "/c", command], check=False)
        except OSError:
            pass

    @staticmethod
    def _input_choice(prompt: str, keys: str) -> int:
        """choice 不可用时的文本输入回退，返回序号（从 1 开始）。

        空输入与非法输入都会重新询问；标准输入关闭（EOF）时直接退出，
        以免上层菜单循环永远拿不到有效输入。
        """
        choices = "/".join(keys.upper())
        while True:
            try:
                answer = input(f'{prompt}（输入 {choices} 之一）: ').strip().upper()
            except KeyboardInterrupt:
                raise SystemExit(1) from None
            except EOFError:
                raise SystemExit("[ERROR] 标准输入已关闭，交互菜单不可用；请改用命令行参数模式") from None
            if len(answer) == 1 and answer in keys.upper():
                return keys.upper().index(answer) + 1
            print("输入有误，请重新输入")


# 进程内共享的默认 Shell，供模块级便捷函数使用
_default_shell = Shell()


def clear_screen() -> None:
    """清屏（等价于 cls）。"""
    _default_shell.clear()


def pause() -> None:
    """暂停等待按键。"""
    _default_shell.pause()


def wait_enter(prompt: str = "按回车键返回功能菜单...") -> None:
    """等待用户按回车（日志较多时用于避免立即清屏）。"""
    _default_shell.wait_enter(prompt)


def set_title(text: str) -> None:
    """设置控制台标题。"""
    _default_shell.title(text)


def prompt_choice(prompt: str, keys: str) -> int:
    """基于 Windows choice 的按键选择，返回序号（从 1 开始）。"""
    return _default_shell.choose(prompt, keys)


def confirm(prompt: str = "是否继续") -> bool:
    """Yes/No 确认，Y 为同意。"""
    return _default_shell.confirm(prompt)


# 兼容旧名称
cls = clear_screen
