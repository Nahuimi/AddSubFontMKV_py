"""字体信息读取：解析 TTF/OTF/TTC/OTC 的 name 与 OS/2 表，并构建字体索引缓存。"""

from __future__ import annotations

import sys
from os import path
from typing import Optional

from fontTools import ttLib

from ..core.console import Ansi, colorize, pad_display
from ..platform.paths import cache_dir
from ..utils.crc import font_crc
from .cache import FontCache
from .models import FontIndex
from .name_decoder import NameDecoder
from .scanner import FONT_EXTS

# LCID 过滤器，用于选择字体名称所用语言
# 结构: { platformID(十进制): { LCID: 文本编码 } }
# 详情见 https://learn.microsoft.com/en-us/typography/opentype/spec/name
LCID_FILTER = {
    3: {2052: "gbk", 1042: "euc-kr", 1041: "shift_jis", 1033: "utf-16-be", 1028: "big5", 0: "utf-16-be"},
    2: {0: "ascii", 1: "utf_16_be", 2: "latin1"},
    1: {33: "gbk", 23: "euc_kr", 19: "big5", 11: "shift_jis", 0: "mac-roman"},
    0: {0: "utf-16-be", 1: "utf-16-be", 2: "utf-16-be", 3: "utf-16-be", 4: "utf-16-be", 5: "utf-16-be", 6: "utf-16-be"},
}

# 兼容旧名称
lcidfil = LCID_FILTER


def load_font_faces(font_path: str, ext: str, is_collection: bool) -> tuple:
    """按扩展名读取字体，返回 (faces, is_collection)；失败返回 (None, is_collection)。"""
    if ext in ("ttf", "otf"):
        try:
            return [ttLib.TTFont(font_path, lazy=True)], is_collection
        except Exception:
            print(colorize(f'\n[ERROR] "{font_path}": {sys.exc_info()}\n[TRY] 正在尝试使用TTC/OTC模式读取', Ansi.RED))
            try:
                faces = ttLib.TTCollection(font_path, lazy=True)
                print(colorize(f'[WARNING] 错误的字体扩展名"{font_path}"', Ansi.BLUE))
                return faces, True
            except Exception:
                print(colorize(f'\n[ERROR] "{font_path}": {sys.exc_info()}', Ansi.RED))
                return None, is_collection
    try:
        return ttLib.TTCollection(font_path, lazy=True), True
    except Exception:
        print(colorize(f'\n[ERROR] "{font_path}": {sys.exc_info()}\n[TRY] 正在尝试使用TTF/OTF模式读取', Ansi.RED))
        try:
            faces = [ttLib.TTFont(font_path, lazy=True)]
            print(colorize(f'[WARNING] 错误的字体扩展名"{font_path}"', Ansi.BLUE))
            return faces, is_collection
        except Exception:
            print(colorize(f'\n[ERROR] "{font_path}": {sys.exc_info()}', Ansi.RED))
            return None, is_collection


def read_face_names(face, font_path: str, decoder: NameDecoder) -> Optional[tuple]:
    """读取单个字体的名称/样式信息。返回 7 元组或 None。"""
    try:
        fs_selection = bin(face["OS/2"].fsSelection)[2:].zfill(10)
    except Exception:
        fs_selection = "1".zfill(10)
    is_italic = int(fs_selection[-1])
    is_bold = int(fs_selection[-6])

    dict_name_str = {"other": []}
    dict_fstyle = {"other": []}
    dict_family = {"other": []}
    try:
        len(face["name"].names)
    except Exception:
        return None

    is_warning = False
    last_encoding = ""
    for ii, name in enumerate(face["name"].names):
        platform = name.platformID
        lang = name.langID
        encoding = LCID_FILTER.get(platform, {}).get(lang, "other") if platform in LCID_FILTER else "other"

        if name.nameID == 1:
            family, last_encoding, is_warning = decoder.read(face, ii, font_path)
            family = family.strip(" ").strip("\u0000")
            if encoding not in dict_family or isinstance(dict_family[encoding], str):
                dict_family[encoding] = family
            else:
                dict_family["other"].append(family)
        elif name.nameID == 2:
            style, last_encoding, is_warning = decoder.read(face, ii, font_path)
            if style is not None:
                style = style.strip(" ").strip("\u0000")
                if encoding not in dict_fstyle or isinstance(dict_fstyle[encoding], str):
                    dict_fstyle[encoding] = style
                else:
                    dict_fstyle["other"].append(style)
        elif name.nameID == 4:
            full, last_encoding, is_warning = decoder.read(face, ii, font_path)
            if full is None:
                continue
            full = full.strip(" \u0000")
            if encoding not in dict_name_str:
                dict_name_str[encoding] = [full]
            elif full not in dict_name_str[encoding]:
                dict_name_str[encoding].append(full)
        else:
            continue

    return dict_name_str, is_italic, is_bold, dict_fstyle, dict_family, is_warning, last_encoding


