"""字体载入服务：全量载入、工作目录临时载入与追加载入回调。"""

from __future__ import annotations

import os
from os import path
from typing import Optional

from ..core.console import Ansi, colorize
from ..fonts.models import FontIndex
from ..fonts.parser import progress_fonts
from ..fonts.scanner import FONT_EXTS, get_font_file_list


def make_font_loader(config, duplicate_fonts: Optional[dict] = None):
    """
    构造 check_ass_font 需要的追加字体回调。

    :param config: AppConfig
    :param duplicate_fonts: 重复字体累加器，可为 None
    """

    def loader(target: str) -> FontIndex:
        if path.isdir(target):
            fl = get_font_file_list([target], noreg=True)
        else:
            fl = [[target, "0"]]
        return progress_fonts(fl, FontIndex(), quiet=config.start_quiet,
                              duplicate_fonts=duplicate_fonts)

    return loader


def temple_font_load(directory: str, font_info: FontIndex, *, s_fontload: bool = False) -> FontIndex:
    """从字幕所在目录临时载入字体。"""
    font_list: list = []
    print(colorize("正在尝试从字幕所在文件夹载入字体...", Ansi.GREEN))
    if s_fontload:
        for root, _dirs, files in os.walk(directory):
            for name in files:
                full = path.join(root, name)
                if path.isfile(full) and path.splitext(full)[1][1:].lower() in FONT_EXTS:
                    font_list.append([full, "1"])
    else:
        dirs = [directory]
        for name in os.listdir(directory):
            if path.isdir(path.join(directory, name)) and "font" in name.lower():
                dirs.append(path.join(directory, name))
        for folder in dirs:
            for name in os.listdir(folder):
                full = path.join(folder, name)
                if path.isfile(full) and path.splitext(full)[1][1:].lower() in FONT_EXTS:
                    font_list.append([full, "1"])
    if font_list:
        font_info = progress_fonts(font_list, font_info, True)
        print()
    else:
        print(colorize("目录下没有字体", Ansi.GREEN))
    return font_info


def load_fonts(config, using_cache: bool = True, extra_dirs: Optional[list] = None,
               duplicate_fonts: Optional[dict] = None) -> FontIndex:
    """读取字体信息，返回新的 FontIndex。"""
    dirs = list(config.fontin) + list(extra_dirs or [])
    # 注意：f_priority 只影响 check_ass_font 的字体索引合并，与 progress_fonts 的
    # overwrite 语义无关；旧实现把它按位置传成了 overwrite，导致启用优先级时
    # 重复字体检测被静默关闭。
    return progress_fonts(get_font_file_list(dirs), FontIndex(),
                          using_cache=using_cache, quiet=config.start_quiet,
                          duplicate_fonts=duplicate_fonts)


# 兼容旧名称
templeFontLoad = temple_font_load
