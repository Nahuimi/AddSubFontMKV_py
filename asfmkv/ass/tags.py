"""ASS/SSA 特效标签拆分：分析每行文本所用的字体与粗斜体。"""

from __future__ import annotations

import re

from ..core.errors import AssParseError

# 事件 Tags 拆分所用正则
RE_VECTOR = re.compile(r'\{.*?\\p[1-9]\d*.*?\}([\s\S]*?)\{.*?\\p0.*?\}')
RE_VECTOR_OPEN = re.compile(r'\{.*?\\p[1-9]\d*.*?\}')
RE_EFFECT = re.compile(r'\{.*?(?:\\b[1-9]00|\\b[0-1]|\\i[0-1]|\\fn|\\r).*?\}')
RE_IB_ON = re.compile(r'\\b[1-9]00|\\b[0-1]|\\i[0-1]|\\fn|\\r')
RE_ALL_TAGS = re.compile(r'\{.*?\}')
RE_EFFECT_DEL = re.compile(r'\{.*?\}|\\[nNhs]|\n')
RE_FIND_R = re.compile(r'\\r.*?[\\\}]')
RE_FIND_B = re.compile(r'\\b[7-9]00|\\b1')
RE_FIND_FN = re.compile(r'\\fn.*?[\\\}]')
RE_FN_TAG = re.compile(r'\{.*?\\fn.*?\}')
RE_VECTOR_P = re.compile(r'\\p\d+')
RE_TAG_PAIR = re.compile(r'}.*?\{')
RE_HEADER_LINE = re.compile(r'^\[.*\]$')
RE_NUMBER_TAG = re.compile(r'\\p\d+')


def split_tag_positions(st: str, pos_r: int) -> dict:
    """计算一个特效标签块内各类标签的启用状态。"""
    add_bold = None
    add_italic = None
    find_b = RE_FIND_B.findall(st)
    pos_b1 = st.rfind(find_b[-1]) if find_b else -1
    pos_b0 = max(st.rfind("\\b0"), st.rfind("\\b\\"), st.rfind("\\b}"))
    if max(pos_b1, pos_b0) > -1:
        if pos_b1 > max(pos_b0, pos_r):
            add_bold = "1"
        elif pos_b0 > max(pos_b1, pos_r):
            add_bold = "0"
    pos_i1 = st.rfind("\\i1")
    pos_i0 = max(st.rfind("\\i0"), st.rfind("\\i\\"), st.rfind("\\i}"))
    if max(pos_i1, pos_i0) > -1:
        if pos_r > max(pos_i1, pos_i0):
            add_italic = "r"
        elif pos_i1 > max(pos_r, pos_i0):
            add_italic = "1"
        elif pos_i0 > max(pos_i1, pos_r):
            add_italic = "0"
    return {"bold": add_bold, "italic": add_italic}


