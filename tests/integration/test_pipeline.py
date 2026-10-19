"""集成测试：完整子集化流水线（端到端）。"""

from __future__ import annotations

import os
from os import path

import pytest

from asfmkv.ass import ass_analyse, ass_event_tags_split, ass_font_change, ass_font_list
from asfmkv.fonts.index import check_ass_font, update_ass_font
from asfmkv.fonts.models import FontIndex
from asfmkv.fonts.parser import progress_fonts
from asfmkv.fonts.scanner import get_font_file_list
from asfmkv.fonts.subsetter import subset_fonts

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def font_index():
    fl = get_font_file_list(noreg=False)[:120]
    return progress_fonts(fl, FontIndex(), quiet=True)


def _write_ass(path: str, fontname: str, events: int = 160) -> None:
    lines = ["[Script Info]\n", "Title: Integration\n", "ScriptType: v4.00+\n", "\n",
             "[V4+ Styles]\n", "Format: Name, Fontname, Fontsize, Bold, Italic\n",
             f"Style: Default,{fontname},20,-1,0\n", "\n",
             "[Events]\n", "Format: Layer, Start, End, Style, Text\n"]
    for i in range(events):
        lines.append(f"Dialogue: 0,0:00:{i % 60:02d}.00,0:00:{(i % 60) + 1:02d}.00,Default,"
                     f"Hello 世界 {i}\\NSecond line\n")
    with open(path, "w", encoding="utf-8-sig") as fh:
        fh.writelines(lines)


def test_pipeline_produces_subset_font_and_subtitle(tmp_path, font_index):
    fontname = next((n for n in font_index.font_name if n.lower() == "arial"), None)
    if fontname is None:
        pytest.skip("系统未安装 Arial")

    ass_path = str(tmp_path / "ep1.ass")
    _write_ass(ass_path, fontname)

    info = ass_analyse(ass_path)
    split = ass_event_tags_split(info, False)
    font_list = ass_font_list(info, split, False)
    ass_font, font_index = check_ass_font(font_list, font_index, ignore_lost_fonts=True)
    assert ass_font

    out_dir = str(tmp_path / "fonts")
    new_font_name = subset_fonts(ass_font, out_dir, char_compatible=True, ignore_lost=True,
                                 error_stop=True)
    assert new_font_name
    for new_path, new_name in new_font_name.values():
        assert path.isfile(new_path)
        assert new_name is not None

    new_ass = ass_font_change(new_font_name, ass_path, info, split, str(tmp_path / "subs"))
    assert path.isfile(new_ass)
    rewritten = ass_analyse(new_ass)
    assert rewritten["Subset"]
    assert rewritten["Styles"]["Default"]["Fontname"] != fontname


def test_subset_output_is_deterministic(tmp_path, font_index):
    fontname = next((n for n in font_index.font_name if n.lower() == "arial"), None)
    if fontname is None:
        pytest.skip("系统未安装 Arial")

    ass_path = str(tmp_path / "ep2.ass")
    _write_ass(ass_path, fontname)

    def run(out):
        info = ass_analyse(ass_path)
        split = ass_event_tags_split(info, False)
        fl = ass_font_list(info, split, False)
        af, _ = check_ass_font(fl, font_index, ignore_lost_fonts=True)
        return subset_fonts(af, out, char_compatible=True, ignore_lost=True, error_stop=True)

    first = run(str(tmp_path / "f1"))
    second = run(str(tmp_path / "f2"))
    assert {k: path.basename(v[0]) for k, v in first.items()} == \
           {k: path.basename(v[0]) for k, v in second.items()}


def test_embed_mode_multiple_subtitles_share_temp_fonts(tmp_path, font_index):
    """--embed 处理多份字幕时，临时子集字体不能被第一份字幕删掉。"""
    fontname = next((n for n in font_index.font_name if n.lower() == "arial"), None)
    if fontname is None:
        pytest.skip("系统未安装 Arial")

    first = str(tmp_path / "ep1.chs.ass")
    second = str(tmp_path / "ep1.cht.ass")
    _write_ass(first, fontname, events=5)
    _write_ass(second, fontname, events=5)

    info = ass_analyse(first)
    split = ass_event_tags_split(info, False)
    font_list = ass_font_list(info, split, False)
    ass_font, font_index = check_ass_font(font_list, font_index, ignore_lost_fonts=True)
    new_font_name = subset_fonts(ass_font, str(tmp_path / "fonts"), char_compatible=True,
                                 ignore_lost=True, error_stop=True)
    assert new_font_name

    for index, ass_path in enumerate((first, second)):
        sub_info = ass_analyse(ass_path)
        sub_split = ass_event_tags_split(sub_info, False)
        out = ass_font_change(new_font_name, ass_path, sub_info, sub_split,
                              str(tmp_path / f"subs{index}"), embedded=True)
        assert path.isfile(out)
        assert ass_analyse(out, keep_embedded=True)["Fonts"]  # 字体确实写进了字幕


