"""字体索引：缺字检查、字体解析（resolve）与多来源合并。"""

from __future__ import annotations

from os import path
from typing import Optional

from ..core.console import Ansi, colorize
from .models import FontIndex


def resolve_from_family(font_family: dict, fn: str, is_italic: int, is_bold: int) -> str:
    """按字体家族与粗斜体回退查找字体名。"""
    candidates = font_family.get(fn)
    if not candidates:
        return fn
    for key in ((is_italic, is_bold), (0, is_bold), (is_italic, 0), (0, 0)):
        if candidates.get(key):
            return candidates[key][0]
    return fn


def merge_font_index(font_info: FontIndex, add: FontIndex, priority: bool) -> None:
    """把新读入的字体信息合并进主 FontIndex。"""
    if priority:
        font_info.font_name.update(add.font_name)
        font_info.font_n_lower.update(add.font_n_lower)
        font_info.font_family.update(add.font_family)
        font_info.warning_font.update(add.warning_font)
        return
    for key, value in add.font_name.items():
        font_info.font_name.setdefault(key, value)
    for key, value in add.font_n_lower.items():
        font_info.font_n_lower.setdefault(key, value)
    for key, value in add.font_family.items():
        font_info.font_family.setdefault(key, value)
    for key, value in add.warning_font.items():
        font_info.warning_font.setdefault(key, value)


def merge_ass_font_entry(ass_font: dict, dict_key: tuple, key: tuple, font_list: dict,
                         name: str, check_file: str, is_italic: int, is_bold: int) -> None:
    """同一字体出现多个字幕名时的合并逻辑。"""
    entry = ass_font[dict_key]
    tfname = entry[2]
    new_names = entry[1].split("|")
    old_str = font_list[key]
    for new_name in new_names:
        if key[0].lower() not in "|".join(new_names).lower():
            k1, k2 = 0, 0
            for ii in (0, 1):
                k1, k2 = ii, 0
                if font_list.get((new_name, k1, 0)) is not None:
                    break
                if font_list.get((new_name, k1, 1)) is not None:
                    k2 = 1
                    break
            new_str = font_list.get((new_name, k1, k2), "")
            new_name = "|".join([key[0], new_name])
            for ch in new_str:
                if ch not in old_str:
                    old_str += ch
        else:
            for ch in entry[0]:
                if ch not in old_str:
                    old_str += ch
        if name.lower() not in tfname.lower():
            tfname = "|".join([name, tfname])
        ass_font[dict_key] = [old_str, new_name, tfname,
                              list(set(entry[3] + [check_file])),
                              list(set(entry[4] + [(is_italic, is_bold)]))]
        font_list[key] = old_str


def update_ass_font(ass_font: Optional[dict], ass_font2: Optional[dict]) -> Optional[dict]:
    """合并两个字幕字体需求字典。"""
    if ass_font2 is None:
        return None
    if ass_font is None:
        ass_font = {}
    for key, value in ass_font2.items():
        if ass_font.get(key):
            ass_font[key] = [
                ass_font[key][0] + "".join(c for c in value[0] if c not in ass_font[key][0]),
                ass_font[key][1] + "".join("|" + s for s in value[1].split("|")
                                           if s.lower() not in ass_font[key][1].lower()),
                ass_font[key][2] + "".join("|" + s for s in value[2].split("|")
                                           if s.lower() not in ass_font[key][2].lower()),
                list(set(ass_font[key][3] + value[3])),
                list(set(ass_font[key][4] + value[4])),
            ]
        else:
            ass_font[key] = value
    return ass_font


