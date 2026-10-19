"""交互菜单层：主菜单与各功能子菜单。

本层允许直接使用 ``print``，因为菜单排版依赖精确的 ANSI 序列。
可变状态集中存放在 :class:`App` 中，取代原脚本的模块级全局变量。
"""

from __future__ import annotations

import copy
import os
import re
import sys
from datetime import datetime
from os import path

from ..core.console import Ansi, colorize
from ..fonts.models import FontIndex
from ..fonts.cache import FontCache
from ..fonts.parser import progress_fonts
from ..fonts.scanner import get_font_file_list
from ..match.rename import apply_rename, rename_preview
from ..match.subtitles import get_subtitles, name_matching_progress, name_position
from ..platform.paths import cache_dir_or_none
from ..platform.shell import clear_screen, confirm, pause, prompt_choice, set_title, wait_enter
from ..services.list_fonts import list_ass_font_scan
from ..services.load_fonts import load_fonts, make_font_loader, temple_font_load
from ..services.subset_mux import run_pipeline
from ..services.transcode import transcode_batch
from ..utils.fs import basename_no_ext, get_file_list, sanitize_filename
from ..utils.proc import run
from . import lang as langmod
from .prompts import check_out_path, prompt_input_path, show_license, show_message_subset

TITLE = "ASFMKV Python Remake"


class App:
    """一次运行期间的可变状态与配置容器。"""

    def __init__(self, config, version: str = "", title: str = TITLE, shell=None):
        self.config = config
        self.version = version
        self.title = title
        self.font_info = FontIndex()
        self.extlist = list(config.extlist)
        self.duplicate_fonts: dict = {}
        self.extsupp: list = []
        self.iso639_all: dict = {}
        self.translation_lang: dict = {}
        self.langlist: dict = {}
        self.no_mkvmerge = False
        self.no_cmd_choice = False
        self.mkv_ver = ""
        self.ff_ver = ""
        self.instead_ff = False
        self.subname_lang = langmod.split_subname_lang(config.sub_name2_lang)

    # -- 配置读写 -------------------------------------------------------
    def set_config(self, **kwargs):
        self.config = self.config.with_overrides(**kwargs)

    @property
    def prefer_lang(self) -> str:
        return self.config.subl_local

    # -- 字体载入 -------------------------------------------------------
    def font_loader(self):
        return make_font_loader(self.config, self.duplicate_fonts)

    def load_fonts(self, using_cache: bool = True, extra_dirs=None) -> FontIndex:
        return load_fonts(self.config, using_cache=using_cache, extra_dirs=extra_dirs,
                          duplicate_fonts=self.duplicate_fonts)

    def temple_font_load(self, directory: str, font_info: FontIndex) -> FontIndex:
        return temple_font_load(directory, font_info, s_fontload=self.config.s_fontload)


# ---------------------------------------------------------------------------
# 依赖检测
# ---------------------------------------------------------------------------

def check_ff(app: App) -> None:
    """检查 ffmpeg 与 ffprobe 是否可用。"""
    ok_ffmpeg = run(["ffmpeg", "-version"]).returncode == 0
    ok_ffprobe = run(["ffprobe", "-version"]).returncode == 0
    if ok_ffmpeg and ok_ffprobe:
        proc = run(["ffmpeg", "-version"])
        first = (proc.stdout or "").splitlines()
        if first:
            app.ff_ver = "\n" + " ".join(first[0].rstrip("\n").split(" ")[:3])
        app.instead_ff = True


def detect_dependencies(app: App) -> None:
    """检测 mkvmerge / choice / ffmpeg 的可用性并填充 App 状态。"""
    set_title(f"{app.title} | (c) 2022-2024 yyfll | Apache-2.0")
    app.mkv_ver = "\n" + colorize("没有检测到 mkvmerge", Ansi.YELLOW)
    if run(["mkvmerge", "-V"]).returncode > 0:
        app.no_mkvmerge = True
        check_ff(app)
    else:
        print(colorize("\n\n正在获取 mkvmerge 支持格式列表，请稍等...", Ansi.YELLOW))
        app.mkv_ver = "\n" + (run(["mkvmerge", "-V", "--ui-language", "en"]).stdout or "").replace("\n", "")
        if not app.config.no_extcheck:
            listing = run(["mkvmerge", "-l", "--ui-language", "en"]).stdout or ""
            for line in listing.splitlines()[1:]:
                found = re.search(r"\[.*\]", line)
                if found:
                    app.extsupp.extend(found.group().lstrip("[").rstrip("]").split(" "))
            original = app.extlist[:]
            app.extlist.clear()
            print("")
            for s in original:
                if s in app.extsupp:
                    app.extlist.append(s)
                else:
                    print(colorize(f"[WARNING] 您设定的媒体扩展名 {s} 无效，已从列表移除", Ansi.RED))
            if len(app.extlist) != len(original):
                print(colorize(f'\n当前的媒体扩展名列表: "{";".join(app.extlist)}"', Ansi.YELLOW))
                pause()
        if app.config.using_ff:
            check_ff(app)
    if run(["choice", "/?"]).returncode > 0:
        app.no_cmd_choice = True


