"""平台抽象：控制台、注册表、路径。"""

from .shell import Shell
from .paths import (
    APP_NAME,
    application_dir,
    cache_dir,
    cache_dir_or_none,
    default_ini_path,
    is_frozen,
)
