"""ASS/SSA 解析、标签拆分与写回测试。"""

from __future__ import annotations

import pytest

from asfmkv.ass import ass_analyse, ass_event_tags_split, ass_file_write, ass_font_list
from asfmkv.ass.tags import split_tag_positions
from asfmkv.utils.encoding import normalize_encoding


def test_parse_fixture(ass_file):
    info = ass_analyse(ass_file)
    assert info["Lines"]["Events"] > 0
    assert "Default" in info["Styles"]
    assert len(info["Events"]) == 160
    assert info["Events"][0]["Event"] == "Dialogue"
    assert "Bold" in info["Styles"]["Default"]


def test_tag_split_detects_bold(ass_file):
    info = ass_analyse(ass_file)
    split = ass_event_tags_split(info, False)
    assert len(split) == 160
    fonts = {part["Fontname"] for parts in split.values() for part in parts}
    assert fonts == {"Arial"}


def test_font_list_aggregates_characters(ass_file):
    info = ass_analyse(ass_file)
    split = ass_event_tags_split(info, False)
    font_list = ass_font_list(info, split, False)
    assert font_list
    (name, italic, bold), chars = next(iter(font_list.items()))
    assert name == "Arial"
    assert "世" in chars and "界" in chars


def test_write_roundtrip_bytes(ass_file, tmp_path):
    info = ass_analyse(ass_file)
    out = tmp_path / "out.ass"
    ass_file_write(str(out), info, False, False)
    again = ass_analyse(str(out))
    assert again["Styles"] == info["Styles"]
    assert again["Events"] == info["Events"]


def test_split_tag_positions_bold_italic():
    flags = split_tag_positions("{\\b1}x", -1)
    assert flags["bold"] == "1"
    assert flags["italic"] is None


def test_missing_format_line_raises(tmp_path):
    from asfmkv.core.errors import AssParseError
    bad = tmp_path / "bad.ass"
    bad.write_text("[Script Info]\nTitle: x\n\n[Events]\n"
                   "Dialogue: 0,x\n" * 40, encoding="utf-8-sig")
    with pytest.raises((AssParseError, IndexError)):
        ass_analyse(str(bad))


def test_dialogue_text_may_contain_commas(tmp_path):
    """事件行 Text 字段允许包含逗号（真实字幕常见），不得报“字段数多于Format定义”。"""
    body = ("[Script Info]\nTitle: x\nScriptType: v4.00+\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, Bold, Italic\n"
            "Style: Default,Arial,20,-1,0\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            'Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,'
            '{\\fad(200,200)\\fnArial}中文字幕, English, 更多\n'
            "Dialogue: 0,0:00:03.00,0:00:04.00,Default,,0,0,0,,纯文本\n")
    target = tmp_path / "commas.ass"
    target.write_text(body, encoding="utf-8-sig")

    info = ass_analyse(str(target))
    assert info["Events"][0]["Text"] == '{\\fad(200,200)\\fnArial}中文字幕, English, 更多'
    assert info["Events"][1]["Text"] == "纯文本"

    # 写回再解析，文本内容保持完全一致（不能丢逗号或空格）
    out = tmp_path / "out.ass"
    ass_file_write(str(out), info)
    again = ass_analyse(str(out))
    assert again["Events"][0]["Text"] == info["Events"][0]["Text"]


def test_style_line_with_extra_commas_still_raises(tmp_path):
    """样式行字段数超过 Format 定义属于畸形数据，仍应给出明确错误。"""
    from asfmkv.core.errors import AssParseError

    body = ("[Script Info]\nTitle: x\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname\n"
            "Style: Default,Arial,Extra\n\n"
            "[Events]\nFormat: Layer, Text\nDialogue: 0,x\n")
    bad = tmp_path / "bad_style.ass"
    bad.write_text(body, encoding="utf-8-sig")
    with pytest.raises(AssParseError):
        ass_analyse(str(bad))


def test_utf8_bom_keeps_first_section_when_chardet_says_utf8(ass_file, monkeypatch):
    """chardet 把带 BOM 的 UTF-8 报成 utf-8 时，BOM 仍应被正确剥离。"""
    import chardet.universaldetector as ud
    import asfmkv.utils.encoding as enc

    class StubDetector:
        def __init__(self):
            self.done = False
            self.result = {"encoding": "utf-8"}

        def feed(self, data):
            self.done = True

    monkeypatch.setattr(ud, "UniversalDetector", StubDetector)
    monkeypatch.setattr(enc, "UniversalDetector", StubDetector)

    info = ass_analyse(ass_file)
    assert info["Styles"]                                  # 首行 BOM 未破坏段落识别
    assert "Default" in info["Styles"]
    assert info["Info"].get("Title") == "Fixture"


def test_normalize_encoding_prefers_bom():
    assert normalize_encoding("utf-8", b"\xef\xbb\xbf[Script") == "utf-8-sig"
    assert normalize_encoding("ascii", b"[Script") == "ascii"
    assert normalize_encoding("gb2312", b"[Script") == "gbk"
    assert normalize_encoding(None, b"[Script") == "utf-8"


def test_truncated_events_section_raises_parse_error(tmp_path):
    """段落头位于文件末尾时应报 AssParseError，而不是 IndexError。"""
    from asfmkv.core.errors import AssParseError

    bad = tmp_path / "truncated.ass"
    bad.write_text("[Script Info]\nTitle: x\n\n[Events]\n", encoding="utf-8-sig")
    with pytest.raises(AssParseError):
        ass_analyse(str(bad))


def test_embedded_section_at_eof_is_parsed(tmp_path):
    """内嵌字体段落位于文件末尾（无后续空行）时不应 IndexError。"""
    body = ("[Script Info]\nTitle: x\n\n[Fonts]\n"
            "fontname: a.ttf\n"
            "M/&5S\"E%!L\n")
    target = tmp_path / "embedded.ass"
    target.write_text(body, encoding="utf-8-sig")
    info = ass_analyse(str(target), keep_embedded=True)
    assert "a.ttf" in info["Fonts"]


def test_embedded_roundtrip(tmp_path):
    """写回再解析后，内嵌字体内容保持一致。"""
    body = "[Script Info]\nTitle: x\n\n[Fonts]\nfontname: a.ttf\nM/&5S\"E%!L\n"
    target = tmp_path / "embedded.ass"
    target.write_text(body, encoding="utf-8-sig")
    info = ass_analyse(str(target), keep_embedded=True)
    out = tmp_path / "out.ass"
    ass_file_write(str(out), info)
    again = ass_analyse(str(out), keep_embedded=True)
    assert again["Fonts"] == info["Fonts"]