def check_ass_font(font_list: dict, font_info: FontIndex,
                   only_check: bool = False, check_file: str = "", *,
                   loader=None, ignore_lost_fonts: bool = False,
                   warning_stop: bool = False, f_priority: bool = False,
                   noreg_font_list=None) -> tuple:
    """
    检查系统/自定义字体是否满足字幕需求，缺少时（交互模式）要求用户提供。

    :param loader: 载入追加字体的回调，签名为 loader(target) -> FontIndex；为 None 时跳过交互追加
    :param ignore_lost_fonts: 对应旧 noRequestFont，缺少字体时不索要
    :param noreg_font_list: 目录追加时使用的字体清单函数，默认 scanner.get_font_file_list

    返回 (assfont, font_info)：
      assfont: {(字体路径, 索引): [字符, ASS内字体名, 修正字体名, [字幕文件], [(斜体, 粗体)]]}
    """
    ass_font: dict = {}
    font_name = font_info.font_name
    font_n_lower = font_info.font_n_lower
    font_family = font_info.font_family
    warning_font = font_info.warning_font

    for key in list(font_list.keys()):
        is_bold = key[2]
        is_italic = key[1]
        name = resolve_from_family(font_family, key[0], is_italic, is_bold)
        cok = False
        resolved = name
        if name not in font_name:
            if font_n_lower.get(name.lower()):
                resolved = font_n_lower[name.lower()]
                cok = True
        elif not path.exists(font_name[name][0]):
            del font_name[name]
        else:
            cok = True

        direct_out = 0
        recheck = False
        if not cok:
            if only_check:
                ass_font[(name, name)] = ["", key[0], name, [check_file], [(is_italic, is_bold)]]
            elif ignore_lost_fonts:
                del font_list[key]
                continue
            elif loader is None:
                del font_list[key]
                continue
            else:
                print(colorize(f'[ERROR] 缺少字体"{name}"\n请输入追加的字体文件或其所在字体目录的绝对路径\n'
                               f'或输入"SKIPFONT"（全大写）以跳过剩余的缺少字体', Ansi.RED))
                in_font = ""
                while in_font == "" and direct_out < 3:
                    try:
                        in_font = input().strip("\'\" ")
                    except (EOFError, KeyboardInterrupt):
                        # 管道/重定向输入等非交互场景下 input() 会抛 EOFError，
                        # 旧实现会让整个流程直接崩溃，这里退回“跳过缺失字体”策略。
                        print(colorize("[WARNING] 当前环境无法读取输入，已跳过缺失字体", Ansi.YELLOW))
                        ignore_lost_fonts = True
                        del font_list[key]
                        break
                    if in_font == "SKIPFONT":
                        ignore_lost_fonts = True
                        del font_list[key]
                        break
                    if path.exists(in_font):
                        if path.isdir(in_font):
                            add_font = loader(in_font)
                            print()
                        else:
                            add_font = loader(in_font)
                            print()
                        if name.lower() not in add_font.font_n_lower:
                            target = (f'输入路径中"{in_font}"没有所需字体"{name}"' if path.isdir(in_font)
                                      else f'输入字体"{"|".join(add_font.font_name.keys())}"不是所需字体"{name}"')
                            print(colorize(f"[ERROR] {target}", Ansi.RED))
                            in_font = ""
                        else:
                            merge_font_index(font_info, add_font, f_priority)
                            cok = True
                            recheck = True
                    else:
                        print(colorize(f"[ERROR] 您没有输入任何字符！再回车{3 - direct_out}次回到主菜单", Ansi.RED))
                        direct_out += 1
                        in_font = ""

        if recheck:
            if name not in font_name:
                if font_n_lower.get(name.lower()) is not None:
                    resolved = font_n_lower[name.lower()]
                    cok = True
            elif not path.exists(font_name[name][0]):
                del font_name[name]
                cok = False
            else:
                cok = True

        if cok:
            if not only_check and resolved.lower() in warning_font:
                print(colorize(f'[WARNING] 字体"{resolved}"可能不能正常子集化', Ansi.RED))
                if warning_stop:
                    print(colorize(f'[WARNING] 请修复"{resolved}"，工作已中断', Ansi.RED))
                    return None, font_info
            if direct_out < 3:
                font_path = font_name[resolved][0]
                font_index = font_name[resolved][1]
                dict_key = (font_path, str(font_index))
                if ass_font.get(dict_key) is None:
                    ass_font[dict_key] = [font_list[key], key[0], name, [check_file], [(is_italic, is_bold)]]
                else:
                    merge_ass_font_entry(ass_font, dict_key, key, font_list, name, check_file, is_italic, is_bold)
        if direct_out >= 3:
            return None, font_info

    return ass_font, font_info


# 兼容旧名称
fnGetFromFamilyName = resolve_from_family
checkAssFont = check_ass_font
updateAssFont = update_ass_font
