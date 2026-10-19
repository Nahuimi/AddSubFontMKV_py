"""服务层参数映射与输出目录测试。"""

from __future__ import annotations

import importlib
from os import path


def test_collect_ass_fonts_accepts_expected_signature(ass_file, config):
    """collect_ass_fonts 已不再接受未使用的 out 参数。"""
    import inspect

    from asfmkv.fonts.models import FontIndex
    from asfmkv.services.list_fonts import collect_ass_fonts

    params = inspect.signature(collect_ass_fonts).parameters
    assert list(params) == ["target", "font_info", "config"]

    cfg = config.with_overrides(no_request_font=True, fontload=False)
    ass_font, font_dir = collect_ass_fonts(ass_file, FontIndex(), cfg)
    assert isinstance(ass_font, dict)
    assert font_dir.endswith("Fonts")

def test_load_fonts_does_not_map_priority_to_overwrite(config, monkeypatch):
    """f_priority 曾按位置被传成 progress_fonts 的 overwrite，导致重复字体检测失效。"""
    load_fonts_module = importlib.import_module("asfmkv.services.load_fonts")

    captured = {}

    def fake_progress(fl, font_info=None, *args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return font_info

    monkeypatch.setattr(load_fonts_module, "progress_fonts", fake_progress)
    monkeypatch.setattr(load_fonts_module, "get_font_file_list", lambda dirs, noreg=True: [])

    cfg = config.with_overrides(f_priority=True)
    load_fonts_module.load_fonts(cfg)

    assert captured["args"] == ()
    assert "overwrite" not in captured["kwargs"]
    assert captured["kwargs"]["using_cache"] is True


def test_run_pipeline_creates_relative_output_dirs(config, monkeypatch, tmp_path):
    """相对/多级输出目录以前会被静默丢弃，现在应被创建。"""
    from asfmkv.services import subset_mux

    media = tmp_path / "ep1.mkv"
    media.write_text("x", encoding="utf-8")
    subs = tmp_path / "ep1.ass"
    subs.write_text("[Script Info]\nTitle: x\n\n[Events]\nFormat: Layer, Text\n", encoding="utf-8-sig")

    relative_out = path.join("nested", "ass")
    monkeypatch.chdir(tmp_path)
    cfg = config.with_overrides(notfont=True)  # 仅测试目录解析，不触发字体/封装

    new_ass, new_font, rc = subset_mux.run_pipeline(
        None, [str(subs)], cfg, mux=False, out_dir=[relative_out, "", ""], vpath=str(media))

    assert path.isdir(tmp_path / relative_out)
    assert rc == -1


def test_cmd_subset_autoloads_fonts_from_subtitle_dir(tmp_path, monkeypatch):
    """CLI subset 曾漏掉“从字幕所在目录补载字体”，list-fonts / 交互菜单都有这一步。"""
    from types import SimpleNamespace

    from asfmkv import cli

    subs = tmp_path / "ep1.ass"
    subs.write_text("[Script Info]\n", encoding="utf-8-sig")
    called = {}

    monkeypatch.setattr(cli, "load_fonts", lambda config: object())
    monkeypatch.setattr(cli, "make_font_loader", lambda config: None)

    def fake_temple(directory, font_info, *, s_fontload=False):
        called.setdefault("dirs", []).append(directory)
        return font_info

    monkeypatch.setattr(cli, "temple_font_load", fake_temple)
    monkeypatch.setattr(cli, "run_pipeline", lambda *a, **k: ([], {}, -1))

    cfg = SimpleNamespace(fontload=True, s_fontload=False, notfont=False)
    args = SimpleNamespace(path=str(subs), subtitle=[], out_ass=None, out_font=None,
                           out_media=None, mux=False, ffmpeg=False, embed=False, mks=False,
                           pattern="")

    assert cli.cmd_subset(cfg, args) == 0
    assert called["dirs"] == [str(tmp_path)]

    called.clear()
    cfg.fontload = False
    assert cli.cmd_subset(cfg, args) == 0
    assert called == {}


def _prepare_mks_subset(tmp_path, monkeypatch, sub_names, media_names=(), pattern=""):
    """准备 cmd_subset --mks 的假流水线与假封装调用，返回调用记录。"""
    from types import SimpleNamespace

    from asfmkv import cli

    for name in sub_names:
        (tmp_path / name).write_text("[Script Info]\n", encoding="utf-8-sig")
    for name in media_names:
        (tmp_path / name).write_text("x", encoding="utf-8")

    calls = {"pipeline": [], "mux": []}
    fake_font = str(tmp_path / "fakefonts" / "Arial.1234.ttf")

    monkeypatch.setattr(cli, "load_fonts", lambda config: object())
    monkeypatch.setattr(cli, "make_font_loader", lambda config: None)
    monkeypatch.setattr(cli, "temple_font_load", lambda d, fi, *, s_fontload=False: fi)

    def fake_pipeline(font_info, ass_paths, config, **kwargs):
        calls["pipeline"].append(sorted(ass_paths))
        return [str(tmp_path / "out.subset.ass")], {("Arial", 0, 0): [fake_font, "Arial.1234"]}, -1

    def fake_mux(job, **kwargs):
        calls["mux"].append({"file": job.file, "out": job.out_file, "mks": job.make_mks,
                             "ass": list(job.ass_paths), "fonts": list(job.font_paths),
                             "honor": kwargs.get("honor_outfile")})
        return SimpleNamespace(return_code=0, out_file=job.out_file)

    monkeypatch.setattr(cli, "run_pipeline", fake_pipeline)
    monkeypatch.setattr(cli, "mux_with_mkvmerge", fake_mux)

    cfg = SimpleNamespace(fontload=False, s_fontload=False, notfont=False,
                          subext=("ass", "ssa"), match_strict=True, s_subdir=False,
                          extlist=("mkv",), v_subdir=False)
    args = SimpleNamespace(path=str(tmp_path), subtitle=[], out_ass=None, out_font=None,
                           out_media=str(tmp_path / "mks"), mux=False, ffmpeg=False,
                           embed=False, mks=True, pattern=pattern)
    return cfg, args, calls


def test_cmd_subset_mks_batches_each_subtitle_without_media(tmp_path, monkeypatch):
    """目录里没有视频时，--mks 为每条字幕各生成一个 mks。"""
    from asfmkv import cli

    cfg, args, calls = _prepare_mks_subset(
        tmp_path, monkeypatch, ["ep1.chs.ass", "ep1.cht.ass"])

    assert cli.cmd_subset(cfg, args) == 0
    assert len(calls["pipeline"]) == 2
    assert all(len(group) == 1 for group in calls["pipeline"])
    assert sorted(call["out"] for call in calls["mux"]) == [
        str(tmp_path / "mks" / "ep1.chs.mks"),
        str(tmp_path / "mks" / "ep1.cht.mks"),
    ]
    for call in calls["mux"]:
        assert call["mks"] is True and call["honor"] is True
        assert call["fonts"] and call["ass"]


def test_cmd_subset_mks_groups_subtitles_by_media(tmp_path, monkeypatch):
    """目录里有视频时，同一视频的多条字幕合并进一个 mks。"""
    from asfmkv import cli

    cfg, args, calls = _prepare_mks_subset(
        tmp_path, monkeypatch, ["ep1.chs.ass", "ep1.cht.ass"], media_names=["ep1.mkv"])

    assert cli.cmd_subset(cfg, args) == 0
    assert calls["pipeline"] == [[str(tmp_path / "ep1.chs.ass"), str(tmp_path / "ep1.cht.ass")]]
    assert len(calls["mux"]) == 1
    # mks 不打包视频，媒体路径只是占位（放在可写的工作目录里）
    assert calls["mux"][0]["file"] == str(tmp_path / "mks" / "ep1.mkv")
    assert calls["mux"][0]["out"] == str(tmp_path / "mks" / "ep1.mks")


def test_cmd_subset_mks_pattern_groups_episode_subtitles(tmp_path, monkeypatch):
    """--pattern 按“视频文件名规则”把同一集的多条字幕合并进一个 mks。"""
    from asfmkv import cli

    sub_names = ["[Test][01][1080p].chs.ass", "[Test][01][1080p].cht.ass", "[Test][02][1080p].chs.ass"]
    cfg, args, calls = _prepare_mks_subset(
        tmp_path, monkeypatch, sub_names, pattern="[Test][*][1080p]")

    assert cli.cmd_subset(cfg, args) == 0
    assert len(calls["pipeline"]) == 2
    assert sorted(call["out"] for call in calls["mux"]) == [
        str(tmp_path / "mks" / "[Test][01][1080p].mks"),
        str(tmp_path / "mks" / "[Test][02][1080p].mks"),
    ]


def test_cmd_subset_embed_handles_each_subtitle_separately(tmp_path, monkeypatch):
    """--embed 批量要逐条（逐组）内嵌，不能把全剧集字体嵌进每一份字幕。"""
    from asfmkv import cli

    cfg, args, calls = _prepare_mks_subset(
        tmp_path, monkeypatch, ["ep1.chs.ass", "ep1.cht.ass"])
    args.mks = False
    args.embed = True
    args.out_ass = str(tmp_path / "embed")

    assert cli.cmd_subset(cfg, args) == 0
    assert len(calls["pipeline"]) == 2
    assert all(len(group) == 1 for group in calls["pipeline"])
    assert calls["mux"] == []


def test_harden_console_streams_replaces_unencodable(monkeypatch):
    """重定向到 GBK 管道时，编码不了的字符应被替换而不是抛 UnicodeEncodeError。"""
    import io
    import sys

    from asfmkv import cli

    out_buf, err_buf = io.BytesIO(), io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(out_buf, encoding="gbk"))
    monkeypatch.setattr(sys, "stderr", io.TextIOWrapper(err_buf, encoding="gbk"))

    cli._harden_console_streams()
    sys.stdout.write("字体 \uff65 ok")  # U+FF65 半角片假名中点，GBK 无法编码
    sys.stdout.flush()

    assert b"?" in out_buf.getvalue()
