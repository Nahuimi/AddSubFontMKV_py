"""字体索引、名称回退、缓存与子集化辅助测试。"""

from __future__ import annotations

from asfmkv.fonts.cache import FontCache
from asfmkv.fonts.index import resolve_from_family, update_ass_font
from asfmkv.fonts.models import FontIndex


def test_subset_crc_has_single_implementation():
    """subset_crc 只在 utils.crc 实现，fonts.subsetter 直接复用同一函数。"""
    from asfmkv.fonts import subsetter
    from asfmkv.utils.crc import subset_crc

    assert subsetter.subset_crc is subset_crc
    assert subset_crc("abc", "Demo") == subset_crc("abc", "Demo")
    assert len(subset_crc("", "x")) >= 8


def test_font_index_has_no_dead_f_all_field():
    """f_all 曾只写不读、且在每次解析末尾被清空，已从模型中移除。"""
    assert "f_all" not in FontIndex.__dataclass_fields__
    info = FontIndex()
    assert info.get_by_index(3) is info.warning_font
    assert info.get_by_index(4) is None


def test_resolve_from_family_exact():
    family = {"Demo": {(0, 0): ["Demo Regular"], (0, 1): ["Demo Bold"], (1, 0): ["Demo Italic"]}}
    assert resolve_from_family(family, "Demo", 0, 1) == "Demo Bold"
    assert resolve_from_family(family, "Demo", 1, 0) == "Demo Italic"
    assert resolve_from_family(family, "Demo", 0, 0) == "Demo Regular"


def test_resolve_from_family_fallback_order():
    family = {"Demo": {(0, 0): ["Only"]}}
    assert resolve_from_family(family, "Demo", 1, 1) == "Only"
    assert resolve_from_family(family, "Unknown", 1, 1) == "Unknown"


def test_update_ass_font_merges_and_dedups():
    a = {("p", "0"): ["ab", "A", "B", ["f1"], [(0, 0)]]}
    b = {("p", "0"): ["bc", "B", "C", ["f2"], [(0, 1)]]}
    merged = update_ass_font(a, b)
    assert merged[("p", "0")][0] == "abc"
    assert set(merged[("p", "0")][3]) == {"f1", "f2"}
    assert set(merged[("p", "0")][4]) == {(0, 0), (0, 1)}


def test_update_ass_font_none_passthrough():
    assert update_ass_font(None, None) is None
    assert update_ass_font(None, {}) == {}


def test_font_index_get_by_index_and_find():
    info = FontIndex(font_name={"Arial": ["p", 0, {}, False]}, font_n_lower={"arial": "Arial"})
    assert info.get_by_index(0) is info.font_name
    assert info.get_by_index(1) is info.font_n_lower
    assert info.get_by_index(9) is None
    assert info.find("arial") == ["p", 0, {}, False]


def test_font_cache_roundtrip(tmp_path):
    cache = FontCache(str(tmp_path / "cache"))
    key = cache.dir_key(str(tmp_path))
    assert cache.load(key) == {}
    cache.save(key, {"?version": cache.version, "abc": {"0": ["n", 0, 0, {}, {}]}})
    assert cache.load(key)["abc"]["0"][0] == "n"
    cache.clear()
    assert cache.load(key) == {}


def test_font_cache_clear_keeps_foreign_files(tmp_path):
    """clear() 只清理 8 位十六进制 CRC 缓存文件，不能删除目录里的其他文件。"""
    root = tmp_path / "cache_keep"
    cache = FontCache(str(root))
    key = cache.dir_key(str(tmp_path))
    cache.save(key, {"?version": cache.version})
    foreign = root / "notes.txt"
    foreign.write_text("keep me", encoding="utf-8")
    cache.clear()
    assert not (root / key).exists()
    assert foreign.is_file()


def test_font_cache_save_is_atomic(tmp_path):
    root = tmp_path / "cache_atomic"
    cache = FontCache(str(root))
    key = cache.dir_key(str(tmp_path))
    cache.save(key, {"?version": cache.version, "x": 1})
    assert cache.load(key)["x"] == 1
    assert not list(root.glob("*.tmp"))


def test_font_cache_save_skips_gracefully_when_unwritable(tmp_path, monkeypatch):
    """缓存目录不可写（只读环境 / 受限账户）时只提示一次，不抛异常。"""
    import asfmkv.fonts.cache as cache_mod

    root = tmp_path / "cache_readonly"
    cache = FontCache(str(root))
    key = cache.dir_key(str(tmp_path))
    real_open = open

    def fake_open(file, *args, **kwargs):
        if str(file).startswith(str(root)):
            raise PermissionError(13, "Permission denied", str(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(cache_mod, "open", fake_open, raising=False)
    cache.save(key, {"?version": cache.version})   # 首次：提示并跳过
    cache.save(key, {"?version": cache.version})   # 再次：不应重复提示
    assert not (root / key).exists()
    assert not list(root.glob("*.tmp"))
    assert cache._warned is True


def _ansi_cmap_font():
    """构造一个只有 ANSI(GBK) cmap 的最小字体对象。"""
    from fontTools.ttLib import TTFont, newTable
    from fontTools.ttLib.tables._c_m_a_p import CmapSubtable

    font = TTFont()
    cmap_table = newTable("cmap")
    cmap_table.tableVersion = 0
    sub = CmapSubtable.newSubtable(4)
    sub.platformID, sub.platEncID, sub.language = 3, 2, 0
    sub.cmap = {0x41: "A", 0xB0A1: "uni4E00"}
    cmap_table.tables = [sub]
    font["cmap"] = cmap_table
    return font


def test_fix_ansi_cmap_rewrites_local_codes_to_unicode():
    from asfmkv.fonts.subsetter import fix_ansi_cmap

    font = _ansi_cmap_font()
    fix_ansi_cmap(font, {0x41: 0x41, 0xB0A1: 0x4E00})
    tables = font["cmap"].tables
    assert [(t.platformID, t.platEncID) for t in tables] == [(0, 3), (1, 0), (3, 1)]
    assert 0x4E00 in tables[0].cmap and 0x4E00 in tables[2].cmap
    assert 0x4E00 not in tables[1].cmap          # Mac Roman 子表只保留 ASCII
    assert all(0xB0A1 not in t.cmap for t in tables)
    font.close()


def test_fix_ansi_cmap_subtables_do_not_share_state():
    """三个子表必须各自持有独立 cmap，且 Mac Roman 子表只能保留 ASCII。"""
    from asfmkv.fonts.subsetter import fix_ansi_cmap

    font = _ansi_cmap_font()
    fix_ansi_cmap(font, {0x41: 0x41, 0xB0A1: 0x4E00})
    tables = font["cmap"].tables
    assert len({id(t.cmap) for t in tables}) == 3
    assert all(k < 128 for k in tables[1].cmap)
    font.close()
