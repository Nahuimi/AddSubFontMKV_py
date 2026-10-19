"""服务：完整处理流程（分析 -> 检查字体 -> 子集化 -> 替换 -> 可选封装）。"""

from __future__ import annotations

import os
import sys
from os import path
from typing import Optional

from ..ass import ass_analyse, ass_event_tags_split, ass_font_change, ass_font_list
from ..core.console import Ansi, colorize
from ..fonts.index import check_ass_font, update_ass_font
from ..fonts.models import FontIndex
from ..fonts.subsetter import subset_fonts
from ..mux import MuxJob, mux_with_ffmpeg, mux_with_mkvmerge


def run_pipeline(font_info: FontIndex, ass_paths: list, config, out_dir: Optional[list] = None,
                 mux: bool = False, vpath: str = "", ass_langs: Optional[dict] = None,
                 ff_muxer: int = 0, force_sub_track: str = "?", make_mks: bool = False,
                 font_loader=None) -> tuple:
    """
    完整处理流程。

    :param ff_muxer: 0 = mkvmerge, 1 = FFmpeg, 2 = ASS/SSA 内嵌
    :param font_loader: 追加字体回调（check_ass_font 使用）
    返回 (new_ass_paths, new_font_name, mux_return_code)
    """
    ass_langs = ass_langs or {}
    out_dir = list(out_dir or ["", "", ""])
    print("")
    resolved_out = ["", "", ""]
    for i, raw in enumerate(out_dir[:3]):
        if raw is None or raw == "":
            resolved_out[i] = ""
            continue
        if raw.startswith("?"):
            # 与配置项一致的语义："?子目录" 表示媒体所在目录下的子目录
            raw = path.join(path.dirname(vpath) if vpath else os.getcwd(), raw[1:])
        try:
            # 统一用 makedirs：旧实现要求父目录已存在，相对路径/多级路径会被静默丢弃
            os.makedirs(raw, exist_ok=True)
            if path.isdir(raw):
                resolved_out[i] = raw
        except OSError:
            print(colorize(f"[ERROR] 创建输出文件夹错误\n[ERROR] {sys.exc_info()}", Ansi.RED))
            resolved_out[i] = ""
    out_dir = resolved_out

    multi_ass: dict = {}
    broken_subtitles: set = set()
    ass_font: dict = {}
    new_ass_paths: list = []
    font_sub_dir = ""

    if not config.notfont:
        for sub_path in ass_paths:
            if path.splitext(sub_path)[1][1:].lower() not in ("ass", "ssa"):
                multi_ass[sub_path] = (None, None)
                continue
            ass_info = ass_analyse(sub_path)
            tag_split = ass_event_tags_split(ass_info, False)
            font_list = ass_font_list(ass_info, tag_split, config.negative_tag_detect)
            if font_list is None:
                print(colorize(f'[ERROR] 缺少参数的ASS/SSA文件！"{path.basename(sub_path)}"', Ansi.RED))
                broken_subtitles.add(sub_path)
                continue
            multi_ass[sub_path] = (ass_info, tag_split)
            ass_font2, font_info = check_ass_font(
                font_list, font_info, loader=font_loader,
                ignore_lost_fonts=config.no_request_font, warning_stop=config.warning_stop,
                f_priority=config.f_priority)
            ass_font = update_ass_font(ass_font, ass_font2)
            if ass_font is None:
                return None, None, -2

        ass_name = path.splitext(path.basename(ass_paths[0]))[0]
        default_font_dir = path.join(path.dirname(ass_paths[0]), "Fonts")
        if out_dir[1] == "":
            out_dir[1] = default_font_dir
        if not path.isdir(out_dir[1]):
            try:
                os.mkdir(out_dir[1])
                font_sub_dir = path.join(out_dir[1], ass_name)
            except OSError:
                font_sub_dir = path.join(path.dirname(out_dir[1]), ass_name)
        else:
            font_sub_dir = path.join(out_dir[1], ass_name)

        print(colorize("字幕所需字体", Ansi.WHITE, bold=True))
        for af in ass_font.values():
            print(colorize(f'"{af[2]}"', Ansi.WHITE, bold=True) + f": 字符数[" + colorize(str(len(af[0])), Ansi.YELLOW) + "]")

        new_font_name = subset_fonts(ass_font, font_sub_dir, ff_muxer == 2,
                                     char_compatible=config.char_compatible,
                                     ignore_lost=config.ignore_lost, error_stop=config.error_stop)
        if new_font_name is None:
            return [], {}, -2
        for sub_path in ass_paths:
            if path.splitext(sub_path)[1][1:].lower() not in ("ass", "ssa"):
                new_ass_paths.append(sub_path)
            elif sub_path in broken_subtitles:
                # 解析失败的字幕已在前面报错；此处跳过，避免 multi_ass[sub_path] KeyError
                continue
            elif len(multi_ass[sub_path][0]["Events"]) == 0:
                continue
            else:
                new_ass_paths.append(ass_font_change(new_font_name, sub_path, multi_ass[sub_path][0],
                                                     multi_ass[sub_path][1], out_dir[0], embedded=ff_muxer == 2))

        if ff_muxer == 2:
            # 内嵌模式：字体已写入每一份字幕，全部处理完后再统一删除临时子集字体。
            # 旧实现每处理一份字幕就删字体，导致多字幕时第二份开始报 FileNotFoundError。
            for font_path in sorted({f[0] for f in new_font_name.values()}):
                try:
                    os.remove(font_path)
                except OSError:
                    pass
            try:
                os.rmdir(font_sub_dir)
            except OSError:
                pass
    else:
        new_ass_paths = ass_paths
        new_font_name = {}

    if not mux:
        return new_ass_paths, new_font_name, -1

    if out_dir[2] == "":
        out_dir[2] = path.dirname(vpath)
    if not path.isdir(out_dir[2]):
        try:
            os.mkdir(out_dir[2])
        except OSError:
            out_dir[2] = path.dirname(out_dir[2])

    font_file_paths = sorted({f[0] for f in new_font_name.values()})
    target = path.join(out_dir[2], path.splitext(path.basename(vpath))[0] + ".mkv")
    job = MuxJob(file=vpath, out_file=target, ass_langs=ass_langs, ass_paths=new_ass_paths,
                 font_paths=font_file_paths, force_sub_track=force_sub_track, make_mks=make_mks)
    if ff_muxer == 1:
        mux_rc = mux_with_ffmpeg(job, rm_ass_in=config.rm_ass_in, rm_attach=config.rm_attach,
                                 notfont=config.notfont).return_code
    elif ff_muxer == 0:
        mux_rc = mux_with_mkvmerge(job, rm_ass_in=config.rm_ass_in, rm_attach=config.rm_attach,
                                   notfont=config.notfont).return_code
    else:
        mux_rc = 0

    if not config.notfont:
        for ap in new_ass_paths:
            if path.exists(path.dirname(ap)) and path.splitext(ap)[1][1:].lower() not in ("ass", "ssa"):
                try:
                    os.rmdir(path.dirname(ap))
                except OSError:
                    break
        for fp in new_font_name:
            if path.exists(path.dirname(new_font_name[fp][0])):
                try:
                    os.rmdir(path.dirname(new_font_name[fp][0]))
                except OSError:
                    continue
        if path.isdir(font_sub_dir):
            try:
                os.rmdir(font_sub_dir)
            except OSError:
                pass
    return new_ass_paths, new_font_name, mux_rc


# 兼容旧名称
main = run_pipeline
