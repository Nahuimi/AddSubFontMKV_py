"""字体索引模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FontIndex:
    """
    字体信息集合。

    :font_name:    {字体名: [绝对路径, 字体索引, 样式dict, 是否为TTC]}
    :font_n_lower: {小写字体名: 原始字体名}
    :font_family:  {家族名: {(斜体, 粗体): [字体名, ...]}}
    :warning_font: {小写字体名: [编码, ...]}（可能无法正常子集化的老旧字体）
    """

    font_name: dict = field(default_factory=dict)
    font_n_lower: dict = field(default_factory=dict)
    font_family: dict = field(default_factory=dict)
    warning_font: dict = field(default_factory=dict)

    def get_by_index(self, index: int):
        """与传统 font_info 列表索引兼容。"""
        values = (self.font_name, self.font_n_lower, self.font_family, self.warning_font)
        if index not in range(4):
            return None
        return values[index]

    # 兼容旧名称
    getByIndex = get_by_index

    def find(self, name: str, italic: int = 0, bold: int = 0) -> Optional[list]:
        """按名称（大小写不敏感）查找字体记录。"""
        if name in self.font_name:
            return self.font_name[name]
        resolved = self.font_n_lower.get(name.lower())
        if resolved is not None:
            return self.font_name.get(resolved)
        return None

    def all_names(self):
        return self.font_name.keys()

    def duplicates(self) -> dict:
        return self.duplicate_fonts

    # 由 FontParser 填充：{(路径1, 路径2): [重复名称, ...]}
    duplicate_fonts: dict = field(default_factory=dict)


# 兼容旧名称
FontInfo = FontIndex


@dataclass
class FontFile:
    """一个字体的定位信息。"""

    path: str
    index: int = 0
    is_collection: bool = False