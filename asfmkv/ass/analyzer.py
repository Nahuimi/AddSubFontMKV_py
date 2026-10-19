"""ASS 字体使用分析：汇总所需字体，并按子集化结果替换字体名。"""

from __future__ import annotations

import os
import re
from os import path

from ..core.console import Ansi, colorize
from ..utils.fs import ensure_directory, unique_path
from .writer import ass_file_write
from .tags import RE_FN_TAG


def ass_font_list(ass_info: dict, event_split: dict, negative_tag_detect: bool = False) -> dict:
    """汇总字幕所用字体与所需字符。返回 {(字体名, 斜体, 粗体): '字符'}。"""
    font_list: dict = {}
    if negative_tag_detect:
        effect_re = re.compile(r'\{.*?\\.*?\}')
    else:
        effect_re = re.compile(r'\{.*?\}')

    for index in event_split:
        for part in event_split[index]:
            font_name = part["Fontname"].lstrip("@")
            text = effect_re.sub("", part["Text"])
            if ass_info["Subset"] and font_name in ass_info["Subset"]:
                font_name = ass_info["Subset"][font_name]
            key = (font_name, abs(int(part["Italic"])), abs(int(part["Bold"])))
            if key in font_list:
                font_list[key] += "".join(ch for ch in set(text) if ch not in font_list[key])
            else:
                font_list[key] = "".join(set(text))
    return font_list


def ass_font_change(new_font_name: dict, ass_path: str, ass_info: dict, split_events: dict,
                    out_dir: str = "", cover: bool = False, embedded: bool = False) -> str:
    """按子集化结果替换 ASS 内的字体名与 \\fn 标签，并写出新字幕。返回新字幕路径。"""
    if new_font_name:
        for key in ass_info["Styles"]:
            style = ass_info["Styles"][key]
            style_italic = abs(int(style["Italic"]))
            style_bold = abs(int(style["Bold"]))
            font_str = style["Fontname"]
            nfn_key = (font_str.lstrip("@"), style_italic, style_bold)
            if new_font_name.get(nfn_key) is None:
                continue
            if new_font_name[nfn_key][1] is not None:
                style["Fontname"] = new_font_name[nfn_key][1].split("?")[0]
                if font_str[0] == "@":
                    style["Fontname"] = "@" + style["Fontname"]

        used = {k: v for k, v in new_font_name.items() if v[1] is not None}
        used_upper = {(k[0].upper(), k[1], k[2]): v for k, v in used.items()}

        if split_events:
            for fn_line in split_events:
                for part in split_events[fn_line]:
                    fname = part["Fontname"].lstrip("@")
                    if not fname:
                        continue
                    fl_key = (fname.upper(), abs(part["Italic"]), abs(part["Bold"]))
                    replace_fn = used_upper.get(fl_key)
                    if replace_fn is None:
                        # 旧实现在这里 os.system("timeout /T 10") 阻塞 10 秒，且该命令在
                        # 非 Windows 平台不存在；批量处理时每遇到一次就白等，CLI 下尤其糟糕。
                        print(colorize(
                            f'[WARNING] 找不到字体"{fname}"的子集化结果：该 \\fn 标签会保留原字体名，'
                            '可能导致缺字，请检查输出字幕', Ansi.YELLOW))
                        continue
                    if replace_fn[1] is not None:
                        original_text = ass_info["Events"][fn_line]["Text"]
                        for tag in RE_FN_TAG.findall(part["Text"]):
                            original_text = original_text.replace(tag, tag.replace(part["Fontname"], replace_fn[1]))
                        ass_info["Events"][fn_line]["Text"] = original_text
                        part["Fontname"] = replace_fn[1]

        for key in used:
            ass_info["Subset"][new_font_name[key][1]] = key[0].split("|")[0]

        if embedded:
            for key in new_font_name:
                font_file = new_font_name[key][0]
                if path.basename(font_file) in ass_info["Fonts"]:
                    continue
                with open(font_file, mode="rb") as fh:
                    ass_info["Fonts"][path.basename(font_file)] = fh.read()
                ass_info["Subset"][new_font_name[key][1]] = key[0].split("|")[0]

    if path.exists(path.dirname(out_dir)):
        if not path.isdir(out_dir):
            if not ensure_directory(out_dir):
                out_dir = os.getcwd()
    print(colorize("字幕输出路径:", Ansi.YELLOW) + " " + colorize(f'"{out_dir}"', Ansi.WHITE))
    if path.isdir(out_dir):
        new_ass_path = path.join(out_dir, ".subset".join(path.splitext(path.basename(ass_path))))
    else:
        new_ass_path = ".subset".join(path.splitext(ass_path))
    if path.exists(new_ass_path) and not cover:
        new_ass_path = unique_path(new_ass_path)

    ass_file_write(new_ass_path, ass_info, False, False, ignore_exists=cover)
    if embedded:
        print(colorize("字幕嵌入成功", Ansi.GREEN))
    return new_ass_path


# 兼容旧名称
assFontList = ass_font_list
assFontChange = ass_font_change
