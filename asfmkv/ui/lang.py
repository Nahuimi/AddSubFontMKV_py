"""字幕语言辅助：ISO-639 语言表加载与交互式语言选择。"""

from __future__ import annotations

import json
import os
from os import path
from typing import Optional

from ..platform.shell import clear_screen, pause, prompt_choice
from ..utils.proc import run
from ..match.subtitles import get_sub_name


def split_subname_lang(raw: str) -> dict:
    """解析 subName2Lang 的配置文本为字典。"""
    result = {}
    for chunk in raw.split(";"):
        if "=" not in chunk:
            continue
        key, _, value = chunk.rpartition("=")
        result[key.strip().lower()] = value.strip().lower()
    return result


def get_iso_langs(runtime) -> Optional[dict]:
    """读取 APPDATA 中缓存的 ISO-639 语言名称对照表。"""
    lang_dir = path.join(os.getenv("APPDATA") or "", "ASFMKVpy", "isoLang")
    if not path.isdir(lang_dir):
        return None
    candidates = [
        d for d in os.listdir(lang_dir)
        if path.isdir(path.join(lang_dir, d)) and path.exists(path.join(lang_dir, d, "language.json"))
    ]
    if not candidates:
        return None
    prefer_lang = runtime.prefer_lang
    lang_sub_dir = ""
    if prefer_lang in candidates:
        lang_sub_dir = prefer_lang
    else:
        for d in candidates:
            if prefer_lang.split("_")[0] == d.split("_")[0]:
                lang_sub_dir = d
                break
    if not lang_sub_dir:
        return None

    with open(path.join(lang_dir, lang_sub_dir, "language.json"), mode="r", encoding="utf-8") as fh:
        all_iso = json.load(fh)
    bucket = runtime.iso639_all.setdefault(lang_sub_dir, {})
    for lc, name in all_iso.items():
        if len(lc) <= 3:
            bucket[lc] = name
    return runtime.iso639_all


def get_lang_name(runtime, code: str) -> str:
    """获取语言代码对应的本地化名称。"""
    show = runtime.translation_lang.get(code, "") or runtime.langlist.get(code, "")
    return show or code


def has_lang(runtime, lang: str) -> bool:
    """判断语言输入是否已在语言列表中（不区分大小写）。"""
    return lang.lower() in runtime.langlist or lang in runtime.langlist


def search_lang(runtime, query: str) -> Optional[str]:
    """在语言列表与本地化名称中搜索匹配的语言代码。"""
    hit_dict: dict = {}
    keys = query.lower().split(" ")
    for code, shown in runtime.langlist.items():
        hits = 0
        text = shown.lower()
        for key in keys:
            if key in text:
                hits += 1
                text = text.replace(key, "")
        hit_dict.setdefault(hits, {}).setdefault(shown, code)
        if code in runtime.translation_lang:
            hits = 0
            text = runtime.translation_lang[code].lower()
            for key in keys:
                if key in text:
                    hits += 1
                    text = text.replace(key, "")
            hit_dict.setdefault(hits, {}).setdefault(shown, code)
    if max(hit_dict.keys(), default=0) == 0:
        return None
    hit_out: dict = {}
    hit_index = -1
    for hit in range(1, max(hit_dict.keys()) + 1):
        print(f"【关键字匹配数 \033[1;33m{hit}\033[0m】")
        for shown, code in hit_dict[hit].items():
            hit_index += 1
            print(f"[\033[1;33m{hit_index}\033[0m] {get_lang_name(runtime, code)}")
            hit_out[hit_index] = code
    if len(hit_out) == 1:
        return next(iter(hit_out.values()))
    while True:
        select = input("请输入方括号内数字选择语言:")
        if select.isnumeric() and int(select) in hit_out:
            return hit_out[int(select)]


def get_all_sub_name(media_ass: dict) -> tuple:
    """从媒体-字幕对应表中提取不重复的字幕注释，用于语言/默认轨道选择。"""
    sub_langs: dict = {}
    sub_exp: dict = {}
    for media in media_ass:
        for sub in media_ass[media]:
            sub_name = get_sub_name(media, sub)[1]
            key = sub_name.lower() if sub_name else ""
            sub_langs.setdefault(key, "")
            sub_exp.setdefault(key, (media, sub))
    return sub_langs, sub_exp


