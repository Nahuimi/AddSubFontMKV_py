"""字体子集化：调用 fontTools subset，重写名称表并修复 ANSI CMAP。"""

from __future__ import annotations

import os
import re
import sys
from os import path
from typing import Optional

from fontTools import subset, ttLib

from ..core.console import Ansi, colorize
from ..utils.crc import subset_crc
from ..utils.fs import ensure_directory, sanitize_filename
from .cmap import char_exists_check


def name_str_for_subset(name, subfont_crc: str) -> str:
    """替换 NameID 为 1/3/4/6 的名称记录为新的 CRC 标识。"""
    if name.nameID in (1, 3, 4, 6):
        return subfont_crc
    try:
        return name.toStr()
    except Exception:
        return name.toBytes().decode("utf-16-be", errors="ignore")


def fix_ansi_cmap(new_font, gfs_uni: dict) -> None:
    """把 ANSI CMAP 转换为 Unicode CMAP，提升兼容性。"""
    cmap = new_font["cmap"].tables[0].cmap
    use_table = new_font["cmap"].tables[0]
    for table in new_font["cmap"].tables:
        if len(cmap) < len(table.cmap):
            cmap = table.cmap
            use_table = table

    def make_subtable(platform: int, enc_id: int, ascii_only: bool) -> object:
        sub = use_table.newSubtable(4)
        sub.platformID = platform
        sub.platEncID = enc_id
        sub.language = 0
        # 每个子表必须使用独立的 cmap 副本：旧实现三个子表共用同一个 dict 并原地改写，
        # 导致 ascii_only 分支在第二次遍历时已找不到本地编码键（Mac Roman 子表被写入 CJK 映射）。
        table_cmap = {k: v for k, v in cmap.items() if not ascii_only or k < 128}
        for local, uni in gfs_uni.items():
            glyph = table_cmap.get(local)
            if glyph is None:
                continue
            table_cmap[uni] = glyph
            if local != uni:
                table_cmap.pop(local, None)
        sub.cmap = table_cmap
        return sub

    first = make_subtable(0, 3, False)
    new_font["cmap"].tables = [first]
    new_font["cmap"].tables.append(make_subtable(1, 0, True))
    new_font["cmap"].tables.append(make_subtable(3, 1, False))
    new_font["cmap"].tables = new_font["cmap"].tables[:3]


