"""子进程封装：一律使用参数列表，禁止 shell 字符串拼接。"""

from __future__ import annotations

import subprocess
from typing import Optional, Sequence


def run(args: Sequence[str], *, encoding: str = "utf-8", capture: bool = True,
        timeout: Optional[float] = None) -> subprocess.CompletedProcess:
    """
    运行外部命令。

    可执行文件缺失或不可执行时返回 ``returncode=127``，不抛异常，
    便于调用方按返回值判断外部工具可用性。

    :param args: 参数列表（例如 ["mkvmerge", "-V"]）
    :param capture: 是否捕获输出
    """
    argv = list(args)
    try:
        return subprocess.run(
            argv,
            check=False,
            capture_output=capture,
            text=True,
            encoding=encoding,
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(argv, 127, stdout="", stderr=f"{argv[0]}: command not found")
    except PermissionError:
        return subprocess.CompletedProcess(argv, 126, stdout="", stderr=f"{argv[0]}: permission denied")


def run_to_console(args: Sequence[str]) -> int:
    """运行外部命令并让其直接输出到当前控制台，返回退出码。"""
    return subprocess.run(list(args), check=False).returncode