def get_force_sub(media_ass: dict) -> str:
    """交互选择默认字幕轨道。"""
    sub_langs, sub_exp = get_all_sub_name(media_ass)
    max_num = len(str(len(sub_langs)))
    if len(sub_langs) == 1:
        return "?"

    def show_focus(current: str) -> None:
        print("【字幕示例】")
        for index, key in enumerate(sub_langs):
            media, sub = sub_exp[key]
            highlight = get_sub_name(media, sub)[1]
            base = path.basename(sub)
            highlight_str = base.replace(highlight, f"\033[1;31m{highlight}\033[1;33m")
            normal_str = base.replace(highlight, f"\033[1;31m{highlight}\033[0m")
            if key == current:
                print(f'[{str(index).rjust(max_num)}] "\033[1;33m{highlight_str}\033[0m" \033[1;34m默认轨道\033[0m')
            else:
                print(f'[{str(index).rjust(max_num)}] "{normal_str}"')

    while True:
        show_focus("?")
        print("")
        select = input("请输入字幕文件名前括号内的序号以选择默认字幕轨道: ")
        attempts = 0
        while (not select.strip(" ").isnumeric()
               or int(select.strip(" ")) not in range(len(sub_langs))) and attempts < 3:
            attempts += 1
            select = input("请输入字幕文件名前括号内的序号以选择默认字幕轨道: ")
        if attempts >= 3 or not select.strip(" ").isnumeric():
            return "?"
        clear_screen()
        show_focus(list(sub_langs.keys())[int(select)])
        print("")
        if input("确定选择这个字幕为默认轨道吗？[输入Y并回车确认]: ").lower().strip(" ") != "y":
            continue
        return list(sub_langs.keys())[int(select)]


