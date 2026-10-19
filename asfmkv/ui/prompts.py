"""交互提示：输出路径校验、结果概览与许可证。"""

from __future__ import annotations

import re
from os import path

from ..core.console import Ansi, colorize
from ..platform.shell import clear_screen, pause
from ..utils.fs import get_file_list, sanitize_filename


def check_out_path(op: str, default: str) -> str:
    """校验输出目录配置：'' -> 默认；'?name' -> 子目录；绝对路径 -> 原样。"""
    if op == "":
        return default
    if op[0] == "?":
        return "?" + sanitize_filename(op[1:])
    if not path.isabs(op):
        print(colorize(f'[ERROR] 输入的必须是绝对路径或子目录名称！: "{op}"', Ansi.RED))
        pause()
        return default
    if path.isdir(op):
        return op
    if path.isfile(op):
        return path.dirname(op)
    print(colorize(f'[ERROR] 输入的必须是目录路径或子目录名称！: "{op}"', Ansi.RED))
    pause()
    return default


def show_message_subset(new_ass_paths: list, new_font_name: dict) -> None:
    """打印子集化/封装结果概览。"""
    for ap in new_ass_paths:
        if path.exists(ap):
            print(colorize("成功:", Ansi.GREEN) + " " + colorize(f'"{path.basename(ap)}"', Ansi.WHITE))
    seen = []
    for nf, value in new_font_name.items():
        if path.exists(value[0]) and value[1] not in seen:
            if value[1] is None:
                print(colorize("失败:", Ansi.RED) + colorize(f' "{nf[0]}"', Ansi.WHITE)
                      + " >> " + colorize(f'"{path.basename(value[0])}"', Ansi.WHITE))
            else:
                print(colorize("成功:", Ansi.GREEN) + colorize(f' "{nf[0]}"', Ansi.WHITE)
                      + " >> " + colorize(f'"{path.basename(value[0])}" ({value[1]})', Ansi.WHITE))
        seen.append(value[1])


def show_license(version: str) -> None:
    """输出依赖与许可证信息。"""
    clear_screen()
    print(f"""AddSubFontMKV Python Remake {version}

Apache-2.0 License
https://www.apache.org/licenses/

Copyright(c) 2022-2024 yyfll

Requirements:
fontTools     |  MIT License
chardet       |  LGPL-2.1 License
colorama      |  BSD-3 License

Selective Requirements:
mkvmerge      |  GPL-2 License
ffmpeg        |  LGPL-2.1 License
language-list |  MIT License
""")
    pause()


def prompt_input_path(work: int, config, extlist) -> tuple:
    """
    请求用户输入文件/目录路径并解析出媒体与字幕。

    返回 (cpath, medias, sub_only, sub_only_p, make_mks, cancelled)。
    """
    cpath = ""
    give_up = False
    sub_only = False
    sub_only_p: list = []
    while not path.exists(cpath) and not give_up:
        give_up = True
        cpath = input("不输入任何值 直接回车回到上一页面\n请输入文件或目录路径: ").strip('" ')
        if cpath == "":
            print("没有输入，回到上级菜单")
        elif not path.isabs(cpath):
            print(colorize(f'[ERROR] 输入的必须是绝对路径！: "{cpath}"', Ansi.RED))
        elif not path.exists(cpath):
            print(colorize(f'[ERROR] 找不到路径: "{cpath}"', Ansi.RED))
        elif path.isfile(cpath):
            test_ext = path.splitext(cpath)[1][1:].lower()
            if test_ext in extlist:
                give_up = False
            elif test_ext in ("ass", "ssa") and work in (1, 20):
                give_up = False
                sub_only = True
            else:
                print(colorize(f'[ERROR] 扩展名不正确: "{cpath}"', Ansi.RED))
        elif not path.isdir(cpath):
            print(colorize(f'[ERROR] 输入的应该是目录或媒体文件！: "{cpath}"', Ansi.RED))
        else:
            give_up = False
    if give_up:
        return cpath, [], sub_only, sub_only_p, False, True

    medias: list = []
    make_mks = False
    if path.isfile(cpath):
        if not sub_only:
            medias = [[path.splitext(path.basename(cpath))[0], cpath]]
        else:
            sub_only_p = [(path.splitext(path.basename(cpath))[0], cpath)]
        cpath = path.dirname(cpath)
    else:
        medias = get_file_list(cpath, extlist, config.v_subdir) if work != 20 else []
        if not medias:
            sub_only_p = get_file_list(cpath, ["ass", "ssa"], config.s_subdir)
            if work == 20:
                sub_only = True
            elif sub_only_p:
                clear_screen()
                print(colorize("[WARNING]", Ansi.YELLOW))
                print('您输入的目录下只有字幕而无视频，需要输入文件名规则才可进行下一步。\n'
                      '请将字幕对应的视频文件名中不统一的部分替换为通配符"\033[1;33m*\033[0m"，以便匹配视频文件名\n'
                      '例如字幕："[dmhy][ARIA_The_ANIMATION][\033[1;33m01\033[0m][DVDRIP][AVC_AC3][\033[1;33mF49E85D5\033[0m].sc.ass"\n'
                      '需要输入："[dmhy][ARIA_The_ANIMATION][\033[1;33m*\033[0m][DVDRIP][AVC_AC3][\033[1;33m*\033[0m]"')
                trying = 0
                sub_only_v = ""
                while not sub_only_v:
                    sub_only_v = input("视频文件名规则: ").strip(" ")
                    if not sub_only_v:
                        trying += 1
                    elif not confirm_prompt('"确定吗？"'):
                        sub_only = True
                        give_up = True
                    else:
                        pattern = re.compile(re.escape(sub_only_v).replace(r"\*", ".*?"))
                        for fn, fp in sub_only_p:
                            found = pattern.search(fn)
                            if found:
                                media_name = found.group()
                                medias.append((media_name, path.join(path.dirname(fp), media_name + ".mp4")))
                        medias = list(dict.fromkeys(medias))
                        if medias:
                            sub_only_p.clear()
                            sub_only = False
                            make_mks = True
                        else:
                            print(colorize("[ERROR] 文件名规则有误：匹配失败", Ansi.RED))
                            give_up = True
                    if trying >= 3:
                        give_up = True
            else:
                print(colorize("[ERROR] 路径下找不到字幕", Ansi.RED))
                give_up = True
    return cpath, medias, sub_only, sub_only_p, make_mks, give_up


def confirm_prompt(prompt: str = "是否继续") -> bool:
    from ..platform.shell import confirm
    return confirm(prompt)


# 兼容旧名称
checkOutPath = check_out_path
showMessageSubset = show_message_subset
_prompt_input_path = prompt_input_path
