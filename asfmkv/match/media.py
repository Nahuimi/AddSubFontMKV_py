"""媒体文件扫描。"""

from __future__ import annotations

from ..utils.fs import get_file_list


def list_media(in_path: str, extlist, subdir: bool = False) -> list:
    """列出目录下匹配扩展名的媒体文件。"""
    return get_file_list(in_path, extlist, subdir)