def get_sub_langs(runtime, media_ass: dict, sub_name2lang: dict) -> dict:
    """交互为每个字幕注释分配 ISO-639 语言代码。"""
    sub_langs, sub_exp = get_all_sub_name(media_ass)
    clear_screen()
    if not runtime.iso639_all:
        get_iso_langs(runtime)
    if not runtime.translation_lang:
        prefer = runtime.prefer_lang
        runtime.translation_lang = (runtime.iso639_all.get(prefer, {})
                                    or runtime.iso639_all.get(prefer.split("_")[0], {}))
        if not runtime.translation_lang:
            for key in runtime.iso639_all:
                if key.split("_")[0] == prefer.split("_")[0]:
                    runtime.translation_lang = runtime.iso639_all[key]
                    break
        if not runtime.no_mkvmerge:
            print("正在从mkvmerge获取ISO-639语言列表，请稍等...")
            proc = run(["mkvmerge", "--list-languages"])
            out = proc.stdout or ""
            for line in out.splitlines()[2:]:
                parts = line.replace("\n", "").split("|")
                for part in parts[1:]:
                    if part.strip(" "):
                        runtime.langlist[part.strip(" ").lower()] = parts[0].strip(" ")
        else:
            runtime.langlist = runtime.translation_lang

    no_lang = not runtime.langlist
    restart = True
    while restart:
        restart = False
        sub_langs, sub_exp = get_all_sub_name(media_ass)
        for i in sub_langs:
            def show_focus(current: str) -> None:
                print("【字幕示例】")
                for key in sub_langs:
                    show_lang = get_lang_name(runtime, sub_langs[key].lower())
                    if show_lang == sub_langs[key].lower():
                        show_lang = get_lang_name(runtime, sub_langs[key])
                    show_iso = f"{sub_langs[key].lower()}: "
                    media, sub = sub_exp[key]
                    highlight = get_sub_name(media, sub)[1]
                    highlight_str = path.basename(sub).replace(highlight, f"\033[1;31m{highlight}\033[1;33m")
                    if key == current:
                        print(f'"\033[1;33m{highlight_str}\033[0m" \033[1;34m{show_iso}{show_lang}\033[0m')
                    else:
                        print(f'"{path.basename(sub)}" \033[1;34m{show_iso}{show_lang}\033[0m')

            lang = ""
            auto_get = False
            while not has_lang(runtime, lang):
                clear_screen()
                show_focus(i)
                print("")
                if not auto_get:
                    if i in sub_name2lang:
                        lang = sub_name2lang[i]
                        auto_get = True
                    elif runtime.config.rude_sub_n2_l:
                        for key in sub_name2lang:
                            if key.lstrip(".") in i:
                                lang = sub_name2lang[key]
                                auto_get = True
                                break
                if not auto_get:
                    if runtime.no_mkvmerge and runtime.translation_lang:
                        search_hint = "仅本地语言搜索"
                    elif runtime.no_mkvmerge:
                        search_hint = "该状态下不可用"
                    elif not runtime.translation_lang:
                        search_hint = "仅英文English搜索"
                    else:
                        search_hint = "English/本地语言搜索"
                    if sub_langs[i]:
                        print("该项之前已经有赋值了，如果您不想修改，请直接回车")
                    elif runtime.no_mkvmerge:
                        print("可接受语言代码: ISO-639-2T/3，不区分大小写")
                    else:
                        print("可接受语言代码: ISO-639-1/2/3，不区分大小写")
                    print("常用语言代码: [chi]中 [eng]英 [jpn]日 [kor]韩 [und]未知")
                    if not runtime.langlist:
                        print("[WANRING] 您正在无语言编码参考文件的环境下运行，程序无法确认您输入的正确性")
                    lang = input(f"请输入语言(或搜索语言名称，{search_hint}):").strip(" \'\"")
                    if not lang:
                        if sub_langs[i]:
                            lang = sub_langs[i]
                            auto_get = True
                        else:
                            continue

                if not auto_get:
                    if no_lang:
                        if len(lang) in (2, 3) and all(ch.isalpha() for ch in lang):
                            lang = lang.lower()
                    elif not has_lang(runtime, lang):
                        found = search_lang(runtime, lang)
                        if found is None:
                            print("找不到对应语言")
                            pause()
                            continue
                        lang = found

                clear_screen()
                show_focus(i)
                lname = get_lang_name(runtime, lang.lower())
                if lname == lang.lower():
                    lname = get_lang_name(runtime, lang)
                if auto_get and i in sub_name2lang:
                    print("\n用户自定义匹配表有对应语言")
                print(f'语言为"\033[1;33m{lname}\033[0m"，确定吗？')
                if not prompt_confirm():
                    lang = ""
                    auto_get = False
                    continue
                sub_langs[i] = lang
                auto_get = False
                if i == list(sub_langs.keys())[-1]:
                    clear_screen()
                    print("【完整预览】")
                    for key in sub_langs:
                        highlight = get_sub_name(sub_exp[key][0], sub_exp[key][1])[1]
                        highlight_str = path.basename(sub_exp[key][1]).replace(
                            highlight, f"\033[1;31m{highlight}\033[0m")
                        print(f'"{highlight_str}" \033[1;34m{get_lang_name(runtime, sub_langs[key].lower())}\033[0m')
                    print("\n【完整预览】")
                    print("请检查您的输入是否正确，要重新开始吗(R)？或是放弃(C)？按Y继续封装")
                    choice = prompt_choice("", "RYC")
                    if choice == 1:
                        restart = True
                        break
                    if choice == 3:
                        return {}
                    clear_screen()
            if restart:
                break
    return sub_langs


def prompt_confirm(prompt: str = "是否继续") -> bool:
    """Yes/No 确认，Y 为同意。"""
    from ..platform.shell import confirm
    return confirm(prompt)


# 兼容旧名称
getISOLangs = get_iso_langs
getAllSubName = get_all_sub_name
getForceSub = get_force_sub
getSubsLangsV2 = get_sub_langs
_get_lang_name = get_lang_name
_has_lang = has_lang
_search_lang = search_lang