# ---------------------------------------------------------------------------
# [S] 搜索字体
# ---------------------------------------------------------------------------

def font_search_menu(app: App) -> None:
    """[S] 搜索字体。"""
    leave = True
    while leave:
        clear_screen()
        print("""ASFMKV FontSearch
请选择功能:
[1] 完全匹配（不区分大小写）
[2] 部分匹配（不区分大小写）
[0] 回到主菜单
""")
        work = prompt_choice("请选择: ", "012")
        if work == 1:
            leave = False
        elif work in (2, 3):
            clear_screen()
            if work == 3:
                print('AND = " "（半角空格）\n仅支持AND')
            query = input("请输入字体名称:\n").strip(" \"").lower()
            print("")
            if not query:
                continue
            found = False
            if work == 2:
                target = app.font_info.get_by_index(1).get(query)
                if target is not None:
                    entry = app.font_info.get_by_index(0).get(target)
                    if entry is not None:
                        print(f'\033[1;31m[{target}]\033[0m {entry[2].get("utf-8", "")}\033[1m\n"{entry[0]}"\033[0m\n')
                        found = True
            else:
                for key, entry in app.font_info.get_by_index(0).items():
                    if all(part in key.lower() for part in query.split(" ")):
                        print(f'\033[1;31m[{key}]\033[0m {entry[2].get("utf-8", "")}\033[1m\n"{entry[0]}"\033[0m\n')
                        found = True
            if not found:
                print(colorize("没有找到所搜索的字体", Ansi.RED))
            pause()


# ---------------------------------------------------------------------------
# [C] 重复字体 / [W] 旧格式字体
# ---------------------------------------------------------------------------

def show_duplicate_fonts(app: App) -> None:
    clear_screen()
    if app.duplicate_fonts:
        for key, names in app.duplicate_fonts.items():
            for path_item in key:
                print(colorize(f"[{path_item}]", Ansi.RED))
            print(colorize("\n".join(names), Ansi.WHITE))
            print("")
    else:
        print("没有名称重复的字体")
    pause()


def show_legacy_fonts(app: App) -> None:
    clear_screen()
    warning_font = app.font_info.get_by_index(3)
    if warning_font:
        old_list: dict = {}
        for s in warning_font:
            old_name = app.font_info.get_by_index(1).get(s)
            entry = app.font_info.get_by_index(0).get(old_name)
            if entry is None:
                continue
            old_list.setdefault(entry[0], []).append(old_name)
        for fp, names in old_list.items():
            for name in names:
                print(colorize(f"[{name}]", Ansi.RED))
            print(colorize(fp, Ansi.WHITE) + "\n")
    else:
        print("没有使用旧格式的字体")
    pause()


# ---------------------------------------------------------------------------
# [A] 列出字幕所用字体
# ---------------------------------------------------------------------------

