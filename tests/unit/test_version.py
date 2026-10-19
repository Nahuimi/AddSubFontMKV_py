"""版本号来源：源码默认值，以及发布工作流生成的 ``asfmkv/_version.py`` 覆盖。"""

from __future__ import annotations

import importlib
import sys
import types


def test_app_version_is_non_empty_string():
    import asfmkv

    assert isinstance(asfmkv.APP_VERSION, str)
    assert asfmkv.APP_VERSION.strip()
    assert asfmkv.__version__ == asfmkv.APP_VERSION


def test_generated_version_module_overrides_default(monkeypatch):
    """模拟打包前生成 asfmkv/_version.py：导入时应优先使用其中的版本号。"""
    import asfmkv

    fake = types.ModuleType("asfmkv._version")
    fake.APP_VERSION = "v9.9.9-generated"
    monkeypatch.setitem(sys.modules, "asfmkv._version", fake)
    try:
        assert importlib.reload(asfmkv).APP_VERSION == "v9.9.9-generated"
    finally:
        monkeypatch.undo()
        # 恢复成正常来源，避免影响其它用例
        reloaded = importlib.reload(asfmkv)
        assert reloaded.APP_VERSION != "v9.9.9-generated"
