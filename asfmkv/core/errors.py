"""ASFMKV：异常体系。"""

from __future__ import annotations


class AsfmkvError(Exception):
    """ASFMKV 所有自定义异常的基类。"""


class ConfigError(AsfmkvError):
    """配置读取或校验失败。"""


class FontError(AsfmkvError):
    """字体读取、索引或子集化相关错误。"""


class AssParseError(AsfmkvError):
    """ASS/SSA 解析或写回失败。"""


class SubsetError(FontError):
    """字体子集化失败。"""


class MuxError(AsfmkvError):
    """封装（mkvmerge/ffmpeg/内嵌）失败。"""


class DependencyError(AsfmkvError):
    """缺少外部依赖（mkvmerge/ffmpeg 等）。"""


# 兼容旧名称
AssError = AssParseError