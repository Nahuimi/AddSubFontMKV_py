"""字幕扫描与剧集位置匹配。"""

from __future__ import annotations

import os
from os import path

from ..core.console import Ansi, colorize
from ..utils.fs import basename_no_ext


def get_subtitles(cpath: str, medias=None, *, subext=("ass", "ssa", "srt", "sup", "idx"),
                  match_strict: bool = True, s_subdir: bool = False) -> dict:
    """
    在目录中查找与媒体文件对应的字幕。

    返回 {媒体绝对路径: [字幕绝对路径, ...]}；未提供 medias 时结果位于键 'none'。
    """
    medias = medias or []
    media_ass: dict = {}
    if not medias:
        media_ass["none"] = []

    def consider(full: str, li: list) -> None:
        sext = path.splitext(full)
        if (li[0] in full and not match_strict) or \
           (li[0] == path.basename(full)[:len(li[0])] and match_strict):
            # .idx 必须与同名的 .sub 成对出现才有意义；
            # 旧实现误用 sext[1][:1]（始终是 "."）与相对路径判断，条件永远不成立。
            if sext[1][1:].lower() == "idx" and not path.exists(f"{sext[0]}.sub"):
                return
            media_ass.setdefault(li[1], []).append(full)

    if s_subdir:
        for root, _dirs, files in os.walk(cpath):
            for name in files:
                if path.splitext(name)[1][1:].lower() not in subext:
                    continue
                full = path.join(root, name)
                if ".subset" in path.basename(full):
                    continue
                if medias:
                    for li in medias:
                        vdir = path.dirname(li[1]).lower()
                        sdir = path.dirname(full).lower()
                        if (vdir in sdir and sdir not in vdir) or vdir == sdir:
                            consider(full, li)
                else:
                    media_ass["none"].append(full)
    else:
        for name in os.listdir(cpath):
            full = path.join(cpath, name)
            if path.isdir(full) or path.splitext(name)[1][1:].lower() not in subext:
                continue
            if ".subset" in path.basename(full):
                continue
            if medias:
                for li in medias:
                    if path.dirname(li[1]).lower() == path.dirname(full).lower():
                        consider(full, li)
            else:
                media_ass["none"].append(full)
    return media_ass


def most_common(values: list):
    """返回出现次数最多的项，按首次出现顺序稳定选取。"""
    if not values:
        return 0
    best, best_count = values[0], 0
    for value in dict.fromkeys(values):
        count = values.count(value)
        if count > best_count:
            best, best_count = value, count
    return best


def name_position(files: list) -> tuple:
    """自动推断文件名中剧集编号所在的位置（起始下标，结束字符）。"""
    collected = {"starts": [], "ends": []}
    for i1, name1 in enumerate(files):
        print("\r" + colorize(f"正在计算{i1 + 1}/{len(files)} {(i1 + 1) / len(files) * 100:.2f}%", Ansi.GREEN),
              end="", flush=True)
        diffs = []
        for name2 in files:
            if name2 == name1:
                continue
            stopped = False
            d_start = 0
            end_counters = [0, 0, 0]
            for i in range(len(name1)):
                if i >= len(name2):
                    break
                if name1[i] != name2[i] or stopped:
                    if stopped:
                        if not name1[i].isnumeric():
                            end_counters[0] = i
                        if not name2[i].isnumeric():
                            end_counters[1] = i
                        if name1[i] == name2[i] and not name1[i].isnumeric() and not name2[i].isnumeric():
                            end_counters[2] = i
                        if end_counters[0] * end_counters[1] * end_counters[2] > 0:
                            break
                    else:
                        stopped = True
                        d_start = i
            # 三个候选结束位置都为 0 表示本轮没有找到差异结束位置；旧实现会把
            # name1[0] 当成结束字符塞进 diffs，污染 most_common 的结果，这里直接丢弃。
            end_index = max(end_counters)
            if not 0 < end_index < len(name1):
                continue
            d_end = name1[end_index]
            if d_end:
                diffs.append((d_start, d_end, name2))
        collected["starts"].append(most_common([d[0] for d in diffs]))
        collected["ends"].append(most_common([d[1] for d in diffs]))
    print("")

    m_start = most_common(collected["starts"])
    m_end = most_common(collected["ends"])
    if (m_start - 1) in collected["starts"]:
        m_start -= 1
    return m_start, m_end


def name_matching_progress(medias: list, m_start: int, m_end: str, s_start: int, s_end: str, subs: list) -> dict:
    """按剧集位置匹配媒体与字幕，返回 {媒体元组: [字幕路径]}。"""
    media_ass: dict = {}
    for media in medias:
        media = tuple(media)
        media_ass[media] = []
        m_end_i = m_start + media[0][m_start:].find(m_end)
        if m_end_i < m_start:
            continue
        for sub in subs:
            sub_name = path.basename(sub)
            s_end_i = s_start + sub_name[s_start:].find(s_end)
            if s_end_i < s_start:
                continue
            m_key = media[0][m_start:m_end_i].lower()
            s_key = sub_name[s_start:s_end_i].lower()
            if m_key == s_key or m_key.rjust(s_end_i - s_start, "0") == s_key \
                    or m_key == s_key.rjust(m_end_i - m_start, "0"):
                media_ass[media].append(sub)
        if not media_ass[media]:
            del media_ass[media]
    return media_ass


def get_sub_name(video: str, sub: str) -> tuple:
    """返回 (字幕路径, 媒体名之外的注释部分)。"""
    b_sub = basename_no_ext(sub)
    b_video = basename_no_ext(video)
    return sub, b_sub[b_sub.find(b_video) + len(b_video):]


# 兼容旧名称
getSubtitles = get_subtitles
getSubName = get_sub_name
nameMatchingProgress = name_matching_progress
namePosition = name_position
_most_common = most_common
