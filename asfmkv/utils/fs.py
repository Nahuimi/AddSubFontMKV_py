"""文件系统工具。"""

from __future__ import annotations

import os
import re
from os import path

ILLEGAL_FILENAME_CHARS = re.compile(r'[\\/:\*"><\|]')
# 兼容旧名称
cillegal = ILLEGAL_FILENAME_CHARS
style_read = re.compile('.*\nStyle:.*')


def sanitize_filename(name: str) -> str:
    """将非法文件名字符替换为下划线。"""
    return ILLEGAL_FILENAME_CHARS.sub("_", name)


def unique_path(target: str, is_file: bool = True) -> str:
    """若目标已存在，追加 #N 生成不冲突的新路径（对应原 dExistsPath）。"""

    def exists(candidate: str) -> bool:
        return path.isfile(candidate) if is_file else path.isdir(candidate)

    if not exists(target):
        return target
    stem, ext = path.splitext(target)
    counter = 1
    candidate = f"{stem}#{counter}{ext}"
    while exists(candidate):
        counter += 1
        candidate = f"{stem}#{counter}{ext}"
    return candidate


def ensure_directory(target: str) -> bool:
    """确保目录存在，成功返回 True。"""
    if path.isdir(target):
        return True
    if not target:
        return False
    try:
        os.makedirs(target, exist_ok=True)
        return True
    except OSError:
        return False


def basename_no_ext(filename: str) -> str:
    return path.splitext(path.basename(filename))[0]


def get_file_list(in_path: str, ext_filter=None, subdir: bool = False) -> list:
    """获取目录/文件列表，返回 [(文件名（无扩展名）, 绝对路径), ...]。"""
    ext_filter = [s.lower().strip(". ") for s in (ext_filter or []) if s.strip()]

    def match_ext(ext: str) -> bool:
        return bool(ext_filter) and ext.lower().lstrip(".") in ext_filter

    file_list: list = []
    if path.isdir(in_path):
        if subdir:
            for root, _dirs, files in os.walk(in_path):
                for name in files:
                    if match_ext(path.splitext(name)[1]):
                        file_list.append((path.splitext(name)[0], path.join(root, name)))
        else:
            for name in os.listdir(in_path):
                full = path.join(in_path, name)
                if path.isfile(full) and match_ext(path.splitext(name)[1]):
                    file_list.append((path.splitext(name)[0], full))
    else:
        file_list = [(path.splitext(in_path)[0], in_path)]
    return file_list


# 兼容旧名称
dExistsPath = unique_path
basenameNoEXT = basename_no_ext
getFileList = get_file_list