@pytest.mark.integration
def test_subset_command_generates_mks_batch(tmp_path):
    """asfmkv subset <目录> --mks：每条字幕生成一个含字幕轨与字体附件的 mks。"""
    import json
    from types import SimpleNamespace

    from asfmkv import cli
    from asfmkv.config import load_config
    from asfmkv.utils.proc import run

    if run(["mkvmerge", "-V"]).returncode > 0:
        pytest.skip("未安装 mkvmerge")

    cfg = load_config(ini_path=str(tmp_path / "none.ini"))
    for name in ("01.chs.ass", "01.cht.ass"):
        _write_ass(str(tmp_path / name), "Arial", events=5)

    out_dir = tmp_path / "mks"
    args = SimpleNamespace(path=str(tmp_path), subtitle=[], out_ass=None, out_font=None,
                           out_media=str(out_dir), mux=False, ffmpeg=False, embed=False, mks=True)
    assert cli.cmd_subset(cfg, args) == 0

    files = sorted(out_dir.glob("*.mks"))
    assert len(files) == 2
    for mks in files:
        probe = run(["mkvmerge", "-J", str(mks)])
        assert probe.returncode in (0, 1)
        data = json.loads(probe.stdout)
        assert any(t["type"] == "subtitles" for t in data["tracks"])
        assert data.get("attachments")


@pytest.mark.integration
def test_subset_command_mks_pattern_merges_episode_subtitles(tmp_path):
    """--pattern 按视频文件名规则把同一集的 chs/cht 合并进一个 mks。"""
    import json
    from types import SimpleNamespace

    from asfmkv import cli
    from asfmkv.config import load_config
    from asfmkv.utils.proc import run

    if run(["mkvmerge", "-V"]).returncode > 0:
        pytest.skip("未安装 mkvmerge")

    cfg = load_config(ini_path=str(tmp_path / "none.ini"))
    for name in ("[Test][01][1080p].chs.ass", "[Test][01][1080p].cht.ass"):
        _write_ass(str(tmp_path / name), "Arial", events=5)

    out_dir = tmp_path / "mks"
    args = SimpleNamespace(path=str(tmp_path), subtitle=[], out_ass=None, out_font=None,
                           out_media=str(out_dir), mux=False, ffmpeg=False, embed=False,
                           mks=True, pattern="[Test][*][1080p]")
    assert cli.cmd_subset(cfg, args) == 0

    files = sorted(out_dir.glob("*.mks"))
    assert [f.name for f in files] == ["[Test][01][1080p].mks"]
    data = json.loads(run(["mkvmerge", "-J", str(files[0])]).stdout)
    assert [t["type"] for t in data["tracks"]] == ["subtitles", "subtitles"]


@pytest.mark.integration
def test_mkvmerge_mux_structure(tmp_path):
    """用 ffmpeg 现造一段媒体，再用 mkvmerge 封装并校验产物结构。"""
    from asfmkv.mux import MuxJob, mux_with_mkvmerge
    from asfmkv.utils.proc import run

    if run(["mkvmerge", "-V"]).returncode > 0:
        pytest.skip("未安装 mkvmerge")
    if run(["ffmpeg", "-version"]).returncode != 0:
        pytest.skip("未安装 ffmpeg")

    media = str(tmp_path / "movie.mkv")
    gen = run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=128x72:rate=5",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", media])
    if gen.returncode != 0 or not path.isfile(media):
        pytest.skip("ffmpeg 无法生成测试媒体")

    ass = str(tmp_path / "movie.sc.ass")
    with open(ass, "w", encoding="utf-8-sig") as fh:
        fh.write("[Script Info]\nTitle: T\nScriptType: v4.00+\n\n"
                 "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, Bold, Italic\n"
                 "Style: Default,Arial,20,-1,0\n\n"
                 "[Events]\nFormat: Layer, Start, End, Style, Text\n"
                 "Dialogue: 0,0:00:00.00,0:00:01.00,Default,hi\n")

    job = MuxJob(file=media, out_file=str(tmp_path / "out.mkv"), ass_paths=[ass], make_mks=False)
    result = mux_with_mkvmerge(job, rm_ass_in=True, rm_attach=True, notfont=True)
    assert result.return_code in (0, 1)
    assert path.isfile(result.out_file)

    probe = run(["mkvmerge", "-J", result.out_file])
    import json
    data = json.loads(probe.stdout)
    kinds = [t["type"] for t in data.get("tracks", [])]
    assert "video" in kinds and "subtitles" in kinds