def progress_fonts(fl: list, font_info: Optional[FontIndex] = None, overwrite: bool = False,
                   using_cache: bool = True, *, cache: Optional[FontCache] = None,
                   decoder: Optional[NameDecoder] = None, quiet: bool = True,
                   duplicate_fonts: Optional[dict] = None) -> FontIndex:
    """
    读取字体文件，填充 FontIndex 并更新重复字体词典。

    :param fl: [[字体绝对路径, 来源标记], ...]
    :param duplicate_fonts: 重复字体累加器；结束后原地替换为 {(路径1, 路径2): [名称, ...]}
    :param quiet: 为 True 时不输出名称编码修正过程（对应旧 startQuiet）
    """
    font_info = font_info if font_info is not None else FontIndex()
    decoder = decoder if decoder is not None else NameDecoder(quiet=quiet)
    cache = cache if cache is not None else FontCache(cache_dir())
    dups = duplicate_fonts if duplicate_fonts is not None else {}

    warning_font = font_info.warning_font
    font_family = font_info.font_family
    font_n_lower = font_info.font_n_lower
    f_n = font_info.font_name

    new_cache: dict = {}
    loaded_cache: dict = {}

    total = len(fl)
    print(colorize("正在读取字体信息...", Ansi.GREEN))
    for si in range(total):
        source = fl[si][0]
        fl[si][1] = str(fl[si][1])
        from_custom = bool(fl[si][1])

        ext = path.splitext(source)[1][1:].lower()
        if ext not in FONT_EXTS:
            continue

        file_crc = ""
        is_tc = False
        read_cache = None
        dir_key = cache.dir_key(path.dirname(source))

        if using_cache:
            if dir_key not in loaded_cache:
                loaded_cache[dir_key] = cache.load(dir_key)
            dir_cache = loaded_cache[dir_key]
            file_crc = font_crc(source)
            cached = dir_cache.get(file_crc)
            if cached is not None:
                read_cache = cached
                if len(read_cache) > 1:
                    is_tc = True

        if read_cache is None:
            print("\r" + colorize(f"{si + 1}/{total} {(si + 1) / total * 100:.2f}%", Ansi.GREEN)
                  + " " + colorize(pad_display(path.dirname(source)), Ansi.WHITE), end="", flush=True)
        else:
            print("\r" + colorize(f"{si + 1}/{total} {(si + 1) / total * 100:.2f}%", Ansi.GREEN)
                  + " " + colorize("【缓存】" + pad_display(path.dirname(source)), Ansi.WHITE), end="", flush=True)

        if read_cache is None:
            faces, is_tc = load_font_faces(source, ext, is_tc)
            if faces is None:
                continue
        else:
            faces = read_cache

        if not file_crc:
            file_crc = font_crc(source)
        new_cache.setdefault(dir_key, {"?version": cache.version})
        if new_cache[dir_key].get("?version", cache.version) != cache.version:
            new_cache[dir_key]["?version"] = cache.version
        new_cache[dir_key].setdefault(file_crc, {})

        # 缓存命中时 faces 是 {索引: 7 元组}，实时解析时是 TTFont 列表；
        # 统一成 (索引, 条目) 迭代，避免旧实现 enumerate + faces[item] 两套类型混用。
        face_items = enumerate(faces) if read_cache is None else faces.items()
        for ti, item in face_items:
            tencodings: list = []
            if read_cache is None:
                data = read_face_names(item, source, decoder)
                if data is None:
                    # 读取失败时把当前及后续尚未关闭的 face 一并关闭，避免字体文件被占用
                    for face in faces[ti:]:
                        face.close()
                    break
                dict_name_str, is_italic, is_bold, dict_fstyle, dict_family, is_warning, enc = data
                for key, value in dict_family.items():
                    if key == "other":
                        for n in value:
                            font_family.setdefault(n, {})
                    else:
                        font_family.setdefault(value, {})
            else:
                entry = item
                enc = entry[6]
                is_warning = entry[5]
                dict_name_str = entry[0]
                is_italic = int(entry[1])
                is_bold = int(entry[2])
                dict_fstyle = entry[3]
                dict_family = entry[4]
                for key, value in dict_family.items():
                    if key == "other":
                        for n in value:
                            font_family.setdefault(n, {})
                    else:
                        font_family.setdefault(value, {})

            if is_warning and enc not in tencodings:
                tencodings.append(enc)

            new_cache[dir_key][file_crc][ti] = (dict_name_str, is_italic, is_bold, dict_fstyle,
                                                dict_family, is_warning, enc)

            for enc_key, name_list in dict_name_str.items():
                for namestr in name_list:
                    if is_warning and namestr not in warning_font:
                        warning_font[namestr.lower()] = [c for c in tencodings if c]
                    if f_n.get(namestr) and not overwrite:
                        dupp = f_n[namestr][0]
                        if (dupp != source
                                and path.splitext(path.basename(dupp))[0] != path.splitext(path.basename(source))[0]
                                and not from_custom and f_n[namestr][2] == dict_fstyle):
                            if not quiet:
                                print(colorize(
                                    f'\n[WARNING] 字体"{path.basename(f_n[namestr][0])}"与字体'
                                    f'"{path.basename(source)}"的名称"{namestr}"重复！', Ansi.PURPLE))
                            if dups.get(namestr) is not None:
                                if source not in dups[namestr]:
                                    dups[namestr].append(source)
                            else:
                                dups[namestr] = [dupp, source]
                    else:
                        f_n[namestr] = [source, ti, dict_fstyle, is_tc]
                    font_n_lower.setdefault(namestr.lower(), namestr)

                if dict_family:
                    family_names = []
                    if enc_key in dict_family and isinstance(dict_family[enc_key], str):
                        family_names.append(dict_family[enc_key])
                    else:
                        family_names.extend(dict_family["other"])
                    for family in family_names:
                        font_family.setdefault(family, {}).setdefault((is_italic, is_bold), [])
                        if namestr not in font_family[family][(is_italic, is_bold)]:
                            font_family[family][(is_italic, is_bold)].append(namestr)

            if dict_family:
                for key, value in dict_family.items():
                    if key == "other":
                        continue
                    if key not in dict_name_str:
                        namestr = list(dict_name_str.values())[-1][0]
                        if namestr.strip(" "):
                            font_family.setdefault(value, {}).setdefault((is_italic, is_bold), [namestr])

            # 每个 face 处理完立即关闭（TTC 多 face 时旧实现只关闭最后一个，句柄泄漏）
            if read_cache is None:
                item.close()

    for dir_key, data in new_cache.items():
        cache.save(dir_key, data)

    # 仅保留真正存在样式差异的字体家族
    for family in list(font_family.keys()):
        # 值形如 {(斜体, 粗体): [字体名, ...]}，旧实现拿 list 与 str 比较，条件永不成立
        if len(font_family[family]) <= 1 and all(v == [family] for v in font_family[family].values()):
            font_family.pop(family)

    # 将 {名称: [路径1, 路径2]} 重组为 {(路径1, 路径2): [名称]}
    rebuilt: dict = {}
    for name, dup_paths in dups.items():
        rebuilt.setdefault(tuple(dup_paths), []).append(name)
    dups.clear()
    dups.update(rebuilt)

    return font_info


# 兼容旧名称
fontProgress = progress_fonts
requireFontFile = load_font_faces
readFaceNames = read_face_names
