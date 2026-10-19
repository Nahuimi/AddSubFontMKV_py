"""ASS/SSA 文档模型与常量。"""

from __future__ import annotations

# 需要记录行号的段落名
TAG_NAMES = ("Info", "Styles", "Events", "Fonts", "Graphics", "Garbage")

# [Script Info] 中的子集化还原信息前缀
SUBSET_PREFIX = "; Font Subset: "


def new_tag_lines() -> dict:
    """新建段落名到行号的映射，初始均为 -1。"""
    return {name: -1 for name in TAG_NAMES}


def new_ass_info() -> dict:
    """新建空的 ASS 信息字典。"""
    return {
        "Lines": new_tag_lines(),
        "Info": {},
        "Styles": {},
        "Events": [],
        "Fonts": {},
        "Graphics": {},
        "Garbage": {},
        "Subset": {},
    }
