"""服务：列出字幕所需字体。"""

from __future__ import annotations

import copy
import os
import shutil
import sys
from os import path
from typing import Optional

from ..ass import ass_analyse, ass_event_tags_split, ass_font_list, ass_file_write
from ..core.console import Ansi, colorize
from ..fonts.cmap import char_exists_check
from ..fonts.index import check_ass_font, update_ass_font
from ..fonts.models import FontIndex
from ..utils.fs import get_file_list
from .load_fonts import temple_font_load


def write_non_subset(file_path: str, ass_info: dict) -> None:
    """若字幕含子集化信息，则写出一份恢复字体名的字幕。"""
    if not ass_info["Subset"]:
        return
    ns_dir = path.join(path.dirname(file_path), "NoSubsetSub")
    ns_file = path.join(ns_dir, path.basename(file_path))
    try:
        os.makedirs(ns_dir, exist_ok=True)
        ass_file_write(ns_file, ass_info)
        print(colorize("已恢复字幕: ", Ansi.YELLOW) + colorize(f'"{ns_file}"', Ansi.WHITE))
    except OSError:
        print(colorize(f"[ERROR] 恢复的子集化字幕写入失败\n{sys.exc_info()}", Ansi.RED))


def write_embedded_fonts(file_path: str, ass_info: dict) -> None:
    """抽出字幕中的内嵌字体（输出目录基于字幕文件本身，而不是扫描目录）。"""
    cache_dir = path.join(path.dirname(file_path), "ExtractFonts", path.basename(file_path))
    os.makedirs(cache_dir, exist_ok=True)
    for name, content in ass_info["Fonts"].items():
        with open(path.join(cache_dir, name), mode="wb") as fh:
            fh.write(content)


def collect_ass_fonts(target: str, font_info: FontIndex, config) -> tuple:
    """
    扫描目录或单个字幕，返回 {(字体路径, 索引): [...]} 形式的字体需求表。

    报表输出由 :func:`list_ass_font_scan` 负责，本函数只负责收集。
    """
    ass_font: dict = {}
    work_info = font_info
    fd = ""
    if path.isdir(target):
        if config.fontload:
            work_info = temple_font_load(target, copy.deepcopy(font_info), s_fontload=config.s_fontload)
        for f in get_file_list(target, ["ass", "ssa"], config.s_subdir):
            ass_info = ass_analyse(f[1], config.embedded_font_extract)
            write_non_subset(f[1], ass_info)
            font_list = ass_font_list(ass_info, ass_event_tags_split(ass_info, False),
                                      config.negative_tag_detect)
            if config.embedded_font_extract:
                # 按单个字幕文件定位输出目录；旧实现传入的是扫描根目录，
                # 导致多个字幕的内嵌字体被写到同一目录并互相覆盖。
                write_embedded_fonts(f[1], ass_info)
            if not ass_info["Styles"]:
                print(colorize(f'[ERROR] 缺少参数的ASS/SSA文件！"{f[0]}"', Ansi.RED))
                continue
            ass_font2, work_info = check_ass_font(
                font_list, work_info, only_check=True, check_file=f[0],
                ignore_lost_fonts=config.no_request_font)
            ass_font = update_ass_font(ass_font, ass_font2)
        fd = path.join(target, "Fonts")
    else:
        if config.fontload:
            work_info = temple_font_load(path.dirname(target), copy.deepcopy(font_info),
                                         s_fontload=config.s_fontload)
        ass_info = ass_analyse(target, config.embedded_font_extract)
        write_non_subset(target, ass_info)
        font_list = ass_font_list(ass_info, ass_event_tags_split(ass_info, False),
                                  config.negative_tag_detect)
        if config.embedded_font_extract:
            write_embedded_fonts(target, ass_info)
        if not ass_info["Styles"]:
            print(colorize(f'[ERROR] 缺少参数的ASS/SSA文件！"{target}"', Ansi.RED))
            return {}
        ass_font2, work_info = check_ass_font(font_list, work_info, only_check=True, check_file=target,
                                              ignore_lost_fonts=config.no_request_font)
        ass_font = update_ass_font(ass_font, ass_font2)
        fd = path.join(path.dirname(target), "Fonts")
    if not ass_font:
        print(colorize("[ERROR] 目标路径没有ASS/SSA字幕文件", Ansi.RED))
    return ass_font, fd