def list_ass_fonts(app: App) -> None:
    """[A] 列出字幕所用字体。"""
    leave = True
    while leave:
        clear_screen()
        print(f"""ASFMKV-ListAssFontPy
注意: 本程序由于设计原因，列出的是字体文件与其内部字体名的对照表
选择功能:
[L] 回到上级菜单
[A] 列出全部字体
[B] 检查并列出字幕所需字体
切换开关:
[1] 将结果写入文件: \033[1;33m{app.config.resultw}\033[0m
[2] 拷贝所需字体: \033[1;33m{app.config.copyfont}\033[0m
[3] 搜索子目录(字幕): \033[1;33m{app.config.s_subdir}\033[0m
[4] 使用工作目录字体：\033[1;33m{app.config.fontload}\033[0m
[5] 显示缺少字体的字幕: \033[1;33m{app.config.exact_lost}\033[0m
[6] 显示字体缺字数(慢): \033[1;33m{app.config.char_lost}\033[0m
[7] 抽出内嵌字体(如果有): \033[1;33m{app.config.embedded_font_extract}\033[0m
""")
        work = prompt_choice("请输入", "AB1234567L")
        if work == 1:
            clear_screen()
            wfile_path = path.join(os.getcwd(), datetime.now().strftime("ASFMKV_FullFont_%Y-%m%d-%H%M-%S_%f.log"))
            wfile = open(wfile_path, mode="w", encoding="utf-8-sig") if app.config.resultw else None
            font_name = app.font_info.font_name
            last = ""
            print("FontList", file=wfile)
            for s in font_name:
                nfn = path.basename(font_name[s][0])
                if nfn != last:
                    if wfile is not None:
                        print(f">\n{nfn} <{s}", end="", file=wfile)
                    else:
                        print(f'>\033[0m\n\033[1;36m{nfn}\033[0m \033[1m<{s}', end="")
                else:
                    print(f", {s}", end="", file=wfile)
                last = nfn
            if wfile is not None:
                print(wfile_path)
                print(">", file=wfile)
                wfile.close()
            else:
                print(">\033[0m")
        elif work == 2:
            _list_ass_font_scan_menu(app)
        elif work == 3:
            app.set_config(resultw=not app.config.resultw)
        elif work == 4:
            app.set_config(copyfont=not app.config.copyfont)
        elif work == 5:
            app.set_config(s_subdir=not app.config.s_subdir)
        elif work == 6:
            if not app.config.o_fontload:
                app.set_config(fontload=not app.config.fontload)
            else:
                clear_screen()
                print("在禁用系统字体源的情况下，fontload必须为True")
                pause()
        elif work == 7:
            app.set_config(exact_lost=not app.config.exact_lost)
        elif work == 8:
            app.set_config(char_lost=not app.config.char_lost)
        elif work == 9:
            app.set_config(embedded_font_extract=not app.config.embedded_font_extract)
        else:
            leave = False
        if work < 3:
            # 字体列表可能很长，按回车后回菜单，避免日志被清屏
            wait_enter()


def _list_ass_font_scan_menu(app: App) -> None:
    """[B] 检查并列出字幕所需字体（交互输入路径）。"""
    clear_screen()
    cpath = ""
    give_up = False
    while not path.exists(cpath) and not give_up:
        give_up = True
        cpath = input("请输入目录路径或字幕文件路径: ").strip('" ')
        if cpath == "":
            print("没有输入，回到上级菜单")
        elif not path.exists(cpath):
            print(colorize(f'[ERROR] 找不到路径: "{cpath}"', Ansi.RED))
        elif not path.isfile(cpath) and not path.isdir(cpath):
            print(colorize(f'[ERROR] 输入的必须是文件或目录！: "{cpath}"', Ansi.RED))
        elif not path.isabs(cpath):
            print(colorize(f'[ERROR] 路径必须为绝对路径！: "{cpath}"', Ansi.RED))
        elif path.isdir(cpath):
            give_up = False
        elif path.splitext(cpath)[1][1:].lower() not in ("ass", "ssa"):
            print(colorize(f'[ERROR] 输入的必须是ASS/SSA字幕文件！: "{cpath}"', Ansi.RED))
        else:
            give_up = False
    if give_up:
        return
    list_ass_font_scan(app.font_info, app.config, cpath)


# ---------------------------------------------------------------------------
# [M] 字幕-视频名称匹配
# ---------------------------------------------------------------------------

def sv_matching_menu(app: App) -> None:
    """[M] 字幕-视频名称匹配。"""
    clear_screen()
    print("Subtitles-Videos Filename Matching (Experiment)")
    s_path = input("字幕目录:").strip(" \"'")
    attempts = 0
    while not (path.exists(s_path) and path.isdir(s_path)):
        attempts += 1
        if attempts > 2:
            print("回到主界面")
            pause()
            return
        s_path = input("字幕目录:").strip(" \"'")

    log_files = [f for f in os.listdir(s_path) if f[:11].lower() == "subsrename_"]
    if log_files and confirm("检测到重命名记录，您要撤销之前的重命名吗？"):
        _undo_rename(s_path, log_files)
        return

    v_path = input("视频目录:").strip("\"' ")
    attempts = 0
    while not (path.exists(v_path) and path.isdir(v_path)):
        attempts += 1
        if attempts > 2:
            print("回到主界面")
            pause()
            return
        v_path = input("视频目录:").strip("\"' ")
    if v_path:
        name_matching(app, s_path, get_file_list(v_path, app.extlist, app.config.v_subdir))
    else:
        print("回到主界面")
    pause()