def ass_event_tags_split(ass_info: dict, change_only: bool = True) -> dict:
    """
    分析 Events 每行文本所用的字体与粗斜体情况。

    返回 {行索引: [{'Text', 'Fontname', 'Bold', 'Italic'}, ...]}
    """
    events = ass_info["Events"]
    lines = {}
    for i, event in enumerate(events):
        if event.get("Event") != "Dialogue":
            continue
        event_text = event["Text"]
        text_remain = ""
        if RE_VECTOR.search(event_text) is not None:
            for seg in RE_VECTOR.findall(event_text):
                vec_find = event_text.find(seg)
                text_remain += event_text[:vec_find]
                text_remain += RE_NUMBER_TAG.sub("", RE_TAG_PAIR.sub("}{", seg))
        elif RE_VECTOR_OPEN.search(event_text) is not None:
            event_text = RE_NUMBER_TAG.sub("", event_text[:RE_VECTOR_OPEN.search(event_text).span()[0]])
        if text_remain:
            event_text = text_remain

        event_font = ass_info["Styles"].get(event["Style"])
        if event_font is None:
            event_font = ass_info["Styles"].get(event["Style"].lstrip("*"))
        if event_font is None:
            if RE_EFFECT_DEL.sub("", event_text):
                raise AssParseError(f'未定义 行{i + 1} 所用样式"{event["Style"].lstrip("*")}"')
            continue

        last_font = event_font["Fontname"]
        last_italic = event_font["Italic"]
        last_bold = event_font["Bold"]
        split_text: list = []

        if RE_EFFECT.search(event_text) is not None:
            last_find = 0
            event_text2 = event_text
            for st in RE_ALL_TAGS.findall(event_text):
                if RE_IB_ON.search(st) is None:
                    continue
                st_find = last_find + event_text2.find(st)
                add_bold = last_bold
                add_italic = last_italic

                # \r 标签解析
                r_styles = RE_FIND_R.findall(st)
                r_font, r_bold, r_italic = last_font, last_bold, last_italic
                pos_r = -1
                if r_styles:
                    pos_r = st.rfind(r_styles[-1])
                    r_style = r_styles[-1].split("\\")[1].lstrip("r").rstrip("}")
                    if r_style in ass_info["Styles"]:
                        r_font = ass_info["Styles"][r_style]["Fontname"]
                        r_italic = ass_info["Styles"][r_style]["Italic"]
                        r_bold = ass_info["Styles"][r_style]["Bold"]
                    else:
                        # \r 未指定样式时回到行基准样式
                        r_font = event_font["Fontname"]
                        r_italic = event_font["Italic"]
                        r_bold = event_font["Bold"]

                flags = split_tag_positions(st, pos_r)
                pos_fn = st.rfind("\\fn")

                # \b 标签
                if flags["bold"] is not None:
                    if flags["bold"] == "r":
                        add_bold = r_bold
                    else:
                        add_bold = flags["bold"]
                # \i 标签
                if flags["italic"] is not None:
                    add_italic = r_italic if flags["italic"] == "r" else flags["italic"]

                # \fn 与 \r 标签
                if pos_fn > -1:
                    fn_tags = RE_FIND_FN.findall(st)
                    if fn_tags and pos_fn > pos_r:
                        fnn = fn_tags[-1].split("\\")[1].rstrip("}")[2:].lstrip("@")
                        if not fnn:
                            fnn = event_font["Fontname"]
                        elif ass_info["Subset"].get(fnn) is not None:
                            fnn = ass_info["Subset"][fnn]
                        if st_find > 0:
                            if not split_text:
                                split_text.append([event_text[:st_find], last_italic, last_bold, last_font])
                            else:
                                split_text[-1][0] = event_text[last_find:st_find]
                        split_text.append([event_text[st_find:], add_italic, add_bold, fnn])
                        last_font = fnn
                    elif pos_fn < pos_r:
                        if st_find > 0:
                            if not split_text:
                                split_text.append([event_text[:st_find], last_italic, last_bold, last_font])
                            else:
                                split_text[-1][0] = event_text[last_find:st_find]
                        last_font = r_font
                        split_text.append([event_text[st_find:], add_italic, add_bold, last_font])
                elif pos_r > -1:
                    if st_find > 0:
                        if not split_text:
                            split_text.append([event_text[:st_find], last_italic, last_bold, last_font])
                        else:
                            split_text[-1][0] = event_text[last_find:st_find]
                    last_font = r_font
                    split_text.append([event_text[st_find:], add_italic, add_bold, last_font])
                else:
                    if not split_text:
                        if st_find > 0:
                            split_text.append([event_text[:st_find], last_italic, last_bold, last_font])
                        split_text.append([event_text[st_find:], add_italic, add_bold, last_font])
                    else:
                        if st_find > 0:
                            split_text[-1][0] = event_text[last_find:st_find]
                        split_text.append([event_text[st_find:], add_italic, add_bold, last_font])

                last_find = st_find
                event_text2 = event_text[st_find:]
                last_bold = add_bold
                last_italic = add_italic

        if not split_text:
            split_text.append([event_text, last_italic, last_bold, last_font])

        lines[i] = [
            {"Text": seg[0], "Fontname": seg[3], "Bold": int(seg[2]), "Italic": int(seg[1])}
            for seg in split_text
        ]

    if change_only:
        return {k: v for k, v in lines.items() if len(v) > 1}
    return lines


# 兼容旧名称
_split_tag_positions = split_tag_positions
eventTagsSplit = ass_event_tags_split
