"""ASFMKV：AddSubFontMKV 的字幕字体子集化与封装工具。"""

from __future__ import annotations

APP_NAME = "ASFMKVpy"
APP_TITLE = "AddSubFontMKV Python Remake"

# 发布工作流会在打包前生成 asfmkv/_version.py（不入库）写入本次发布的版本号；
# 源码运行时没有这个文件，回退到下面的开发版本号。
try:
    from ._version import APP_VERSION
except ImportError:  # pragma: no cover - 只有打包时存在 _version.py
    APP_VERSION = "Pre25-refactor"

from .config import AppConfig, load_config

__all__ = ["APP_NAME", "APP_TITLE", "APP_VERSION", "AppConfig", "load_config"]
__version__ = APP_VERSION
