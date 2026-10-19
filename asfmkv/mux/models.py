"""封装任务与结果模型。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MuxJob:
    """一次封装任务的全部输入。"""

    file: str = ""
    out_file: str = ""
    ass_langs: dict = field(default_factory=dict)
    ass_paths: list = field(default_factory=list)
    font_paths: list = field(default_factory=list)
    force_sub_track: str = "?"
    make_mks: bool = False


@dataclass
class MuxResult:
    """封装结果：退出码与最终输出路径。"""

    return_code: int = 0
    out_file: str = ""

    @property
    def ok(self) -> bool:
        return self.return_code <= 1
