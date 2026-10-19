"""CRC 计算工具（与旧版缓存键保持一致）。"""

from __future__ import annotations

import zlib
from os import path


def dir_crc(directory: str) -> str:
    """目录名（小写）的 CRC，用作字体缓存文件名。"""
    return hex(zlib.crc32(directory.lower().encode("utf-8")))[2:].upper().rjust(8, "0")


def font_crc(font_path: str) -> str:
    """字体文件标识 CRC：路径（小写）+ 大小 + 创建时间。"""
    return hex(zlib.crc32((font_path.lower() + str(path.getsize(font_path))
                           + str(path.getctime(font_path))).encode("utf-8")))[2:].upper().rjust(8, "0")


def subset_crc(glyph_set: str, name: str) -> str:
    """子集化字体的 CRC 标识（用于新字体名）。"""
    value = hex(zlib.crc32((glyph_set + name).encode("utf-8", "replace")))[2:].upper()
    return value if len(value) >= 8 else "0" + value