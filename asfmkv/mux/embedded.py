"""ASS/SSA 内嵌字体方式（不生成独立媒体文件）。"""

from __future__ import annotations

from .models import MuxJob, MuxResult


def mux_embedded(job: MuxJob) -> MuxResult:
    """内嵌方式不执行外部封装，字体在字幕写回阶段被嵌入。"""
    return MuxResult(0, job.out_file)
