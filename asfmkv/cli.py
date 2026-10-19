"""命令行入口：交互主菜单与子命令。"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
import traceback
from os import path
from typing import Optional, Sequence

from . import APP_TITLE, APP_VERSION
from .config import load_config
from .match.subtitles import get_subtitles
from .services.list_fonts import list_ass_font_scan
from .services.load_fonts import load_fonts, make_font_loader, temple_font_load
from .services.subset_mux import run_pipeline
from .services.transcode import detect_transcode, transcode_batch
from .mux import MuxJob, mux_with_mkvmerge
from .platform.shell import pause
from .utils.fs import get_file_list


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ASFMKV", description="AddSubFontMKV Python Remake")
    parser.add_argument("-v", "--version", action="version", version=f"{APP_TITLE} {APP_VERSION}")
    parser.add_argument("--ini", help="指定旧 ASFMKVpy.ini 路径")
    parser.add_argument("--extlist", help="覆盖媒体扩展名列表（分号分隔）")
    sub = parser.add_subparsers(dest="command")

    p_list = sub.add_parser("list-fonts", help="检查并列出字幕所需字体")
    p_list.add_argument("path", help="字幕文件或目录的绝对路径")

    p_subset = sub.add_parser("subset", help="子集化字体（可选封装）")
    p_subset.add_argument("path", help="媒体文件或目录的绝对路径")
    p_subset.add_argument("--subtitle", action="append", default=[], help="指定字幕文件（可重复）")
    p_subset.add_argument("--out-ass", default=None, help="字幕输出文件夹")
    p_subset.add_argument("--out-font", default=None, help="字体输出文件夹")
    p_subset.add_argument("--out-media", default=None, help="媒体 / MKS 输出文件夹")
    subset_mode = p_subset.add_mutually_exclusive_group()
    subset_mode.add_argument("--mux", action="store_true", help="子集化后封装为 MKV")
    subset_mode.add_argument("--mks", action="store_true", help="子集化后封装为外置 MKS（可批量）")
    subset_mode.add_argument("--embed", action="store_true", help="ASS/SSA 内嵌字体")
    p_subset.add_argument("--pattern", default="",
                          help="文件名规则（* 通配），把同一剧集的字幕归为一组（用于 --mks / --embed）")
    p_subset.add_argument("--ffmpeg", action="store_true", help="使用 FFmpeg 封装（配合 --mux）")

    p_mux = sub.add_parser("mux", help="直接封装媒体、字幕与字体")
    p_mux.add_argument("media", help="媒体文件绝对路径")
    p_mux.add_argument("--subtitle", action="append", default=[], help="字幕文件（可重复）")
    p_mux.add_argument("--font", action="append", default=[], help="字体文件（可重复）")
    p_mux.add_argument("-o", "--output", default="", help="输出文件路径")
    p_mux.add_argument("--mks", action="store_true", help="输出为外置 MKS")

    p_trans = sub.add_parser("transcode", help="字幕批量转换为 UTF-8-BOM")
    p_trans.add_argument("path", help="字幕文件或目录的绝对路径")

    p_match = sub.add_parser("match", help="媒体与字幕名称匹配（预览）")
    p_match.add_argument("subtitles", help="字幕目录")
    p_match.add_argument("videos", help="视频目录")

    return parser


def _apply_overrides(config, args):
    overrides = {}
    if getattr(args, "extlist", None):
        overrides["extlist"] = args.extlist
    return config.with_overrides(**overrides) if overrides else config


def cmd_list_fonts(config, args) -> int:
    font_info = load_fonts(config)
    list_ass_font_scan(font_info, config, path.abspath(args.path))
    return 0


def _group_subtitles(config, target: str, ass_paths: list, vpath: str,
                     media_ass: dict, pattern: str = "") -> list:
    """把字幕按“同一剧集/媒体”分组，返回 [(媒体名, [字幕路径, ...]), ...]。

    - 输入是媒体文件：只用该媒体匹配到的字幕；
    - 给了 --pattern：按通配规则（同交互菜单的“视频文件名规则”）把字幕归组；
    - 目录里有视频：按视频合并同集的字幕；
    - 都没有：每条字幕单独一组。
    """
    if vpath:
        return [(vpath, media_ass.get(vpath) or ass_paths)]

    groups: dict = {}
    order: list = []
    if pattern:
        regex = re.compile(re.escape(pattern).replace(r"\*", ".*?"))
        for ass_path in ass_paths:
            found = regex.search(path.basename(ass_path))
            if not found:
                continue
            key = found.group()
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(ass_path)
        grouped = [(key, groups[key]) for key in order]
    else:
        grouped = []
        if path.isdir(target):
            media_files = get_file_list(target, config.extlist, config.v_subdir)
            if media_files:
                matched = get_subtitles(target, media_files, subext=config.subext,
                                        match_strict=config.match_strict,
                                        s_subdir=config.s_subdir)
                grouped = [(media, subs) for media, subs in matched.items() if subs]

    used = set()
    for _key, subs in grouped:
        used.update(subs)
    return grouped + [(ass_path, [ass_path]) for ass_path in ass_paths if ass_path not in used]


def _subset_mks(config, font_info, loader, groups: list, out_dir: list) -> int:
    """逐组生成外置 MKS：子集化字幕 + 子集字体附件，不含视频。"""
    mks_dir = out_dir[2]
    if mks_dir:
        try:
            os.makedirs(mks_dir, exist_ok=True)
        except OSError:
            print(f"[ERROR] 创建 MKS 输出文件夹失败：{mks_dir}")
            return 2

    # 中间子集字幕不要写回源目录（源目录可能只读），没指定 --out-ass 时放到 MKS 目录/临时目录，
    # 封装成功后会被自动清理。
    work_dir = list(out_dir)
    if not work_dir[0]:
        work_dir[0] = mks_dir or tempfile.mkdtemp(prefix="asfmkv-mks-")

    rc = 0
    for media, subs in groups:
        new_ass_paths, new_font_name, prc = run_pipeline(
            font_info, subs, config, mux=False, vpath="", out_dir=work_dir,
            font_loader=loader)
        if prc == -2:
            return 1
        if not new_ass_paths:
            continue
        font_paths = sorted({f[0] for f in new_font_name.values()})
        base = path.splitext(path.basename(media))[0]
        out_file = path.join(mks_dir or path.dirname(media), base + ".mks")
        # MKS 不打包视频，但 mkvmerge 需要媒体路径来推导标题，并在它旁边写临时参数 JSON；
        # 源字幕目录可能是只读的，所以统一用工作目录里的占位路径（mks 模式不检查是否存在）。
        job_file = path.join(work_dir[0], base + ".mkv")
        job = MuxJob(file=job_file, out_file=out_file, ass_paths=new_ass_paths,
                     font_paths=font_paths, make_mks=True)
        result = mux_with_mkvmerge(job, honor_outfile=True)
        if result.return_code > 1:
            rc = 1
        else:
            print(f'[OUT] "{result.out_file}"')
        # 清理子集化产生的临时字体目录（字幕与字体文件已由封装清理）
        for font_path in font_paths:
            try:
                os.rmdir(path.dirname(font_path))
            except OSError:
                pass
    return rc


def _embed_groups(config, font_info, loader, groups: list, out_dir: list) -> int:
    """逐组把子集字体内嵌进 ASS/SSA。

    必须逐组而非整批处理：整批会把所有剧集用到的字符合成一份子集字体，
    再原样嵌进每一份字幕，导致每份字幕都变成“全剧集字体”的超大文件。
    """
    rc = 0
    for _media, subs in groups:
        new_ass_paths, _new_font_name, prc = run_pipeline(
            font_info, subs, config, mux=False, vpath="", out_dir=out_dir,
            ff_muxer=2, font_loader=loader)
        if prc == -2:
            rc = 1
            continue
        for ass_path in new_ass_paths:
            print(f'[OUT] "{ass_path}"')
    return rc


def cmd_subset(config, args) -> int:
    target = path.abspath(args.path)
    font_info = load_fonts(config)
    loader = make_font_loader(config)

    media_ass: dict = {}
    if args.subtitle:
        ass_paths = [path.abspath(s) for s in args.subtitle]
        vpath = target if path.splitext(target)[1][1:].lower() in config.extlist else ""
    elif path.isfile(target):
        if path.splitext(target)[1][1:].lower() in ("ass", "ssa"):
            ass_paths = [target]
            vpath = ""
        else:
            # 传入媒体文件：在同目录按文件名前缀匹配字幕
            vpath = target
            media_ass = get_subtitles(path.dirname(vpath),
                                      [[path.splitext(path.basename(vpath))[0], vpath]],
                                      subext=config.subext, match_strict=config.match_strict,
                                      s_subdir=config.s_subdir)
            ass_paths = [s for subs in media_ass.values() for s in subs]
    else:
        media_ass = get_subtitles(target, subext=config.subext, match_strict=config.match_strict,
                                  s_subdir=config.s_subdir)
        ass_paths = []
        for subs in media_ass.values():
            ass_paths.extend(subs)
        vpath = ""

    if not ass_paths:
        print("[ERROR] 未找到可处理的字幕")
        return 3

    # 与 list-fonts / 交互菜单保持一致：fontload 开启时先补载字幕所在目录的字体，
    # 否则放在字幕同级 Fonts 目录里的字体会被误判为缺失。
    if config.fontload and not config.notfont:
        roots = [target] if path.isdir(target) else sorted({path.dirname(p) for p in ass_paths})
        for root in roots:
            font_info = temple_font_load(root, font_info, s_fontload=config.s_fontload)

    out_dir = [args.out_ass or "", args.out_font or "", args.out_media or ""]

    if args.mks or args.embed:
        groups = _group_subtitles(config, target, ass_paths, vpath, media_ass,
                                  getattr(args, "pattern", "") or "")
        # 批量时中间子集字体不要写进源目录（默认目录是字幕旁的 Fonts），
        # 未指定 --out-font 就放临时目录，处理完整体删除。
        work_dir = list(out_dir)
        temp_font_dir = ""
        if not work_dir[1]:
            temp_font_dir = tempfile.mkdtemp(prefix="asfmkv-fonts-")
            work_dir[1] = temp_font_dir
        try:
            if args.mks:
                return _subset_mks(config, font_info, loader, groups, work_dir)
            return _embed_groups(config, font_info, loader, groups, work_dir)
        finally:
            if temp_font_dir:
                shutil.rmtree(temp_font_dir, ignore_errors=True)

    mux = args.mux and bool(vpath)
    ff_muxer = 1 if args.ffmpeg else 0
    new_ass_paths, new_font_name, rc = run_pipeline(
        font_info, ass_paths, config, mux=mux, vpath=vpath, out_dir=out_dir,
        ff_muxer=ff_muxer, font_loader=loader)
    if rc == -2:
        return 1
    for ap in new_ass_paths:
        print(f'[OUT] "{ap}"')
    return 0


def cmd_mux(config, args) -> int:
    job = MuxJob(file=path.abspath(args.media), out_file=args.output or "",
                 ass_paths=[path.abspath(s) for s in args.subtitle],
                 font_paths=[path.abspath(f) for f in args.font], make_mks=args.mks)
    # 直接封装：不删除用户提供的源字幕与字体
    result = mux_with_mkvmerge(job, rm_ass_in=config.rm_ass_in, rm_attach=config.rm_attach,
                               notfont=config.notfont, cleanup=False, honor_outfile=True)
    return result.return_code


def cmd_transcode(config, args) -> int:
    target = path.abspath(args.path)
    if path.isdir(target):
        return 0 if transcode_batch(target, s_subdir=config.s_subdir) else 1
    out = path.join(path.dirname(target), ".utf8".join(path.splitext(path.basename(target))))
    detect_transcode(target, out)
    return 0


def cmd_match(config, args) -> int:
    from .ui.menus import App, name_matching
    s_path = path.abspath(args.subtitles)
    v_path = path.abspath(args.videos)
    if not (path.isdir(s_path) and path.isdir(v_path)):
        print("[ERROR] 需要字幕与视频目录")
        return 2
    from .utils.fs import get_file_list
    app = App(config, version=APP_VERSION)
    app.extlist = list(config.extlist)
    name_matching(app, s_path, get_file_list(v_path, app.extlist, config.v_subdir))
    return 0


def run_console(argv: Optional[Sequence[str]] = None) -> int:
    """无子命令时进入交互主菜单。"""
    from .ui.menus import App, main_menu
    config = load_config()
    app = App(config, version=APP_VERSION)
    try:
        main_menu(app)
        while True:
            main_menu(app, reload=True)
    except SystemExit:
        return 0
    except Exception:
        print("\n\033[31;1m")
        traceback.print_exc()
        print("\033[0m\n")
        pause()
        return 1
    return 0


def _harden_console_streams() -> None:
    """避免重定向输出时因 GBK 编码不了的字符（日文、半角假名等）导致整个流程崩溃。

    交互控制台（PEP 528）本来就是 UTF-8；重定向到管道/文件时 Windows 会用系统
    代码页（简中即 GBK），遇到编码范围外的字符会抛 UnicodeEncodeError。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv: Optional[Sequence[str]] = None) -> int:
    _harden_console_streams()
    try:
        import colorama
        colorama.init()
    except ImportError:
        pass
    args = build_parser().parse_args(argv)
    config = load_config(args.ini)
    config = _apply_overrides(config, args)

    handlers = {
        "list-fonts": cmd_list_fonts,
        "subset": cmd_subset,
        "mux": cmd_mux,
        "transcode": cmd_transcode,
        "match": cmd_match,
    }
    if args.command in handlers:
        return handlers[args.command](config, args)
    return run_console(argv)
