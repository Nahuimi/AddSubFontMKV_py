"""基于 mkvmerge 的封装实现（参数一律以 argv 列表传入）。"""

from __future__ import annotations

import json
import os
from datetime import datetime
from os import path

from ..core.console import Ansi, colorize
from ..utils.proc import run
from .base import cleanup_after_mux, resolve_mux_outfile, subtitle_note
from .models import MuxJob, MuxResult


def build_mkvmerge_args(job: MuxJob, rm_ass_in: bool, rm_attach: bool) -> list:
    """构造 mkvmerge 的参数列表（不含可执行文件与输出参数）。"""
    mkv_args: list = []
    if not job.make_mks:
        if rm_ass_in:
            mkv_args.append("-S")
        if rm_attach:
            mkv_args.append("-M")
        mkv_args.extend(["(", job.file, ")"])

    media_name = path.splitext(path.basename(job.file))[0]
    if job.ass_paths:
        default_set = False
        for sub in job.ass_paths:
            note = subtitle_note(sub, media_name)
            if len(note) > 1:
                mkv_args.extend(["--track-name", f'0:{note.lstrip(".")}'])
            if job.ass_langs and path.splitext(sub)[1][1:].lower() not in ("idx",):
                mkv_args.append("--language")
                mkv_args.append(f'0:{job.ass_langs[note.lower()]}' if note.lower() in job.ass_langs else "0:und")
                if not default_set and (note.lower() == job.force_sub_track.lower() or job.force_sub_track == "?"):
                    mkv_args.extend(["--default-track-flag", "0:1"])
                    default_set = True
                else:
                    mkv_args.extend(["--default-track-flag", "0:0"])
            mkv_args.extend(["(", sub, ")"])
    if job.font_paths:
        for font in job.font_paths:
            mkv_args.extend(["--attachment-name", path.basename(font)])
            mkv_args.extend(["--attach-file", font])
    mkv_args.extend(["--title", media_name])
    return mkv_args


def mux_with_mkvmerge(job: MuxJob, *, rm_ass_in: bool = True, rm_attach: bool = True,
                      notfont: bool = False, cleanup: bool = True,
                      honor_outfile: bool = False) -> MuxResult:
    """使用 mkvmerge 将媒体、字幕与字体封装进一个 MKV 文件。"""
    if not job.file:
        return MuxResult(4)
    if (not path.exists(job.file) or not path.isfile(job.file)) and not job.make_mks:
        return MuxResult(4)
    if honor_outfile and job.out_file:
        # CLI 显式指定输出路径时严格遵守，不做 .muxed 改名
        out_file = job.out_file
    else:
        out_file = resolve_mux_outfile(job.file, job.out_file or "", job.make_mks)

    mkv_args = build_mkvmerge_args(job, rm_ass_in, rm_attach)
    mkv_json_path = path.splitext(job.file)[0] + ".mkvmerge.json"
    with open(mkv_json_path, mode="w", encoding="utf-8") as fh:
        json.dump(mkv_args, fp=fh, sort_keys=True, indent=2, separators=(",", ": "))

    proc = run(["mkvmerge", f"@{mkv_json_path}", "-o", out_file])
    mkv_mr = proc.returncode

    if mkv_mr > 1:
        print(colorize("\n[ERROR] 检测到不正常的 mkvmerge 返回值，重定向输出...", Ansi.RED))
        log_name = f'{path.splitext(job.file)[0]}.{datetime.now().strftime("%Y-%m%d-%H%M-%S_%f")}.log'
        run(["mkvmerge", "-r", log_name, f"@{mkv_json_path}", "-o", "NUL"])
    else:
        # cleanup=False 时保留输入（直接封装用户文件时不应删除源字幕/字体）
        if not notfont and cleanup:
            cleanup_after_mux(job.ass_paths, job.font_paths)
        # 成功时统一清理临时 JSON 参数文件（旧实现仅在 notfont=False 时删除，会残留垃圾文件）
        try:
            os.remove(mkv_json_path)
        except OSError:
            print(colorize(f'[ERROR] 文件"{mkv_json_path}"删除失败', Ansi.YELLOW))
        print(colorize("输出成功:", Ansi.GREEN) + " " + colorize(f'"{out_file}"', Ansi.WHITE))
    return MuxResult(mkv_mr, out_file)


# 兼容旧名称
asfmkv = mux_with_mkvmerge
ASFMKV = mux_with_mkvmerge
