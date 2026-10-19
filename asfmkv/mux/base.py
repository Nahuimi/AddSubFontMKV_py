"""封装公共逻辑：输出路径推导、字幕注释提取与善后清理。"""

from __future__ import annotations

import os
from os import path

from ..core.console import Ansi, colorize


def resolve_mux_outfile(file: str, out_file: str, make_mks: bool) -> str:
    """推导封装输出路径，存在同名文件时追加 #N。"""
    out_ext = ".mks" if make_mks else ".mkv"
    if (out_file == "" or not path.exists(path.dirname(out_file))
            or path.dirname(out_file) == path.dirname(file)):
        out_file = ".muxed".join([path.splitext(file)[0], out_ext])
    out_file = path.splitext(out_file)[0] + out_ext
    if path.exists(out_file):
        loop = 1
        while path.exists(f"#{loop}".join(path.splitext(out_file))):
            loop += 1
        out_file = f"#{loop}".join([path.splitext(out_file)[0], out_ext])
    return out_file


def subtitle_note(sub_path: str, media_name: str) -> str:
    """从字幕文件名中提取注释（媒体名之后、.subset 之前的部分）。"""
    sub_name = path.splitext(path.basename(sub_path))[0]
    media_at = sub_name.find(media_name)
    # 字幕名里可能不含媒体名（如 CLI 手工指定 --subtitle）；此时整个文件名都是注释，
    # 旧实现会把 find() 的 -1 当成起点，从 len(media_name)-1 处截断，结果随机。
    note = sub_name if media_at < 0 else sub_name[media_at + len(media_name):]
    subset_at = note.find(".subset")
    # 未子集化的字幕（如 "01.zh.ass"）没有 .subset 标记，此时整段都是注释；
    # 旧实现直接切片 [0:-1] 会吃掉注释的最后一个字符（".zh" -> ".z"）。
    return note if subset_at < 0 else note[:subset_at]


def cleanup_after_mux(ass_paths: list, font_paths: list) -> None:
    """封装成功后删除临时字幕与字体。"""
    for p in ass_paths:
        print(colorize("封装成功: ", Ansi.GREEN) + colorize(f'"{p}"', Ansi.WHITE))
        if path.splitext(p)[1][1:].lower() in ("ass", "ssa"):
            try:
                os.remove(p)
            except OSError:
                print(colorize(f'[ERROR] 文件"{p}"删除失败', Ansi.YELLOW))
    for f in font_paths:
        print(colorize("封装成功: ", Ansi.GREEN) + colorize(f'"{f}"', Ansi.WHITE))
        try:
            os.remove(f)
        except OSError:
            print(colorize(f'[ERROR] 文件"{f}"删除失败', Ansi.YELLOW))


# 兼容旧名称
_resolve_mux_outfile = resolve_mux_outfile
_subtitle_note = subtitle_note
_cleanup_after_mux = cleanup_after_mux
