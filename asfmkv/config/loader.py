"""配置加载：默认值 < 旧 INI < 调用方覆盖参数（含 CLI）。"""

from __future__ import annotations

from os import path
from typing import Optional

from ..platform.paths import default_ini_path
from .legacy_ini import read_legacy_ini
from .model import AppConfig, DEFAULTS, normalize_extlist, normalize_path_list


def _coerce(key: str, value) -> object:
    """把原始值转换为 AppConfig 期望的类型。"""
    if key == "extlist":
        return normalize_extlist(value)
    if key == "fontin":
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split("\n") if part.strip())
        return normalize_path_list(value)
    if key == "subext":
        if isinstance(value, str):
            value = [s for s in value.split(",") if s.strip()]
        return tuple(value)
    return value


def load_config(ini_path: Optional[str] = None, overrides: Optional[dict] = None) -> AppConfig:
    """
    载入配置。

    :param ini_path: 旧 ASFMKVpy.ini 路径；None 时使用程序目录下的默认路径；不存在则跳过
    :param overrides: 最高优先级覆盖（例如 CLI 参数），键为 AppConfig 字段名
    """
    values = dict(DEFAULTS)
    legacy = read_legacy_ini(path.abspath(ini_path or default_ini_path()))
    values.update({k: v for k, v in legacy.items() if k in values})
    values.update({k: v for k, v in (overrides or {}).items() if k in values and v is not None})

    typed = {key: _coerce(key, value) for key, value in values.items()}
    config = AppConfig(
        **{key: value for key, value in typed.items() if key in AppConfig.__dataclass_fields__}
    )
    # o_fontload 开启时 fontload 必须为真
    if config.o_fontload and not config.fontload:
        config = config.with_overrides(fontload=True)
    return config