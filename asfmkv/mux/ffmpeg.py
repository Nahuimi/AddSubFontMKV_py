"""基于 FFmpeg 的封装实现（参数一律以 argv 列表传入）。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime
from os import path

from ..core.console import Ansi, colorize
from ..utils.proc import run
from .base import cleanup_after_mux, resolve_mux_outfile, subtitle_note
from .models import MuxJob, MuxResult


def probe_streams(file: str) -> list:
    """调用 ffprobe 获取媒体流信息。"""
    proc = run(["ffprobe", "-print_format", "json", "-show_streams", "-hide_banner", "-v", "0", "-i", file])
    try:
        return json.loads(proc.stdout or "{}").get("streams", [])
    except json.JSONDecodeError:
        print(colorize("[WARNING] ffprobe 输出无法解析，将按无内挂轨道处理", Ansi.YELLOW))
        return []


def build_ffmpeg_args(job: MuxJob, *, rm_ass_in: bool = True, rm_attach: bool = True) -> list:
    """构造 ffmpeg 的参数列表（不含可执行文件）。"""
    ff_args: list = []
    map_list: list = []
    copy_list: list = []
    meta_list: list = []
    first_idx = 0

    if not job.make_mks:
        streams = probe_streams(job.file)
        first_idx = len(streams)
        for stream in streams:
            kind = stream["codec_type"]
            if kind == "video":
                if "0:v" not in map_list:
                    map_list.append("0:v")
                    copy_list.extend(["-c:v", "copy"])
            elif kind == "audio":
                if "0:a" not in map_list:
                    map_list.append("0:a")
                    copy_list.extend(["-c:a", "copy"])
            elif kind == "attachment":
                if not rm_attach:
                    if "0:t" not in map_list:
                        map_list.append("0:t")
                        copy_list.extend(["-c:t", "copy"])
                else:
                    first_idx -= 1
            elif kind == "subtitle":
                if rm_ass_in:
                    first_idx -= 1
                elif "0:s" not in map_list:
                    map_list.append("0:s")
                if not rm_ass_in and stream["disposition"]["default"] == 1:
                    copy_list.extend([f'-disposition:{stream["index"]}', "0"])
        ff_args.extend(["-i", job.file])

    media_name = path.splitext(path.basename(job.file))[0]
    meta_list.extend(["-metadata:g", f'title={media_name}'])
    if job.ass_paths:
        default_set = False
        for i, sub in enumerate(job.ass_paths):
            note = subtitle_note(sub, media_name)
            metadata = []
            if len(note) > 1:
                metadata.append(f'title={note.lstrip(".")}')
            if job.ass_langs and path.splitext(sub)[1][1:].lower() not in ("idx",):
                if note.lower() in job.ass_langs:
                    metadata.append(f'language={job.ass_langs[note.lower()]}')
            for m in metadata:
                meta_list.extend([f"-metadata:s:{first_idx}", m])
            ff_args.extend(["-i", sub])
            map_list.append(str(i + 1 if not job.make_mks else i))
            if not default_set and (note.lower() == job.force_sub_track.lower() or job.force_sub_track == "?"):
                copy_list.extend([f"-disposition:{first_idx}", "default"])
                default_set = True
            else:
                copy_list.extend([f"-disposition:{first_idx}", "0"])
            first_idx += 1

    if job.font_paths:
        ext_mime = {"ttf": "font/ttf", "otf": "font/otf",
                    "ttc": "font/collection", "otc": "font/collection"}
        for font in job.font_paths:
            mime = ext_mime.get(path.splitext(font)[1][1:].lower())
            meta_list.extend([f"-metadata:s:{first_idx}",
                              f'title={path.splitext(path.basename(font))[0].split(".")[-1]}'])
            if mime is not None:
                meta_list.extend([f"-metadata:s:{first_idx}", f'mimetype={mime}'])
            # 附件名使用文件名本身，避免写入完整路径
            ff_args.extend(["-attach", font])
            first_idx += 1

    if job.make_mks:
        meta_list.extend(["-f", "matroska"])

    map_args: list = []
    for spec in map_list:
        map_args.extend(["-map", spec])
    return ff_args + map_args + copy_list + ["-c:s", "copy"] + meta_list


def build_ffmpeg_argv(job: MuxJob, out_target: str) -> list:
    """构造完整的 ffmpeg 命令行（含输出目标）。"""
    return ["ffmpeg"] + build_ffmpeg_args(job) + [out_target]


def mux_with_ffmpeg(job: MuxJob, *, rm_ass_in: bool = True, rm_attach: bool = True,
                    notfont: bool = False, cleanup: bool = True, pause=None) -> MuxResult:
    """使用 FFmpeg 将媒体、字幕与字体封装进一个 MKV 文件。"""
    if not job.file:
        return MuxResult(4)
    if (not path.exists(job.file) or not path.isfile(job.file)) and not job.make_mks:
        return MuxResult(4)
    out_file = resolve_mux_outfile(job.file, job.out_file or "", job.make_mks)

    argv = build_ffmpeg_argv(job, out_file)
    ff_mr = run(argv).returncode

    if ff_mr >= 1:
        print(colorize("\n[ERROR] 检测到不正常的 FFmpeg 返回值，重定向输出...", Ansi.RED))
        env = dict(os.environ)
        # FFREPORT 的取值用冒号分隔选项，Windows 绝对路径里的盘符冒号会被误解析，
        # 因此只能写相对文件名；用进程号命名避免并发运行时互相覆盖。
        report_name = f"ffreport_cache_{os.getpid()}.log"
        env["FFREPORT"] = f"file={report_name}:level=32"
        subprocess.run(build_ffmpeg_argv(job, "NUL"), check=False, env=env)
        try:
            shutil.move(report_name,
                        f'{path.splitext(job.file)[0]}.{datetime.now().strftime("%Y-%m%d-%H%M-%S_%f")}.log')
        except OSError:
            print(colorize(f'[WARNING] "{report_name}"移动失败', Ansi.YELLOW))
            try:
                os.remove(report_name)
            except OSError:
                pass
    elif not notfont:
        # cleanup=False 时保留输入（直接封装用户文件时不应删除源字幕/字体）
        if cleanup:
            cleanup_after_mux(job.ass_paths, job.font_paths)
        print(colorize("输出成功:", Ansi.GREEN) + " " + colorize(f'"{out_file}"', Ansi.WHITE))
    else:
        print(colorize("输出成功:", Ansi.GREEN) + " " + colorize(f'"{out_file}"', Ansi.WHITE))
    if pause is not None:
        pause()
    return MuxResult(ff_mr, out_file)


# 兼容旧名称
ff_asfmkv = mux_with_ffmpeg
ffASFMKV = mux_with_ffmpeg
