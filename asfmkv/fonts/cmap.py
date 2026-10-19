"""字体 CMAP 检查：确认字体是否包含所需字形，并给出字形名/Unicode 映射。"""

from __future__ import annotations

import re

from fontTools import ttLib


def char_exists_check(font_path: str, font_number: int, to_check: str) -> tuple:
    """
    检查字体 CMAP 是否包含所需字符。

    返回 (gfs, gfs_uni, out_of_range)：
      gfs          Unicode CMAP 时返回 'uXXXX' 列表；ANSI CMAP 时返回字形名列表
      gfs_uni      ANSI CMAP 时返回 {本地编码: Unicode}；另有特殊键 cmapFault / textInput
      out_of_range 字体中缺少的字符
    """
    font = ttLib.TTFont(font_path, fontNumber=int(font_number), lazy=True)
    to_check = re.sub(r"[\u007F]", "", to_check)
    cmap: dict = {}
    out_of_range = ""
    try:
        for table in font["cmap"].tables:
            if table.isUnicode() and len(table.cmap) > len(cmap):
                cmap = table.cmap
    except Exception:
        font.close()
        return "cmapFault", {"cmapFault": True}, ""

    glyphs: list = []
    if cmap:
        for ch in to_check:
            dec = ord(ch)
            if cmap.get(dec) is None:
                out_of_range += ch
            else:
                add_char = hex(dec)[2:]
                if len(add_char) > 4:
                    add_char = "u" + add_char.rjust(8, "0")
                elif len(add_char) > 2:
                    add_char = "u" + add_char.rjust(4, "0")
                glyphs.append(add_char)
        font.close()
        return ",".join(glyphs), {"textInput": True}, out_of_range

    # 无 Unicode CMAP，回退到 ANSI CMAP
    gfs_uni: dict = {}
    if len(font["cmap"].tables) > 0:
        tcoding = ""
        for table in font["cmap"].tables:
            if len(table.cmap) > len(cmap):
                cmap = table.cmap
                tcoding = table.getEncoding()
        if not cmap:
            font.close()
            return "", {}, ""
        if tcoding.lower() in ("gb2312", "x_mac_simp_chinese_ttx"):
            tcoding = "gbk"
        print(f'\n\033[1;33m[Warning] 正在使用地区编码\033[0m"{tcoding}"\033[1;33m读取CMAP映射表\033[0m')
        for ch in to_check:
            if re.match(r"[\u0000-\u007F]", ch):
                dec = ord(ch)
            else:
                try:
                    dec = int("".join(hex(b).lstrip("0x") for b in ch.encode(tcoding)), 16)
                except UnicodeError as exc:
                    show_utf = "U+" + "".join(hex(b).lstrip("0x").upper() for b in ch.encode("utf-16-be"))
                    raise UnicodeError(
                        f'使用文本编码"{exc.encoding}"处理字符"{show_utf}"时出错，'
                        f'请确认该字符是否正确。字符正则表达式："[\\u{show_utf[2:]}]"')
            if dec >= 0 and cmap.get(dec) is not None:
                glyphs.append(cmap[dec])
                gfs_uni[dec] = ord(ch)
            else:
                out_of_range += ch
    font.close()
    return ",".join(glyphs), gfs_uni, out_of_range