def _undo_rename(s_path: str, log_files: list) -> None:
    """按日志撤销之前的批量重命名。"""
    # 日志文件名包含时间戳，排序后即按时间先后；旧实现直接使用 listdir 顺序，
    # 撤销顺序因此可能错乱。
    log_files = sorted(log_files)
    log_count = 0
    if len(log_files) > 1:
        print("请选择您要撤销到的时间点")
        for i, name in enumerate(log_files):
            print(f"[{i}] {name[11:]}")
        print("")
        tries = 0
        while True:
            answer = input("请输入方括号内的数字:").strip()
            if answer.isdigit() and 0 <= int(answer) <= len(log_files) - 1:
                log_count = int(answer)
                break
            # 旧实现把 -1 取相反数变成 1，非法输入反而撤销了日志，这里改为明确放弃撤销
            tries += 1
            if tries > 2:
                print("输入有误，已放弃撤销")
                return
            print(f"输入有误，请重新输入；或者继续有误输入{3 - tries}次退出")
    ren_cache: dict = {}
    for i in range(0, log_count + 1):
        log_path = path.join(s_path, log_files[i])
        try:
            with open(log_path, mode="r", encoding="utf-8") as log_file:
                lines = log_file.readlines()
        except (OSError, UnicodeDecodeError):
            print(colorize(f'[ERROR] 日志文件读取失败 "{log_files[i]}"', Ansi.RED))
            continue
        for line in lines:
            parts = line.strip("\n").split("|")
            if len(parts) < 2:
                continue
            if parts[1] in ren_cache:
                ren_cache[path.basename(parts[0])] = (ren_cache[parts[1]][0], parts[0])
                del ren_cache[parts[1]]
            else:
                ren_cache[path.basename(parts[0])] = (path.join(path.dirname(parts[0]), parts[1]), parts[0])
    clear_screen()
    print("[重命名预览]\n")
    for r in ren_cache:
        print(colorize(f'"{path.basename(ren_cache[r][0])}"', Ansi.WHITE, bold=True))
        print('>>>> ' + colorize(f'"{r}"', Ansi.YELLOW) + "\n")
    print("")
    if confirm("是否要执行？"):
        no_delete = False
        for r in ren_cache.values():
            try:
                os.rename(r[0], r[1])
            except OSError:
                print(colorize("[ERROR]", Ansi.RED) + " 文件" + colorize(r[0], Ansi.WHITE) + "重命名失败")
                no_delete = True
            else:
                print(colorize("[SUCCESS]", Ansi.GREEN) + f' "{path.basename(r[0])}"\n        >>>> '
                      + colorize(f'"{path.basename(r[1])}"', Ansi.YELLOW))
        if not no_delete:
            for name in log_files:
                try:
                    os.remove(path.join(s_path, name))
                except OSError:
                    pass
    pause()