def subset_fonts(ass_font: dict, font_dir: str, all_ttf: bool = False, *,
                 char_compatible: bool = True, ignore_lost: bool = True,
                 error_stop: bool = True) -> Optional[dict]:
    """按字幕需求子集化字体，返回 {原字体名: [新字体路径, 新字体名]}。"""
    new_font_name: dict = {}

    if path.exists(path.dirname(font_dir)):
        if not path.isdir(font_dir):
            if not ensure_directory(font_dir):
                font_dir = os.getcwd()
        if not path.isdir(font_dir):
            font_dir = path.dirname(font_dir)
    else:
        font_dir = os.getcwd()
    print(colorize("字体输出路径:", Ansi.YELLOW) + " " + colorize(f'"{font_dir}"', Ansi.WHITE))

    total = len(ass_font)
    for index, key in enumerate(ass_font.keys(), start=1):
        entry = ass_font[key]
        font_path, font_index, text, ass_name, fixed_name, styles = (
            key[0], key[1], entry[0], entry[1], entry[2], entry[4])
        ext = path.splitext(path.basename(font_path))[1]
        if all_ttf:
            sub_ext = ".ttf"
        elif ext[1:].lower() in ("otc", "ttc"):
            sub_ext = ext[:3].lower() + "f"
        else:
            sub_ext = ext
        font_name_file = sanitize_filename(fixed_name)
        sub_path = path.join(font_dir, font_name_file + sub_ext)
        print(colorize(f"[{index}/{total}]", Ansi.GREEN) + " " + colorize(f"正在子集化……{fixed_name}", Ansi.WHITE))

        if char_compatible:
            if re.search(r"[0-9]", text):
                text = re.sub(r"[0-9]", "", text.replace("\n", "")) + "0123456789"
            text = re.sub(r"[a-zA-Z]", "", text.replace("\n", "")) + "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

        gfs, gfs_uni, out_of_range = char_exists_check(font_path, font_index, text)
        gfs = gfs.lstrip(",")
        if out_of_range:
            shown = " ".join(c if c.isprintable() else "U+" + hex(ord(c))[2:].rjust(4, "0").upper()
                             for c in out_of_range)
            if ignore_lost:
                print(colorize(f"[WARNING] 已忽略不在字体中的字符: {shown}", Ansi.RED))
            else:
                print(colorize(f'[ERROR] 以下字符不在字体"{ass_name}"内', Ansi.RED) + f'\n"{shown}"\n'
                      + colorize(f'[ERROR] 以上字符不在字体"{ass_name}"内', Ansi.RED))
                print(colorize("[ERROR] 已停止子集化，如果您想要强行子集化，请启用ignoreLost", Ansi.RED))
                return None
        if not gfs:
            print(colorize("\n[WARNING] 没有要子集化的字符", Ansi.RED))
            continue

        common = ["--passthrough-tables", "--glyph-names", "--recommended-glyphs"]
        if gfs_uni.get("cmapFault", False):
            print(colorize("\n[WARNING] 字符缺失检查失败，该字体可能无法正常子集化", Ansi.RED))
            subset_args = [font_path, f"--text={text}", f"--output-file={sub_path}",
                           f"--font-number={font_index}", *common, "--ignore-missing-unicodes"]
        elif gfs_uni.get("textInput", False):
            subset_args = [font_path, f"--unicodes={gfs}", f"--output-file={sub_path}",
                           f"--font-number={font_index}", *common, "--ignore-missing-unicodes"]
        else:
            subset_args = [font_path, f"--glyphs={gfs}", f"--output-file={sub_path}",
                           f"--font-number={font_index}", *common,
                           "--name-legacy", "--legacy-cmap", "--ignore-missing-glyphs"]

        try:
            subset_rc = subset.main(subset_args)
            if subset_rc not in (None, 0):
                # fontTools 在参数/输入错误时以返回值 1/2 结束，不会抛异常
                raise RuntimeError(f"fontTools subset 返回 {subset_rc}")
        except Exception:
            print(colorize(f"\n[ERROR] {sys.exc_info()}", Ansi.RED))
            if error_stop:
                print(colorize(f'[WARNING] 字体"{path.basename(font_path)}"子集化失败，强制终止批量处理', Ansi.RED))
                return None
            print(colorize(f'[WARNING] 字体"{path.basename(font_path)}"子集化失败，将会保留完整字体', Ansi.RED))
            fallback_font = ttLib.TTFont(font_path, lazy=False, fontNumber=int(font_index))
            fallback_font.save(sub_path, False)
            fallback_font.close()
            for style in styles:
                for ass_name_part in ass_name.split("|"):
                    new_font_name[(ass_name_part, style[0], style[1])] = [sub_path, None]
            continue

        if not path.exists(sub_path):
            continue

        sub_crc = subset_crc(gfs, fixed_name)

        raw_font = ttLib.TTFont(font_path, lazy=True, fontNumber=int(font_index))
        new_font = ttLib.TTFont(sub_path, lazy=False)
        if len(new_font["name"].names) == 0:
            for i in range(7):
                if len(raw_font["name"].names) - 1 >= i:
                    new_font["name"].addName(name_str_for_subset(raw_font["name"].names[i], sub_crc), minNameID=-1)
        else:
            for i in range(len(raw_font["name"].names)):
                name = raw_font["name"].names[i]
                new_font["name"].setName(name_str_for_subset(name, sub_crc),
                                         name.nameID, name.platformID, name.platEncID, name.langID)

        if gfs_uni:
            fix_ansi_cmap(new_font, gfs_uni)

        if len(new_font.getGlyphOrder()) == 1 and ".notdef" in new_font.getGlyphOrder():
            new_font.close()
            if error_stop:
                raw_font.close()
                print(colorize(f'[WARNING] 字体"{path.basename(font_path)}"子集化失败，强制终止批量处理', Ansi.RED))
                if sub_path != font_path:
                    os.remove(sub_path)
                return None
            print(colorize(f'\n[WARNING] 字体"{path.basename(font_path)}"子集化失败，将会保留完整字体', Ansi.RED))
            # 必须先保存再关闭：TTFont(lazy=True) 关闭后无法再读取表数据
            raw_font.save(sub_path, False)
            raw_font.close()
            sub_crc = None
            crc_new = sub_path
        else:
            crc_new = f".{sub_crc}".join(path.splitext(sub_path))
            new_font.save(crc_new, False)
            new_font.close()
            raw_font.close()
        if path.exists(crc_new):
            if sub_path != crc_new:
                os.remove(sub_path)
            for style in styles:
                for ass_name_part in ass_name.split("|"):
                    new_font_name[(ass_name_part, style[0], style[1])] = [crc_new, sub_crc]
    print("")
    return new_font_name


# 兼容旧名称
getNameStr = name_str_for_subset
assFontSubset = subset_fonts
