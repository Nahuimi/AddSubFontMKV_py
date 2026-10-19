"""配置加载与旧 INI 兼容性测试。"""

from __future__ import annotations

import os

from asfmkv.config import AppConfig, load_config, read_legacy_ini
from asfmkv.config.model import normalize_extlist, normalize_path_list


def test_defaults_are_immutable_derivable():
    cfg = load_config(ini_path=".nonexistent.ini")
    assert isinstance(cfg, AppConfig)
    assert cfg.extlist == ("mkv", "mp4", "mts", "mpg", "flv", "mpeg", "m2ts", "avi",
                           "webm", "rm", "rmvb", "mov", "mk3d", "vob")
    changed = cfg.with_overrides(notfont=True)
    assert changed.notfont is True
    assert cfg.notfont is False                      # 原对象不被修改
    assert changed is not cfg


def test_extlist_normalization():
    assert normalize_extlist("MKV; .Mp4 ; ;Avi") == ("mkv", "mp4", "avi")
    assert normalize_path_list("a?b??c") == ("a", "b", "c")


def test_legacy_ini_roundtrip(tmp_path):
    ini = tmp_path / "ASFMKVpy.ini"
    ini.write_text("[settings]\nusingFF=1\nnotfont=1\nmatchStrict=0\nextlist=mkv,mp4\n"
                   "fontin=D:\\Fonts\n", encoding="utf-8")
    cfg = load_config(ini_path=str(ini))
    assert cfg.using_ff is True
    assert cfg.notfont is True
    assert cfg.match_strict is False
    assert cfg.extlist == ("mkv", "mp4")


def test_legacy_ini_gbk_encoding(tmp_path):
    """旧版中文 Windows 常以 GBK 保存 INI，旧实现会抛未捕获的 UnicodeDecodeError。"""
    ini = tmp_path / "ASFMKVpy.ini"
    ini.write_bytes("[settings]\nfontin=D:\\字体?E:\\字体2\nsubl_local=zh_CN\n".encode("gbk"))
    parsed = read_legacy_ini(str(ini))
    assert parsed["subl_local"] == "zh_CN"
    assert "D:\\字体" in parsed["fontin"]


def test_legacy_ini_undecodable_returns_empty(tmp_path):
    ini = tmp_path / "ASFMKVpy.ini"
    ini.write_bytes(b"\xff\xfe\x00\x00[settings]\n\x81\x00")
    assert read_legacy_ini(str(ini)) == {}


def test_missing_ini_keeps_defaults(tmp_path):
    cfg = load_config(ini_path=str(tmp_path / "absent.ini"))
    assert cfg.fontload is True
    assert read_legacy_ini(str(tmp_path / "absent.ini")) == {}


def test_packaged_default_ini_path(tmp_path, monkeypatch):
    """打包（Nuitka onefile）后默认 ini 应落在 exe 同目录，而不是解包临时目录。"""
    from asfmkv.platform import paths

    exe = tmp_path / "ASFMKV.exe"
    exe.write_bytes(b"")
    monkeypatch.setattr(paths, "__compiled__",
                        type("Compiled", (), {"containing_dir": str(tmp_path)}), raising=False)
    monkeypatch.setattr(paths.sys, "argv", [str(exe)])

    assert paths.is_frozen() is True
    assert paths.application_dir() == str(tmp_path)
    assert paths.default_ini_path() == str(tmp_path / "ASFMKVpy.ini")


def test_source_default_ini_path():
    """源码运行时默认 ini 指向项目根目录。"""
    from asfmkv.platform import paths

    assert paths.is_frozen() is False
    assert paths.default_ini_path() == os.path.join(paths.application_dir(), "ASFMKVpy.ini")