def list_ass_font_scan(font_info: FontIndex, config, target: str, *, result_file: Optional[str] = None) -> dict:
    """检查并列出字幕所需字体（对应原 _list_ass_font_scan 的输出部分）。"""
    ass_font, fd_entry = collect_ass_fonts(target, font_info, config)
    if not ass_font:
        return {}

    cpath = target if path.isdir(target) else path.dirname(target)
    copy_dir = path.join(cpath, "Fonts")
    report_lines: list = []
    log_path = ""
    print("")
    if config.copyfont or config.resultw:
        os.makedirs(copy_dir, exist_ok=True)
    if config.resultw:
        log_path = result_file or path.join(copy_dir, "fonts.txt")

    max_num = 0
    out_of_ranges: dict = {}
    if config.char_lost:
        print(colorize("检查字体缺字情况，请稍等...", Ansi.YELLOW))
    for s in ass_font:
        if s[0] != s[1]:
            max_num = max(max_num, len(ass_font[s][0]))
            if config.char_lost:
                print(colorize("正在检查:", Ansi.YELLOW) + " " + colorize(ass_font[s][1], Ansi.WHITE))
                a, _b, out_of_range = char_exists_check(s[0], int(s[1]), ass_font[s][0])
                shown = " ".join(c if c.isprintable() else "U+" + hex(ord(c))[2:].rjust(4, "0").upper()
                                 for c in out_of_range)
                if out_of_range:
                    out_of_ranges[s] = [str(len(out_of_range)), shown]
                elif not a:
                    print(colorize("检查失败:", Ansi.RED) + " " + colorize(ass_font[s][1], Ansi.WHITE))
                    out_of_ranges[s] = ["N", ""]

    print("【详情】")
    width = len(str(max_num))
    for s in ass_font:
        if s[0] != s[1]:
            fp = s[0]
            fn = path.basename(fp)
            ann = ""
            err_show = False
            if config.copyfont:
                try:
                    if not path.exists(path.join(copy_dir, fn)):
                        shutil.copy(fp, path.join(copy_dir, fn))
                        ann = " - copied"
                    else:
                        ann = " - existed"
                except OSError:
                    print("[ERROR]", sys.exc_info())
                    ann = " - copy error"
                    err_show = True
            if config.resultw:
                report_lines.append(f"{ass_font[s][2]} <{path.basename(fn)}>{ann}")
                if out_of_ranges.get(s) and out_of_ranges[s][0] != "N":
                    report_lines.append("{0}{2} chars no found: {1}".format(
                        "".center(width, " "), out_of_ranges[s][1], out_of_ranges[s][0]))
            count_str = str(len(ass_font[s][0])).rjust(width)
            missing_str = out_of_ranges.get(s, ["0"])[0].ljust(width)
            if config.char_lost:
                head = (colorize(f"[{count_str}", Ansi.GREEN) + "-" + colorize(f"{missing_str}]", Ansi.RED)
                        + " " + colorize(ass_font[s][2], Ansi.LIGHT_BLUE) + " " + colorize(f"<{path.basename(fn)}>", Ansi.WHITE)
                        + colorize(ann, Ansi.RED if err_show else Ansi.GREEN))
                print(head)
                if out_of_ranges.get(s) and out_of_ranges[s][0] != "N":
                    print("{0}[ {1} ]".format("".center(width * 2 + 3, " "), colorize(out_of_ranges[s][1], Ansi.RED)))
            else:
                print(colorize(f"[{count_str}]", Ansi.GREEN) + " " + colorize(ass_font[s][2], Ansi.LIGHT_BLUE)
                      + " " + colorize(f"<{path.basename(fn)}>", Ansi.WHITE)
                      + colorize(ann, Ansi.RED if err_show else Ansi.GREEN))
        else:
            if config.resultw:
                report_lines.append(f"{s[0]} - No Found")
                if config.exact_lost:
                    for f in ass_font[s][3]:
                        report_lines.append('{0}"{1}"'.format("".center(4, " "), f))
            pad = "N".center(width * 2 + 1, "N") if config.char_lost else "N".center(width, "N")
            print(colorize(f"[{pad}]", Ansi.RED) + " " + colorize(s[0], Ansi.LIGHT_BLUE) + colorize(" - No Found", Ansi.RED))
            if config.exact_lost:
                for f in ass_font[s][3]:
                    print('{0}"{1}"'.format("".center(width, " "), f))
    # 报表先收集再一次性写入，避免中途异常时文件句柄悬挂
    if log_path:
        try:
            with open(log_path, mode="w", encoding="utf-8-sig") as wfile:
                wfile.writelines(line + "\n" for line in report_lines)
        except OSError:
            print(colorize(f'[ERROR] 字体清单写入失败: "{log_path}"', Ansi.RED))

    print("\n【概览】")
    for s in ass_font:
        if s[0] != s[1]:
            print(colorize(ass_font[s][2], Ansi.GREEN))
    for s in ass_font:
        if s[0] == s[1]:
            print(colorize(s[0], Ansi.RED))
    print("")
    return ass_font


# 兼容旧名称
_write_non_subset = write_non_subset
_write_embedded_fonts = write_embedded_fonts
_list_ass_font_scan = list_ass_font_scan
