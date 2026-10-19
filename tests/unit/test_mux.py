"""封装公共逻辑与 FFmpeg 参数构造测试。"""

from __future__ import annotations

from os import path

from asfmkv.mux.base import resolve_mux_outfile, subtitle_note
from asfmkv.mux.ffmpeg import build_ffmpeg_args
from asfmkv.mux.models import MuxJob


def test_subtitle_note_extracts_language_after_media_name():
    assert subtitle_note("01.zh.ass", "01") == ".zh"
    assert subtitle_note("/x/01.sc.ass", "01") == ".sc"


def test_subtitle_note_strips_subset_marker():
    assert subtitle_note("ep1.sc.subset.ass", "ep1") == ".sc"
    assert subtitle_note("ep1.subset.ass", "ep1") == ""


def test_subtitle_note_without_subset_marker_keeps_last_char():
    """未子集化的字幕没有 .subset 标记，不能像旧实现那样吃掉最后一个字符。"""
    assert subtitle_note("movie.chs&cht.ass", "movie") == ".chs&cht"
    assert subtitle_note("01.mkv", "01") == ""


def test_subtitle_note_when_media_name_absent():
    """字幕名不含媒体名（CLI 手工指定）时回退为整个文件名，而不是随机截断。"""
    assert subtitle_note("ep1.zh.ass", "a-much-longer-media-name.mkv") == "ep1.zh"
    assert subtitle_note("ep1.zh.subset.ass", "a-much-longer-media-name") == "ep1.zh"


def test_resolve_mux_outfile_appends_counter(tmp_path):
    src = tmp_path / "ep1.mkv"
    src.write_text("x", encoding="utf-8")
    first = resolve_mux_outfile(str(src), "", False)
    assert path.basename(first) == "ep1.muxed.mkv"
    path.join(str(tmp_path), "ep1.muxed.mkv")
    (tmp_path / "ep1.muxed.mkv").write_text("x", encoding="utf-8")
    second = resolve_mux_outfile(str(src), "", False)
    assert path.basename(second) == "ep1.muxed#1.mkv"


def test_ffmpeg_attachment_mime_supports_font_collections():
    """.ttc/.otc 也应能作为附件封装，而旧实现直接 KeyError。"""
    job = MuxJob(file="movie.mkv", make_mks=True, font_paths=["Font.TTC", "Other.otf"])
    args = build_ffmpeg_args(job)
    assert "mimetype=font/collection" in args
    assert "mimetype=font/otf" in args
    assert args.count("-attach") == 2


def test_ffmpeg_attachment_unknown_ext_has_no_mimetype():
    job = MuxJob(file="movie.mkv", make_mks=True, font_paths=["weird.fnt"])
    args = build_ffmpeg_args(job)
    assert "-attach" in args
    assert not any(str(a).startswith("mimetype=") for a in args)
