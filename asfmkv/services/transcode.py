"""服务：字幕编码检测与批量转换为 UTF-8-BOM。"""

from __future__ import annotations

import os
from os import path

from ..core.console import Ansi, colorize
from ..utils.encoding import detect_encoding, preferred_encoding
from ..utils.fs import ensure_directory, get_file_list


def detect_transcode(src: str, dst: str) -> None:
    """检测编码并将字幕转换为 UTF-8-BOM。"""
    encoding = detect_encoding(src, default=preferred_encoding())
    if encoding.lower() == "utf-8-sig":
        print(colorize("[Already UTF-8-BOM] ", Ansi.YELLOW) + colorize(f'"{path.basename(src)}"', Ansi.YELLOW))
        return
    with open(src, mode="r", encoding=encoding) as fh:
        content = fh.read()
    with open(dst, mode="w", encoding="utf-8-sig") as fh:
        fh.write(content)
    print(colorize(f"[{encoding.upper()} >>> UTF-8-BOM] ", Ansi.YELLOW) + colorize(f'"{path.basename(src)}"', Ansi.YELLOW))


def transcode_batch(s_path: str, *, s_subdir: bool = False) -> str:
    """批量转换字幕，返回输出目录（为空表示失败）。"""
    out_path = path.join(s_path, "UTF8-Subtitles")
    if not ensure_directory(out_path):
        return ""
    if path.isdir(s_path):
        for f in get_file_list(s_path, ["ass", "ssa", "srt"], s_subdir):
            try:
                detect_transcode(f[1], path.join(out_path, ".utf8".join(path.splitext(path.basename(f)))))
            except Exception as exc:
                print(colorize(str(exc), Ansi.RED))
    else:
        try:
            detect_transcode(s_path, path.join(out_path, ".utf8".join(path.splitext(path.basename(s_path)))))
        except Exception as exc:
            print(colorize(str(exc), Ansi.RED))
    if not os.listdir(out_path):
        try:
            os.rmdir(out_path)
        except OSError as exc:
            print(colorize(str(exc), Ansi.RED))
        return ""
    print("输出文件夹: " + colorize(f'"{out_path}"', Ansi.YELLOW))
    return out_path


# 兼容旧名称
tc_detect_transcode = detect_transcode
TCDetect_Trans = detect_transcode
