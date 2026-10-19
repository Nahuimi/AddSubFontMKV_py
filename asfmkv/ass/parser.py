"""ASS/SSA 解析：把字幕文件读取为结构化字典。"""

from __future__ import annotations

from os import path

from ..core.errors import AssParseError
from ..utils.encoding import detect_encoding
from .embedded import decode_uue
from .models import new_ass_info
from .tags import RE_HEADER_LINE


def ass_analyse(ass_path: str, keep_embedded: bool = False) -> dict:
    """
    解析 ASS/SSA 文件为结构化字典。

    返回结构（与原 assAnalyseV2 保持一致）::

        {
            Lines:    {标签名: 行号},
            Info:     {字段: 内容},
            Styles:   {样式名: {字段: 内容}},
            Events:   [{字段: 内容}],
            Fonts:    {附件名: bytes},
            Graphics: {附件名: bytes},
            Garbage:  {字段: 内容},
            Subset:   {字体名: 原始名},
        }
    """
    ass_info = new_ass_info()
    tag_lines = ass_info["Lines"]

    encoding = detect_encoding(ass_path)

    with open(ass_path, mode="r", encoding=encoding) as fh:
        print(f'"{path.basename(ass_path)}" - {encoding.upper()}')
        ass_lines = fh.readlines()

    def read_styles_events(tag_line: int) -> list:
        if tag_line == -1:
            return []
        rows = []
        is_event = ass_lines[tag_line].strip("[]\n") == "Events"
        offset = 1
        try:
            parts = ass_lines[tag_line + offset].split(":")
            while len(parts) == 1:
                offset += 1
                parts = ass_lines[tag_line + offset].split(":")
        except IndexError:
            # 段落头位于文件末尾 / 没有 Format 行
            raise AssParseError(f'ASS/SSA格式错误 - 缺少Format行 - "{path.basename(ass_path)}"') from None
        line_format = [s.strip(" \n") for s in ":".join(parts[1:]).strip(" ").split(",")]
        if is_event and "Text" not in line_format:
            raise AssParseError(f'ASS/SSA格式错误 - 缺少Format行 - "{path.basename(ass_path)}"')
        # 事件行最后一个字段是 Text，其内容允许包含逗号（字幕文本原本就常带逗号）；
        # 只有 Text 位于 Format 末尾时才能无歧义地把后续逗号全部并入该字段。
        event_text_last = is_event and line_format[-1] == "Text"

        for i in range(tag_line + offset + 1, len(ass_lines)):
            line = ass_lines[i].split(":")
            if len(line) == 1:
                if ass_lines[i].strip(" ")[:1] == "[":
                    break
                continue
            content = ":".join(line[1:]).strip(" ")
            if event_text_last:
                # 只按结构字段切分，剩余部分（Text）原样保留，避免误报“字段数多于Format定义”
                line = content.split(",", len(line_format) - 1)
            else:
                line = content.split(",")
                if len(line) > len(line_format):
                    raise AssParseError(f'ASS/SSA格式错误 - 字段数多于Format定义 - 位于行{i + 1} 文件"{path.basename(ass_path)}"')
            row = {}
            if is_event:
                row["Event"] = ass_lines[i].split(":")[0]
            for j, field in enumerate(line):
                if is_event and line_format[j] == "Text":
                    # Text 内容原样保留（仅去掉行尾换行），不破坏字幕中的逗号与空格
                    row[line_format[j]] = ",".join(line[j:]).strip(" \t\r\n")
                    break
                row[line_format[j]] = field.strip(" \n")
            expected = len(line_format) + (1 if is_event else 0)
            if len(row) != expected:
                raise AssParseError(f'ASS/SSA格式错误 - 缺少逗号分隔 - 位于行{i + 1} 文件"{path.basename(ass_path)}"')
            rows.append(row)
        return rows

    def read_info(tag_line: int) -> dict:
        if tag_line == -1:
            return {}
        result = {}
        for i in range(tag_line + 1, len(ass_lines)):
            line = ass_lines[i].split(":")
            if ass_lines[i].lstrip(" ").startswith(";"):
                if "font subset" in ass_lines[i].lower() and len(line) > 1:
                    name_parts = [s.strip(" \n") for s in ":".join(line[1:]).split("-")]
                    ass_info["Subset"][name_parts[0]] = "-".join(name_parts[1:])
                continue
            if len(line) == 1:
                if ass_lines[i].strip(" ")[:1] == "[":
                    break
                continue
            result[line[0]] = ":".join(line[1:]).strip(" \n")
        return result

    def read_embedded(tag_line: int) -> dict:
        if tag_line == -1:
            return {}
        result = {}
        i = tag_line
        # 旧实现的 while 边界差一位，段落位于文件末尾时 ass_lines[i] 会 IndexError
        while i + 1 < len(ass_lines):
            i += 1
            if ass_lines[i].lstrip(" ")[:8].lower() in ("fontname", "filename"):
                filename = ass_lines[i].lstrip(" ")[8:].strip(": \n")
                content = []
                i += 1
                while (i < len(ass_lines)
                       and ass_lines[i].lstrip(" ")[:8] not in ("fontname", "filename")
                       and RE_HEADER_LINE.match(ass_lines[i].strip(" ")) is None):
                    if ass_lines[i].strip(" \n"):
                        content.append(ass_lines[i].strip(" \n"))
                    i += 1
                result[filename] = decode_uue(content)
            if i + 1 >= len(ass_lines):
                break
            if ass_lines[i].strip(" ")[:1] == "[":
                break
            if ass_lines[i].lstrip(" ")[:8] in ("fontname", "filename"):
                i -= 1
        return result

    for i in range(len(ass_lines)):
        line = ass_lines[i].strip(" \n")
        if line and line[0] == "[" and line[-1] == "]":
            name = line.strip("[]")
            parts = name.split(" ")
            tag_lines[parts[-1] if len(parts) > 1 else name] = i

    ass_info["Info"] = read_info(tag_lines["Info"])
    ass_info["Garbage"] = read_info(tag_lines["Garbage"])
    if tag_lines["Garbage"] > -1:
        ass_info["Garbage"]["#GarbageWholeTag#"] = ass_lines[tag_lines["Garbage"]].strip(" []")
    styles = read_styles_events(tag_lines["Styles"])
    ass_info["Styles"] = {row.pop("Name"): row for row in styles}
    ass_info["Events"] = read_styles_events(tag_lines["Events"])
    if keep_embedded:
        ass_info["Fonts"] = read_embedded(tag_lines["Fonts"])
        ass_info["Graphics"] = read_embedded(tag_lines["Graphics"])
    return ass_info


# 兼容旧名称
assAnalyseV2 = ass_analyse
