"""Windows 注册表字体读取；非 Windows 或失败时返回空列表。"""

from __future__ import annotations

import sys
from os import path

_WINDOWS_FONTS_DIR = r"C:\Windows\Fonts"


def scan_registry_fonts() -> list:
    """
    读取系统与用户字体注册表，返回 [(字体文件绝对路径, '')]。

    非 Windows 环境或注册表不可用时返回空列表。
    """
    if not sys.platform.startswith("win"):
        return []
    try:
        import winreg
    except ImportError:
        return []

    result: list = []
    for hive, sub_key, base_dir in (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts", _WINDOWS_FONTS_DIR),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts", ""),
    ):
        try:
            key = winreg.OpenKey(hive, sub_key)
        except OSError:
            continue
        try:
            count = winreg.QueryInfoKey(key)[1]
        except OSError:
            count = 0
        for i in range(count):
            try:
                value = winreg.EnumValue(key, i)[1]
            except OSError:
                continue
            full = value if base_dir == "" else path.join(base_dir, value)
            if path.isfile(full):
                result.append([full, ""])
        try:
            winreg.CloseKey(key)
        except OSError:
            pass
    return result