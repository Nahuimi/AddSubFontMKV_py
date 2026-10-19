"""字幕重命名：预览与执行分离。"""

from __future__ import annotations

import os
from datetime import datetime
from os import path

from ..core.console import Ansi, colorize
from ..platform.shell import clear_screen


def rename_preview(media_ass: dict, s_start_a: int = 0, s_end_a: str = "", ann: str = "",
                   ann_list=None, *, match_strict: bool = True) -> tuple:
    """打印重命名预览并返回 ([(原路径, 新文件名)], 是否跳过全部)。"""
    ann_list = ann_list or []
    clear_screen()
    print("[重命名预览]\n")
    ren_list = []
    is_skip = False
    for media in media_ass:
        subs = media_ass[media]
        ann_up = 0
        for sub in subs:
            bname = path.basename(sub)
            if match_strict:
                if len(bname) >= len(media[0]) and media[0] == bname[:len(media[0])]:
                    print(colorize("跳过已匹配字幕", Ansi.YELLOW) + " " + colorize(f'"{bname}"', Ansi.WHITE))
                    is_skip = True
                    continue
            elif media[0] in bname:
                print(colorize("跳过已匹配字幕", Ansi.YELLOW) + " " + colorize(f'"{bname}"', Ansi.WHITE))
                is_skip = True
                continue
            if not ann_list:
                # 每条字幕单独计算注释，避免上一条的 ann 泄漏到下一条
                ann = ""
                reversed_name = path.splitext(bname)[0][::-1]
                if s_start_a - 2 > 1 and s_start_a - 2 < len(reversed_name):
                    if reversed_name[s_start_a - 2] == "." and s_end_a != ".":
                        ann = reversed_name[:s_start_a - 1][::-1]
                elif reversed_name.find(".") > 0:
                    ann = "." + reversed_name[:reversed_name.find(".")][::-1]
                    print("使用了暴力注释抽取，请务必检查注释是否有误")
                elif len(subs) > 1:
                    ann = f".sub{subs.index(sub)}"
                    print("注释自动检测失败，自动添加防重名注释")
            elif subs.index(sub) <= len(ann_list) - 1:
                ann = "." + ann_list[subs.index(sub)].lstrip(".")
            else:
                print("输入的项数不足，已自动补足")
                ann = "." + ann_list[-1].lstrip(".") + f"#{ann_up}"
                ann_up += 1
            print(colorize(f'"{bname}"', Ansi.WHITE, bold=True))
            print('>>>> ' + colorize(f'"{media[0]}', Ansi.YELLOW) + colorize(ann, Ansi.RED)
                  + colorize(f'{path.splitext(sub)[1]}"', Ansi.YELLOW) + "\n")
            ren_list.append((sub, f"{media[0]}{ann}{path.splitext(sub)[1]}"))
    if ren_list:
        print('字幕的注释是指类似以下文件名的高亮部分\n"\033[30;1m[VCB-Studio] Accel World [01][720p][x265_aac]'
              '\033[33;1m.Kamigami-sc\033[30;1m.ass\033[0m"')
    return ren_list, is_skip


def apply_rename(ren_list: list, log_dir: str) -> None:
    """执行重命名并写入日志。"""
    log_path = path.join(log_dir, f'subsRename_{datetime.now().strftime("%Y%m%d-%H%M%S")}.log')
    with open(log_path, mode="w", encoding="utf-8") as log_file:
        for r in ren_list:
            try:
                os.rename(r[0], path.join(path.dirname(r[0]), r[1]))
            except OSError:
                print(colorize(f'[ERROR] "{r[0]}"重命名失败', Ansi.RED))
            else:
                print(colorize("[SUCCESS]", Ansi.GREEN, bold=False)
                      + f' "{path.basename(r[0])}"\n          >>> ' + colorize(f'"{r[1]}"', Ansi.WHITE))
                try:
                    log_file.write(f"{r[0]}|{r[1]}\n")
                except OSError:
                    print(colorize("[ERROR] 日志文件写入失败", Ansi.RED))


# 兼容旧名称
renamePreview = rename_preview