def name_matching(app: App, spath: str, medias: list) -> None:
    """字幕-视频名称匹配的交互流程。"""
    if not medias:
        print("找不到媒体文件")
        return
    m_start, m_end = name_position([s[0] for s in medias])
    subs = get_subtitles(spath, subext=app.config.subext, match_strict=app.config.match_strict,
                         s_subdir=app.config.s_subdir)["none"]
    if not subs:
        print("找不到字幕文件")
        return
    s_start, s_end = name_position([basename_no_ext(s) for s in subs])
    s_start_a, s_end_a = name_position([basename_no_ext(s)[::-1] for s in subs])
    media_ass = name_matching_progress(medias, m_start, m_end, s_start, s_end, subs)
    ren_list, is_skip = rename_preview(media_ass, s_start_a, s_end_a, match_strict=app.config.match_strict)
    ann_list: list = []
    ann = ""

    def ask() -> int:
        if ren_list:
            print("请确认重命名是否正确\n"
                  "如果注释部分不正确您可以选择\033[33;1m[A]\033[0m手动输入字幕注释\n"
                  "如果文件匹配不正确您可以选择\033[33;1m[F]\033[0m手动输入匹配规则")
            return prompt_choice("请选择", "YNAF")
        if not is_skip:
            clear_screen()
            print("视频-字幕匹配失败，请手动输入匹配规则\n")
            return 4
        return 2

    rt = ask()
    while rt in (0, 3, 4):
        if rt == 4:
            if ren_list:
                clear_screen()
            print('请将剧集所在位置用"\033[33;1m:\033[0m"代替\n'
                  '如 "\033[30;1m[VCB-Studio] Accel World [\033[33;1m01\033[30;1m][720p][x265_aac].mp4\033[0m"\n'
                  '替换为 "\033[30;1m[VCB-Studio] Accel World [\033[33;1m:\033[30;1m][720p][x265_aac].mp4\033[0m"\n'
                  "请务必保留剧集位置后的一个字符以便程序正常工作")
            v_search = input("请输入视频匹配规则:").strip(' "\'')
            if not v_search:
                print("输入为空，退出")
                break
            s_search = input("请输入字幕匹配规则:").strip(' "\'')
            if not s_search:
                print("输入为空，退出")
                break
            v_split = v_search.split(":")
            s_split = s_search.split(":")
            if len(v_split) != 2 or len(s_split) != 2:
                print("输入不正确，退出")
                break
            media_ass = name_matching_progress(medias, len(v_split[0]), v_split[1][0], len(s_split[0]), s_split[1][0], subs)
        elif rt == 3:
            ann = input('请输入（可以为空，可以有多个，按预览顺序用"\033[33;1m:\033[0m"分隔）:')
            if ":" in ann:
                ann_list = [sanitize_filename(a) for a in ann.split(":") if a]
                ann = ""
            elif ann:
                if ann[0] != ".":
                    ann = "." + ann
                ann_list = [sanitize_filename(ann)]
        else:
            break
        ren_list, is_skip = rename_preview(media_ass, ann_list=ann_list, match_strict=app.config.match_strict)
        rt = ask()

    if rt == 1:
        apply_rename(ren_list, spath)


# ---------------------------------------------------------------------------
# [B] 字体子集化 & MKV 封装
# ---------------------------------------------------------------------------

def font_subset_menu(app: App) -> None:
    """[B] 字体子集化与封装。"""
    leave = True
    while leave:
        clear_screen()
        if app.instead_ff and not app.no_mkvmerge:
            show_ff = "子集化并封装(mkvmerge)\n[D] 子集化并封装(FFmpeg)"
            show_ff_key = "D"
        elif app.no_mkvmerge and app.instead_ff:
            show_ff = "子集化并封装(FFmpeg)"
            show_ff_key = ""
        else:
            show_ff = "子集化并封装(mkvmerge)"
            show_ff_key = ""
        print(f"""ASFMKV & ASFMKV-FontSubset
选择功能:
[A] 子集化字体
[B] 子集化并封装(ASS/SSA内嵌)
[C] {show_ff}
[L] 回到上级菜单
切换开关:
[1] 检视媒体扩展名列表 及 语言编码列表
[2] 搜索子目录(视频): \033[1;33m{app.config.v_subdir}\033[0m
[3] 搜索子目录(字幕): \033[1;33m{app.config.s_subdir}\033[0m
[4] (封装)移除内挂字幕: \033[1;33m{app.config.rm_ass_in}\033[0m
[5] (封装)移除原有附件: \033[1;33m{app.config.rm_attach}\033[0m
[6] (封装)不封装字体: \033[1;33m{app.config.notfont}\033[0m
[7] 严格字幕匹配: \033[1;33m{app.config.match_strict}\033[0m
[8] 媒体文件输出文件夹: \033[1;33m{app.config.mkvout}\033[0m
[9] 字幕文件输出文件夹: \033[1;33m{app.config.assout}\033[0m
[0] 字体文件输出文件夹: \033[1;33m{app.config.fontout}\033[0m
[U] 广兼容性子集化: \033[1;33m{app.config.char_compatible}\033[0m
[V] 忽略字体所缺字: \033[1;33m{app.config.ignore_lost}\033[0m
[W] 子集化失败中断: \033[1;33m{app.config.error_stop}\033[0m
[X] 忽略字幕缺少字体：\033[1;33m{app.config.no_request_font}\033[0m
[Y] 使用工作目录字体: \033[1;33m{app.config.fontload}\033[0m
[Z] 暴力字幕标题<>语言匹配: \033[1;33m{app.config.rude_sub_n2_l}\033[0m
""")
        work = prompt_choice("请输入", "AC1234567890UVWXYZLB" + show_ff_key)

        if work == 2 and app.no_mkvmerge and not app.instead_ff:
            print("[ERROR] 在您的系统中找不到 mkvmerge 或 ffmpeg, 该功能不可用")
            work = -1
            pause()

        if work == 3:
            clear_screen()
            print("ExtList Viewer 1.00-Final\n")
            for i, s in enumerate(app.extlist):
                print(f"[Ext{i:>3d}] {s}")
            print("\n")
            if not app.no_mkvmerge:
                pause()
                clear_screen()
                run(["mkvmerge", "--list-languages"])
            else:
                print("没有检测到mkvmerge，无法输出语言编码列表")
                pause()
        elif work == 4:
            app.set_config(v_subdir=not app.config.v_subdir)
        elif work == 5:
            app.set_config(s_subdir=not app.config.s_subdir)
        elif work == 6:
            app.set_config(rm_ass_in=not app.config.rm_ass_in)
        elif work == 7:
            app.set_config(rm_attach=not app.config.rm_attach)
        elif work == 8:
            app.set_config(notfont=not app.config.notfont)
        elif work == 9:
            app.set_config(match_strict=not app.config.match_strict)
        elif work in (10, 11, 12):
            clear_screen()
            print('请输入目标目录路径或子目录名称\n(若要输入子目录，请在目录名前加"?")\n'
                  '(不支持多层子目录，会自动将"\\"换成下划线)')
            if work == 10:
                app.set_config(mkvout=check_out_path(input(), app.config.mkvout))
            elif work == 11:
                app.set_config(assout=check_out_path(input(), app.config.assout))
            elif work == 12:
                app.set_config(fontout=check_out_path(input(), app.config.fontout))
        elif work == 13:
            app.set_config(char_compatible=not app.config.char_compatible)
        elif work == 14:
            app.set_config(ignore_lost=not app.config.ignore_lost)
        elif work == 15:
            app.set_config(error_stop=not app.config.error_stop)
        elif work == 16:
            app.set_config(no_request_font=not app.config.no_request_font)
        elif work == 17:
            if not app.config.o_fontload:
                app.set_config(fontload=not app.config.fontload)
            else:
                clear_screen()
                print("在禁用系统字体源的情况下，fontload必须为True")
                pause()
        elif work == 18:
            app.set_config(rude_sub_n2_l=not app.config.rude_sub_n2_l)
        elif work in (1, 2, 20, 21):
            # 子集化/封装会输出大量日志，按回车后再重绘菜单，避免日志被清屏
            if run_subset_workflow(app, work):
                wait_enter()
        else:
            leave = False


