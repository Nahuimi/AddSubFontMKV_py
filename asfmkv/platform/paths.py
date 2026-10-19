"""平台相关路径。"""

from __future__ import annotations

import os
import sys
from os import path

APP_NAME = "ASFMKVpy"


def is_frozen() -> bool:
    """是否运行在打包后的可执行文件中（Nuitka / PyInstaller）。"""
    return bool(getattr(sys, "frozen", False)) or "__compiled__" in globals()


def _frozen_dir() -> str:
    """打包后返回可执行文件所在目录。

    Nuitka onefile 下 ``sys.executable`` 指向临时解包目录，
    而 ``sys.argv[0]`` 才是原始 exe 路径；standalone 下两者一致。
    """
    argv0 = sys.argv[0] if sys.argv else ""
    if argv0:
        candidate = path.abspath(argv0)
        if path.isfile(candidate):
            return path.dirname(candidate)
    compiled = globals().get("__compiled__")
    containing = getattr(compiled, "containing_dir", None) if compiled is not None else None
    if containing:
        return path.abspath(containing)
    return path.dirname(path.abspath(sys.executable))


def application_dir() -> str:
    """返回程序所在目录：打包后为 exe 同目录，源码运行时为项目根目录。"""
    if is_frozen():
        return _frozen_dir()
    return path.normpath(path.join(path.dirname(path.abspath(__file__)), "..", ".."))


def default_ini_path() -> str:
    """返回旧版 ASFMKVpy.ini 的默认路径（程序所在目录）。"""
    return path.join(application_dir(), "ASFMKVpy.ini")


def cache_dir() -> str:
    """返回缓存目录（%APPDATA%/ASFMKVpy），不存在则创建。"""
    base = os.getenv("APPDATA") or path.join(path.expanduser("~"), ".config")
    target = path.join(base, APP_NAME)
    os.makedirs(target, exist_ok=True)
    return target


def cache_dir_or_none() -> str | None:
    """返回已存在的缓存目录；不存在返回 None（用于菜单展示）。"""
    base = os.getenv("APPDATA")
    if not base:
        return None
    target = path.join(base, APP_NAME)
    return target if path.isdir(target) else None
