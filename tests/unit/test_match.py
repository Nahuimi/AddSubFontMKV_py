"""字幕扫描与匹配测试。"""

from __future__ import annotations

from asfmkv.match.subtitles import get_sub_name, get_subtitles, most_common


def _touch(p, name):
    target = p / name
    target.write_text("x", encoding="utf-8")
    return str(target)


def test_get_subtitles_skips_orphan_idx(tmp_path):
    """没有同名 .sub 的 .idx 不构成可封装的字幕轨。"""
    media = _touch(tmp_path, "01.mkv")
    _touch(tmp_path, "01.idx")
    _touch(tmp_path, "01.zh.ass")
    result = get_subtitles(str(tmp_path), [["01", media]], subext=("idx", "ass"), match_strict=True)
    assert result[media] == [str(tmp_path / "01.zh.ass")]


def test_get_subtitles_keeps_idx_with_sub_sibling(tmp_path):
    """存在同名 .sub 时 .idx 才是有效字幕。"""
    media = _touch(tmp_path, "01.mkv")
    _touch(tmp_path, "01.idx")
    _touch(tmp_path, "01.sub")
    result = get_subtitles(str(tmp_path), [["01", media]], subext=("idx",), match_strict=True)
    assert result[media] == [str(tmp_path / "01.idx")]


def test_get_subtitles_without_media_lists_all(tmp_path):
    _touch(tmp_path, "a.ass")
    _touch(tmp_path, "b.ass")
    result = get_subtitles(str(tmp_path), [], subext=("ass",))
    assert len(result["none"]) == 2


def test_get_sub_name_returns_tail_after_media_name():
    assert get_sub_name("/x/ep1.mkv", "/x/ep1.zh.ass") == (str("/x/ep1.zh.ass"), ".zh")


def test_most_common_is_stable_on_ties():
    assert most_common([]) == 0
    assert most_common(["a", "b", "b", "a"]) == "a"


def test_rename_preview_does_not_leak_previous_annotation(tmp_path, monkeypatch):
    """上一条字幕算出的注释曾泄漏到没有注释的下一条。"""
    from asfmkv.match import rename

    monkeypatch.setattr(rename, "clear_screen", lambda: None)
    subs = [_touch(tmp_path, "a.chs.ass"), _touch(tmp_path, "bchta.ass")]
    media = ("ep", str(tmp_path / "ep.mkv"))
    preview, _ = rename.rename_preview({media: subs}, s_start_a=5, s_end_a="")
    assert preview[0][1] == "ep.chs.ass"
    assert preview[1][1] == "ep.ass"          # 修复前会继承 ".chs"


def test_rename_preview_short_name_does_not_crash(tmp_path, monkeypatch):
    """反向文件名比推断位置短时曾抛 IndexError。"""
    from asfmkv.match import rename

    monkeypatch.setattr(rename, "clear_screen", lambda: None)
    subs = [_touch(tmp_path, "a.ass")]
    media = ("ep", str(tmp_path / "ep.mkv"))
    preview, _ = rename.rename_preview({media: subs}, s_start_a=9, s_end_a=".")
    assert preview[0][1].startswith("ep")


def test_name_position_handles_uniform_names():
    """名字完全一致/极短时不能把 name1[0] 当结束字符，也不应崩溃。"""
    from asfmkv.match.subtitles import name_position

    start, end = name_position(["ep", "ep"])
    assert isinstance(start, int)
    assert end in (0, "")