def run_subset_workflow(app: App, work: int) -> bool:
    """执行子集化/封装主流程（A/B/C/D 四个入口共用）。

    返回是否实际执行了流程：用户在路径输入阶段取消时为 False，
    调用方可据此决定是否需要暂停以便阅读日志。
    """
    clear_screen()
    if work == 1:
        print(f"""子集化字体
搜索子目录(视频): \033[1;33m{app.config.v_subdir}\033[0m
搜索子目录(字幕): \033[1;33m{app.config.s_subdir}\033[0m
严格字幕匹配: \033[1;33m{app.config.match_strict}\033[0m
字幕文件输出文件夹: \033[1;33m{app.config.assout}\033[0m
字体文件输出文件夹: \033[1;33m{app.config.fontout}\033[0m
广兼容性子集化: \033[1;33m{app.config.char_compatible}\033[0m
忽略字体所缺字: \033[1;33m{app.config.ignore_lost}\033[0m
子集化失败中断: \033[1;33m{app.config.error_stop}\033[0m
使用工作目录字体：\033[1;33m{app.config.fontload}\033[0m
""")
    else:
        print(f"""子集化字体并封装
搜索子目录(视频): \033[1;33m{app.config.v_subdir}\033[0m
搜索子目录(字幕): \033[1;33m{app.config.s_subdir}\033[0m
移除内挂字幕: \033[1;33m{app.config.rm_ass_in}\033[0m
移除原有附件: \033[1;33m{app.config.rm_attach}\033[0m
不封装字体: \033[1;33m{app.config.notfont}\033[0m
严格字幕匹配: \033[1;33m{app.config.match_strict}\033[0m
媒体文件输出文件夹: \033[1;33m{app.config.mkvout}\033[0m
广兼容性子集化: \033[1;33m{app.config.char_compatible}\033[0m
忽略字体所缺字: \033[1;33m{app.config.ignore_lost}\033[0m
子集化失败中断: \033[1;33m{app.config.error_stop}\033[0m
使用工作目录字体：\033[1;33m{app.config.fontload}\033[0m
""")

    cpath, medias, sub_only, sub_only_p, make_mks, cancelled = prompt_input_path(work, app.config, app.extlist)
    if cancelled:
        return False

    def compute_cache(base: str, op: str, default: str) -> str:
        if op == "":
            return base if default == "parent" else path.join(base, default)
        if op[0] == "?":
            return path.join(base, op[1:])
        return op

    ass_out = compute_cache(cpath, app.config.assout, "Subtitles")
    font_out = compute_cache(cpath, app.config.fontout, "Fonts")
    mkv_out = "" if app.config.mkvout == "" else (path.join(cpath, app.config.mkvout[1:])
                                                  if app.config.mkvout[0] == "?" else app.config.mkvout)

    do_mux = work in (2, 21)
    if medias:
        media_ass = get_subtitles(cpath, medias, subext=app.config.subext,
                                  match_strict=app.config.match_strict, s_subdir=app.config.s_subdir)
        if not media_ass:
            print(colorize("[ERROR] 找不到视频对应字幕", Ansi.RED))
            return True
        sub_langs: dict = {}
        force_sub_track = "?"
        muxer = 0
        clear_screen()
        if do_mux:
            if confirm("您需要为字幕轨道添加语言信息吗？"):
                sub_langs = langmod.get_sub_langs(app, media_ass, app.subname_lang)
            clear_screen()
            force_sub_track = langmod.get_force_sub(media_ass)
            if not make_mks:
                clear_screen()
                if confirm("您要封装为外置MKS文件吗？"):
                    make_mks = True
        if work == 21 or (work == 2 and app.no_mkvmerge):
            muxer = 1
        elif work == 20:
            muxer = 2
            do_mux = False
        for media in media_ass:
            work_info = app.temple_font_load(cpath, copy.deepcopy(app.font_info)) if app.config.fontload else app.font_info
            new_ass_paths, new_font_name, mkvr = run_pipeline(
                work_info, media_ass[media], app.config, mux=do_mux,
                out_dir=[ass_out, font_out, mkv_out], vpath=media,
                ass_langs=sub_langs, ff_muxer=muxer, force_sub_track=force_sub_track, make_mks=make_mks,
                font_loader=app.font_loader())
            if mkvr != -2:
                show_message_subset(new_ass_paths, new_font_name)
            else:
                break
    elif sub_only:
        work_info = app.temple_font_load(cpath, copy.deepcopy(app.font_info)) if app.config.fontload else app.font_info
        muxer = 2 if work == 20 else 0
        for subp in sub_only_p:
            new_ass_paths, new_font_name, mkvr = run_pipeline(
                work_info, [subp[1]], app.config, mux=False, out_dir=[ass_out, font_out, mkv_out],
                ff_muxer=muxer, font_loader=app.font_loader())
            if mkvr != -2:
                show_message_subset(new_ass_paths, new_font_name)
            else:
                break
    return True


