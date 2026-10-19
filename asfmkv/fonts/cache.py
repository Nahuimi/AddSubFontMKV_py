"""字体缓存：JSON + zlib，按目录 CRC 分文件存储。

接口可在后续版本替换为 SQLite，而调用方无需改动。
"""

from __future__ import annotations

import json
import os
import zlib
from os import path
from typing import Optional

from ..utils.crc import dir_crc
from ..utils.fs import ensure_directory

# 当前字体缓存版本，小于该版本的字体缓存会被删除重建
CURRENT_FONT_CACHE_VER = 2


class FontCache:
    """按字体所在目录分片缓存解析结果。"""

    def __init__(self, cache_root: str, version: int = CURRENT_FONT_CACHE_VER):
        self.cache_root = cache_root
        self.version = version
        self._dir_keys: dict = {}
        self._warned = False
        ensure_directory(cache_root)

    def dir_key(self, directory: str) -> str:
        """目录对应的缓存键（同一目录复用）。"""
        lowered = directory.lower()
        if lowered not in self._dir_keys:
            self._dir_keys[lowered] = dir_crc(lowered)
        return self._dir_keys[lowered]

    def load(self, dir_key: str) -> dict:
        """读取单个目录的缓存；版本过旧或损坏时返回空字典并清理文件。"""
        cache_file = path.join(self.cache_root, dir_key)
        legacy_file = path.join(self.cache_root, f"{dir_key}.json")
        if path.exists(cache_file):
            try:
                with open(cache_file, mode="rb") as fh:
                    cache = json.loads(zlib.decompress(fh.read()).decode("utf-8"))
                if cache.get("?version", 0) < self.version:
                    print(f'\n\033[1;31m[WARNING] 已移除旧版本字体缓存文件 "{dir_key}"\033[0m')
                    os.remove(cache_file)
                    return {}
                return cache
            except Exception:
                print(f'\n\033[1;31m[ERROR] 缓存文件读取失败 "{dir_key}"\033[0m')
                try:
                    os.remove(cache_file)
                except OSError:
                    pass
                return {}
        if path.exists(legacy_file):
            try:
                with open(legacy_file, mode="r", encoding="utf-8") as fh:
                    cache = json.load(fh)
            except Exception:
                print(f'\n\033[1;31m[ERROR] 缓存文件读取失败 "{dir_key}.json"\033[0m')
                return {}
            print(f'\n\033[1;33m[FIX] 已禁用旧版缓存 "{dir_key}.json"\033[0m')
            try:
                if not isinstance(list(cache.values())[0]["0"][3], dict):
                    return {}
            except (IndexError, KeyError, TypeError):
                return {}
            return cache
        return {}

    def _warn_unwritable(self, exc: Optional[OSError] = None) -> None:
        """缓存目录不可写时只提示一次，不影响主流程。"""
        if self._warned:
            return
        self._warned = True
        detail = f"（{exc}）" if exc else ""
        print(f'\n\033[1;33m[WARNING] 字体缓存目录不可写，本次跳过缓存{detail}\033[0m')

    def save(self, dir_key: str, cache: dict) -> None:
        """写入单个目录的缓存（先写临时文件再原子替换，避免中断留下半个文件）。

        缓存只是加速手段：目录不可写（只读环境、受限账户）时只提示一次并跳过，
        不应让调用方因此崩溃。
        """
        if not ensure_directory(self.cache_root):
            self._warn_unwritable()
            return
        target = path.join(self.cache_root, dir_key)
        tmp_path = f"{target}.tmp"
        try:
            with open(tmp_path, mode="wb") as fh:
                fh.write(zlib.compress(json.dumps(cache, ensure_ascii=False).encode("utf-8")))
            os.replace(tmp_path, target)
        except OSError as exc:
            self._warn_unwritable(exc)
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    def clear(self) -> None:
        """删除所有缓存文件（新版 CRC 文件与旧版 .json）。

        只删除形如 ``XXXXXXXX`` / ``XXXXXXXX.json``（8 位十六进制 CRC）的文件，
        避免误删用户放在缓存目录里的其他内容。
        """
        if not path.isdir(self.cache_root):
            return
        for name in os.listdir(self.cache_root):
            stem, ext = path.splitext(name)
            if ext and ext not in (".json", ".tmp"):
                continue
            if len(stem) != 8 or any(c not in "0123456789abcdefABCDEF" for c in stem):
                continue
            full = path.join(self.cache_root, name)
            if path.isfile(full):
                try:
                    os.remove(full)
                except OSError:
                    pass