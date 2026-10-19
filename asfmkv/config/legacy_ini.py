"""旧 ASFMKVpy.ini 兼容层：把旧字段名/旧写法映射到新配置字段。"""

from __future__ import annotations

import configparser
from os import path
from .model import LEGACY_KEY_MAP

# configparser 会把键名小写化，因此映射也按小写匹配
_LEGACY_KEY_MAP_LOWER = {key.lower(): value for key, value in LEGACY_KEY_MAP.items()}

# 旧 INI 中按字符串直接赋值的字段
_STRING_KEYS = {"mkvout", "assout", "fontout", "subl_local", "sub_name2_lang"}


def _read_ini(ini_path: str, encoding: str) -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    parser.read(ini_path, encoding=encoding)
    return parser


def read_legacy_ini(ini_path: str) -> dict:
    """
    读取旧格式 ASFMKVpy.ini，返回 {新字段名: 原始值}。

    仅处理 [settings] 段；无法识别的键忽略。
    文件不是 UTF-8 时（旧版中文 Windows 常见 GBK 保存）会按 GBK 重试。
    """
    if not path.isfile(ini_path):
        return {}
    try:
        parser = _read_ini(ini_path, "utf-8")
    except UnicodeDecodeError:
        try:
            parser = _read_ini(ini_path, "gbk")
        except (configparser.Error, UnicodeDecodeError, OSError):
            return {}
    except (configparser.Error, OSError):
        # UnicodeDecodeError 不是 configparser.Error 的子类，旧实现会直接崩溃
        return {}
    if "settings" not in parser:
        return {}

    result: dict = {}
    for legacy_key, raw in parser["settings"].items():
        new_key = _LEGACY_KEY_MAP_LOWER.get(legacy_key.lower())
        if new_key is None:
            continue
        value = raw.strip("\"\' ")
        if new_key in _STRING_KEYS:
            if value:
                result[new_key] = value
        elif new_key == "extlist":
            if value:
                result[new_key] = value
        elif new_key == "fontin":
            if value:
                result[new_key] = value.replace("?", "\n")
        else:
            # 其余按布尔处理：'1' 为 True，其余为 False
            result[new_key] = value == "1"
    return result