# ---------------------------------------------------------------------------
# [U] 字幕批量转换
# ---------------------------------------------------------------------------

def text_coding_transcode_menu(app: App) -> None:
    """[U] 字幕批量转换为 UTF-8-BOM。"""
    clear_screen()
    print("Simple ASS/SSA/SRT to UTF-8-BOM Batch")
    s_path = ""
    loop = 0
    while not (path.isdir(s_path) or (path.isfile(s_path) and path.splitext(s_path)[1][1:].lower() in ("ass", "ssa"))):
        loop += 1
        if loop > 4:
            return
        s_path = input("字幕路径或字幕所在目录路径:").strip("\"' ")
    if path.isdir(s_path):
        loop = 0
        while input(f"""
搜索子目录: \033[33;1m{app.config.s_subdir}\033[0m (再不输入任何值\033[33;1m{7 - loop}\033[0m次回到主菜单)
是否要将目标目录的子目录的字幕一起转换?
\033[33;1m输入任意键(除空格)并回车\033[0m进入到下一步
\033[33;1m不输入任何值\033[0m切换是否搜索子目录
""").strip(" ") == "":
            loop += 1
            if loop > 6:
                return
            app.set_config(s_subdir=not app.config.s_subdir)
    transcode_batch(s_path, s_subdir=app.config.s_subdir)
    # 转码结果逐条输出，按回车后回主菜单
    wait_enter()


# ---------------------------------------------------------------------------
# [R] 字体信息重载
# ---------------------------------------------------------------------------

