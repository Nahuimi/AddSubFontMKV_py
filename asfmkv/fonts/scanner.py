"""字体文件扫描：注册表字体 + 自定义目录字体。"""

from __future__ import annotations

import os
from os import path
from typing import Optional

from ..platform.windows_registry import scan_registry_fonts

# 支持的字体扩展名
FONT_EXTS = ("ttf", "ttc", "otf", "otc")

# 自定义目录字体的来源标记（与原脚本保持一致）
CUSTOM_SOURCE = "custom"


def get_font_file_list(custom_path: Optional[list] = None, noreg: bool = False) -> list:
    """获取字体文件清单 [[绝对路径, 来源('': 注册表, 'custom': 自定义目录)], ...]。"""
    file_list: list = []
    if not noreg:
        file_list.extend(scan_registry_fonts())

    custom_path = custom_path or []
    if custom_path:
        print("\033[1;33m请稍等，正在获取自定义文件夹中的字体\033[0m")
        for folder in custom_path:
            if not path.isdir(folder):
                continue
            for root, _dirs, files in os.walk(folder):
                for name in files:
                    full = path.join(root, name)
                    if path.splitext(full)[1][1:].lower() in FONT_EXTS:
                        file_list.append([full, CUSTOM_SOURCE])
    return file_list