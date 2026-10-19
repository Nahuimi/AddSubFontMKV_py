"""终端输出：ANSI 颜色、显示宽度补齐与分级日志。

UI 菜单允许直接 print；核心与服务层统一走 :class:`Logger`，受日志级别控制。
"""

from __future__ import annotations

import sys
import unicodedata
from enum import Enum
from typing import Optional, TextIO


class Ansi(Enum):
    """终端 ANSI 前景色。"""

    BLACK = 30
    RED = 31
    GREEN = 32
    YELLOW = 33
    BLUE = 34
    PURPLE = 35
    LIGHT_BLUE = 36
    WHITE = 37


textFrontColor = Ansi


def colorize(text: str, color: Ansi = Ansi.RED, bold: bool = True) -> str:
    """用 ANSI 序列包裹文本。"""
    style = "1;" if bold else ""
    return f"\033[{style}{color.value}m{text}\033[0m"


def status(text: str, ok: bool, ok_color: Ansi = Ansi.RED, fail_color: Ansi = Ansi.YELLOW) -> str:
    """按布尔值选择颜色的状态文本（对应原 showColorBool）。"""
    return colorize(text, ok_color if ok else fail_color)


def pad_display(text: str, width: int = 50, total: int = 60) -> str:
    """按终端显示宽度截断并补齐（全角按 2 计）。保留原 outputSameLength 行为。"""
    shown = ""
    length = 0
    for ch in reversed(text):
        length += 2 if unicodedata.east_asian_width(ch) in ("F", "W", "A") else 1
        if length >= width:
            shown = ".." + shown
            break
        shown = ch + shown
    return shown.ljust(total - (length - len(shown)), " ")


# 兼容旧名称
showColorBool = status
outputSameLength = pad_display


class Level(Enum):
    """日志级别。"""

    QUIET = 0
    NORMAL = 1
    VERBOSE = 2
    DEBUG = 3


class Logger:
    """分级日志：QUIET 只输出错误，NORMAL 默认，VERBOSE/DEBUG 逐步详细。"""

    def __init__(self, level: Level = Level.NORMAL, stream: Optional[TextIO] = None):
        self.level = level
        self.stream = stream if stream is not None else sys.stdout

    def _emit(self, text: str, *, end: str = "\n") -> None:
        print(text, end=end, file=self.stream, flush=False)

    def error(self, message: str, *, color: Ansi = Ansi.RED) -> None:
        self._emit(colorize(message, color))

    def warning(self, message: str) -> None:
        if self.level.value >= Level.NORMAL.value:
            self._emit(colorize(message, Ansi.YELLOW))

    def info(self, message: str = "", *, end: str = "\n") -> None:
        if self.level.value >= Level.NORMAL.value:
            self._emit(message, end=end)

    def verbose(self, message: str) -> None:
        if self.level.value >= Level.VERBOSE.value:
            self._emit(message)

    def debug(self, message: str) -> None:
        if self.level.value >= Level.DEBUG.value:
            self._emit(message)

    def progress(self, message: str) -> None:
        """进度行（原地覆盖），NORMAL 及以上输出。"""
        if self.level.value >= Level.NORMAL.value:
            self._emit(message, end="")