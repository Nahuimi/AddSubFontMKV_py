"""ASS/SSA 写回：把结构化字典输出为字幕文件。"""

from __future__ import annotations

from os import path

from .embedded import encode_uue


def ass_file_write(file_path: str, ass_info: dict, subset_recover: bool = True, keep_garbage: bool = True,
                   keep_embedded: bool = True, ignore_exists: bool = False, text_encoding: str = "utf-8-sig") -> None:
    """将 ASS 信息字典写回文件。"""
    if not ignore_exists and path.isfile(file_path):
        raise FileExistsError()

    lines = []

    def write_subset() -> None:
        for key, value in ass_info["Subset"].items():
            lines.append(f"; Font Subset: {key} - {value}\n")

    if ass_info["Info"]:
        lines.append("[Script Info]\n")
        if not subset_recover and ass_info["Subset"]:
            write_subset()
        for key, value in ass_info["Info"].items():
            lines.append(f"{key}: {value}\n")
        lines.append("\n")
    elif not subset_recover and ass_info["Subset"]:
        lines.append("[Script Info]\n")
        write_subset()
        lines.append("\n")

    if keep_garbage and ass_info["Garbage"]:
        lines.append(f"[{ass_info['Garbage']['#GarbageWholeTag#']}]\n")
        for key, value in ass_info["Garbage"].items():
            lines.append(f"{key}: {value}\n")
        lines.append("\n")

    if ass_info["Styles"]:
        is_ssa = path.splitext(file_path)[1][1:].lower() == "ssa"
        lines.append("[V4 Styles]\n" if is_ssa else "[V4+ Styles]\n")
        lines.append("Format: Name")
        for field in next(iter(ass_info["Styles"].values())).keys():
            lines[-1] += f", {field}"
        lines[-1] += "\n"
        for style_name, style in ass_info["Styles"].items():
            lines.append(f"Style: {style_name}")
            for field, value in style.items():
                if subset_recover and field == "Fontname":
                    value = ass_info["Subset"].get(value, value)
                lines[-1] += f",{value}"
            lines[-1] += "\n"
        lines.append("\n")

    if ass_info["Events"]:
        lines.append("[Events]\n")
        lines.append("Format: ")
        for field in list(ass_info["Events"][0].keys())[1:]:
            lines[-1] += f"{field}, "
        lines[-1] = lines[-1].rstrip(", ") + "\n"
        for event in ass_info["Events"]:
            lines.append(f"{event['Event']}: ")
            for key, value in event.items():
                if key != "Event":
                    lines[-1] += value + ","
            lines[-1] = lines[-1][:-1] + "\n"
        lines.append("\n")

    if keep_embedded and ass_info["Fonts"]:
        lines.append("[Fonts]\n")
        for name, content in ass_info["Fonts"].items():
            lines.extend(encode_uue(content, name, True) + ["\n"])
        lines.append("\n")

    if keep_embedded and ass_info["Graphics"]:
        lines.append("[Graphics]\n")
        for name, content in ass_info["Graphics"].items():
            lines.extend(encode_uue(content, name, False) + ["\n"])
        lines.append("\n")

    with open(file_path, mode="w", encoding=text_encoding) as fh:
        fh.writelines(lines)


# 兼容旧名称
assFileWrite = ass_file_write