def font_reload_menu(app: App) -> None:
    """[R] 字体信息重载子菜单。"""
    entered = False
    clear_screen()
    if app.config.o_fontload:
        print("您已禁用系统字体读取，该功能不可用")
        pause()
        return
    cache_dir = cache_dir_or_none()
    print(f"""字体信息重载
缓存目录: "\033[1;33m{cache_dir}\033[0m"

[0] 回到主菜单
[1] 更新缓存
[2] 仅覆盖当前使用的缓存文件并重载
[3] 删除所有缓存文件并重载
[4] 新增自定义字体目录并重载

请选择:""")
    work = prompt_choice("", "01234")
    if work == 2:
        # [1] 更新缓存：忽略已有缓存重新读取字体并刷新缓存文件
        entered = True
        app.font_info = app.load_fonts(using_cache=False)
    elif work == 3:
        entered = True
        app.font_info = app.load_fonts(True)
    elif work == 4:
        entered = True
        if cache_dir:
            FontCache(cache_dir).clear()
        app.font_info = app.load_fonts(True)
    elif work == 5:
        clear_screen()
        font_paths = []
        font_path = input("目录路径，直接回车结束:").strip(" \"'")
        while font_path:
            if path.isdir(font_path):
                font_paths.append(font_path)
            else:
                print(colorize(f'[ERROR] "{font_path}"非有效目录', Ansi.RED))
            print("目录列表")
            for p in font_paths:
                print(f'"{p}"')
            print("")
            font_path = input("目录路径:").strip(" \"'")
        entered = True
        app.font_info = app.load_fonts(extra_dirs=font_paths)
    if entered:
        # 载入过程会输出统计日志，等待回车再回主菜单
        wait_enter()


# ---------------------------------------------------------------------------
# 主菜单
# ---------------------------------------------------------------------------

def main_menu(app: App, reload: bool = False) -> None:
    """初始化环境并显示主菜单。"""
    if not reload:
        if not app.config.o_fontload:
            app.font_info = progress_fonts(get_font_file_list(app.config.fontin), FontIndex(),
                                           quiet=app.config.start_quiet,
                                           duplicate_fonts=app.duplicate_fonts)
        detect_dependencies(app)

    clear_screen()
    fltip = colorize("已禁用系统字体读取", Ansi.PURPLE) if app.config.o_fontload else "包含乱码的名称"
    if app.ff_ver:
        ff_select = ""
        ff_message = ""
    else:
        ff_message = "\n[F] 检查并启用FFmpeg"
        ff_select = "F"
    print(f"""ASFMKV Python Remake {app.version} | (c) 2022-2024 yyfll{app.ff_ver}{app.mkv_ver}
字体名称数: [\033[1;33m{len(app.font_info.font_name)}\033[0m]（{fltip}）
请选择功能:
[A] 列出字幕所用字体
[B] 字体子集化 & MKV封装
[M] 字幕-视频名称匹配
[S] 搜索字体
[W] 检视旧格式字体
[U] 字幕批量转换UTF-8-BOM
[C] 检视重复字体: 重复名称[\033[1;33m{len(app.duplicate_fonts)}\033[0m]
其他:
[R] 字体信息重载
[D] 依赖与许可证
[L] 直接退出{ff_message}""")
    print("")
    work = prompt_choice("请选择: ", f"ABCSWDLRMU{ff_select}")

    if work == 1:
        list_ass_fonts(app)
    elif work == 2:
        font_subset_menu(app)
    elif work == 3:
        show_duplicate_fonts(app)
    elif work == 4:
        if not app.config.o_fontload:
            font_search_menu(app)
        else:
            clear_screen()
            print("您已禁用系统字体读取，该功能不可用")
            pause()
    elif work == 5:
        show_legacy_fonts(app)
    elif work == 8:
        font_reload_menu(app)
    elif work == 6:
        show_license(app.version)
    elif work == 7:
        if prompt_choice("您真的要退出吗", "YN") != 2:
            sys.exit()
    elif work == 9:
        sv_matching_menu(app)
    elif work == 10:
        text_coding_transcode_menu(app)
    elif work == 11:
        check_ff(app)
    else:
        sys.exit()
    clear_screen()


# 兼容旧名称
cFontSearch = font_search_menu
cSVMatching = sv_matching_menu
cFontSubset = font_subset_menu
cListAssFont = list_ass_fonts
cTextCodingTranscode = text_coding_transcode_menu
cLicense = show_license
loadMain = main_menu
