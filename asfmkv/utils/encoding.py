"""编码检测工具。"""

from __future__ import annotations

import codecs
import locale

import chardet
# chardet 7 起 chardet.universaldetector 子模块已弃用，改用顶层导出（5.x 亦可用）
from chardet import UniversalDetector


# UTF-8 BOM 前缀
_BOM_UTF8 = b"\xef\xbb\xbf"
_BOM_PREFIXES = (_BOM_UTF8, b"\xff\xfe\x00\x00", b"\xff\xfe", b"\xfe\xff")


def _bom_encoding(head: bytes) -> str | None:
    """按 BOM 前缀判断编码；无 BOM 返回 None。

    chardet 常把带 BOM 的 UTF-8 报成 ``utf-8``，而 Python 的 ``utf-8``
    解码器不会剥离 BOM，会把 ``\ufeff`` 留在首行导致首个段落头识别失败。
    """
    if head.startswith(_BOM_UTF8):
        return "utf-8-sig"
    if head.startswith(b"\xff\xfe\x00\x00"):
        return "utf-32"
    if head.startswith(b"\xff\xfe"):
        return "utf-16"
    if head.startswith(b"\xfe\xff"):
        return "utf-16"
    return None


def normalize_encoding(encoding: str | None, head: bytes = b"", *, default: str = "utf-8") -> str:
    """把检测结果归一为可用的编码名：BOM 优先，gb2312 归一为 gbk。"""
    bom = _bom_encoding(head)
    if bom:
        return bom
    if not encoding:
        return default
    return encoding.replace("gb2312", "gbk")


def detect_encoding(path_or_bytes, *, default: str = "utf-8") -> str:
    """检测文件/字节的文本编码：BOM 优先，其余用 chardet，gb2312 归一为 gbk。"""
    if isinstance(path_or_bytes, (bytes, bytearray)):
        raw = bytes(path_or_bytes)
        return normalize_encoding(chardet.detect(raw).get("encoding"), raw, default=default)
    head = bytearray()
    detector = UniversalDetector()
    with open(path_or_bytes, mode="rb") as fh:
        for block in fh:
            if len(head) < 4:
                head.extend(block[:4 - len(head)])
            detector.feed(block)
            if detector.done:
                break
    return normalize_encoding(detector.result.get("encoding"), bytes(head), default=default)


def preferred_encoding() -> str:
    """当前系统区域对应的文本编码名。"""
    try:
        return codecs.lookup(locale.getlocale()[1]).name
    except (LookupError, TypeError):
        return "utf-8"