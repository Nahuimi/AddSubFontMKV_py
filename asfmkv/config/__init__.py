"""配置模型、旧 INI 兼容层与加载器。"""

from .model import AppConfig, DEFAULTS, normalize_extlist, normalize_path_list
from .loader import load_config
from ..platform.paths import default_ini_path
from .legacy_ini import read_legacy_ini