"""pytest 公共夹具：合成 ASS 字幕与配置。"""

from __future__ import annotations

import os

import pytest


def _ass_lines(fontname: str = "Arial", events: int = 160) -> list:
    lines = ["[Script Info]\n", "Title: Fixture\n", "ScriptType: v4.00+\n", "\n",
             "[V4+ Styles]\n", "Format: Name, Fontname, Fontsize, Bold, Italic\n",
             f"Style: Default,{fontname},20,-1,0\n", "Style: Alt,Times New Roman,18,0,0\n", "\n",
             "[Events]\n", "Format: Layer, Start, End, Style, Text\n"]
    for i in range(events):
        lines.append(f"Dialogue: 0,0:00:{i % 60:02d}.00,0:00:{(i % 60) + 1:02d}.00,Default,"
                     f"Hello 世界 {i} {{\\b1}}bold{{\\b0}}\\NSecond {i}\n")
    return lines


@pytest.fixture
def ass_file(tmp_path):
    """生成一个 UTF-8-SIG 的合成 ASS 文件并返回其路径。"""
    path = tmp_path / "sub.ass"
    path.write_text("".join(_ass_lines()), encoding="utf-8-sig")
    return str(path)


@pytest.fixture
def config():
    from asfmkv.config import load_config
    return load_config(ini_path=str(".nonexistent.ini"))


@pytest.fixture
def sample_font_name():
    """返回系统上可用的一个字体名（优先 Arial）。"""
    from asfmkv.fonts.models import FontIndex
    from asfmkv.fonts.parser import progress_fonts
    from asfmkv.fonts.scanner import get_font_file_list

    fl = get_font_file_list(noreg=False)[:80]
    info = progress_fonts(fl, FontIndex(), quiet=True)
    for name in info.font_name:
        if name.lower() == "arial":
            return name
    return next(iter(info.font_name))
