"""应用配置模型。"""

from __future__ import annotations

from dataclasses import dataclass, replace


# 程序内置默认值；INI 与命令行参数会覆盖其中部分项
DEFAULTS: dict = {
    "using_ff": False,
    "extlist": "mkv;mp4;mts;mpg;flv;mpeg;m2ts;avi;webm;rm;rmvb;mov;mk3d;vob",
    "no_extcheck": False,
    "subl_local": "zh_CN",
    "sub_name2_lang": ".sc = chi; .tc = chi; .chs = chi; .cht = chi; .jap = jpn; .简体中文 = chi; "
                     ".繁體中文 = chi; .繁体中文 = chi; .zh-hans = chi; .zh-hant = chi",
    "rude_sub_n2_l": False,
    "mkvout": "",
    "assout": "?subs",
    "fontout": "?Fonts",
    "fontin": "",
    "exact_lost": False,
    "char_lost": False,
    "char_compatible": True,
    "fontload": True,
    "o_fontload": False,
    "s_fontload": False,
    "f_priority": False,
    "notfont": False,
    "match_strict": True,
    "negative_tag_detect": False,
    "start_quiet": True,
    "warning_stop": False,
    "ignore_lost": True,
    "no_request_font": False,
    "error_stop": True,
    "rm_ass_in": True,
    "rm_attach": True,
    "v_subdir": False,
    "s_subdir": False,
    "copyfont": False,
    "resultw": False,
    "embedded_font_extract": False,
    "subext": ("ass", "ssa", "srt", "sup", "idx"),
}

# 旧 ASFMKVpy.ini 字段名 -> 新字段名
LEGACY_KEY_MAP = {
    "usingFF": "using_ff",
    "extlist": "extlist",
    "no_extcheck": "no_extcheck",
    "subl_local": "subl_local",
    "subName2Lang": "sub_name2_lang",
    "rudeSubN2L": "rude_sub_n2_l",
    "mkvout": "mkvout",
    "assout": "assout",
    "fontout": "fontout",
    "fontin": "fontin",
    "exact_lost": "exact_lost",
    "char_lost": "char_lost",
    "char_compatible": "char_compatible",
    "fontload": "fontload",
    "o_fontload": "o_fontload",
    "s_fontload": "s_fontload",
    "f_priority": "f_priority",
    "notfont": "notfont",
    "matchStrict": "match_strict",
    "negativeTagDetect": "negative_tag_detect",
    "startQuiet": "start_quiet",
    "warningStop": "warning_stop",
    "ignoreLost": "ignore_lost",
    "noRequestFont": "no_request_font",
    "errorStop": "error_stop",
    "rmAssIn": "rm_ass_in",
    "rmAttach": "rm_attach",
    "v_subdir": "v_subdir",
    "s_subdir": "s_subdir",
    "copyfont": "copyfont",
    "resultw": "resultw",
    "embeddedFontExtract": "embedded_font_extract",
}

# 需要按分隔符切分为列表的字段
_LIST_KEYS = {"extlist", "fontin", "subext"}


@dataclass(frozen=True)
class AppConfig:
    """不可变应用配置。用 :meth:`with_overrides` 派生新实例。"""

    using_ff: bool = False
    extlist: tuple = ()
    no_extcheck: bool = False
    subl_local: str = "zh_CN"
    sub_name2_lang: str = DEFAULTS["sub_name2_lang"]
    rude_sub_n2_l: bool = False
    mkvout: str = ""
    assout: str = "?subs"
    fontout: str = "?Fonts"
    fontin: tuple = ()
    exact_lost: bool = False
    char_lost: bool = False
    char_compatible: bool = True
    fontload: bool = True
    o_fontload: bool = False
    s_fontload: bool = False
    f_priority: bool = False
    notfont: bool = False
    match_strict: bool = True
    negative_tag_detect: bool = False
    start_quiet: bool = True
    warning_stop: bool = False
    ignore_lost: bool = True
    no_request_font: bool = False
    error_stop: bool = True
    rm_ass_in: bool = True
    rm_attach: bool = True
    v_subdir: bool = False
    s_subdir: bool = False
    copyfont: bool = False
    resultw: bool = False
    embedded_font_extract: bool = False
    subext: tuple = DEFAULTS["subext"]

    def with_overrides(self, **kwargs) -> "AppConfig":
        """派生一个替换了部分字段的新配置。"""
        return replace(self, **kwargs)


def normalize_extlist(value) -> tuple:
    """把扩展名配置统一为去点、小写、无空项的元组。"""
    if isinstance(value, str):
        # 内置默认值与命令行使用 ";"，旧版 ASFMKVpy.ini 使用 ","
        items = value.replace(",", ";").split(";")
    else:
        items = value
    return tuple(s.strip().lstrip(".").lower() for s in items if str(s).strip())


def normalize_path_list(value) -> tuple:
    """把以 ? 分隔的目录配置统一为非空字符串元组。"""
    if isinstance(value, (list, tuple)):
        return tuple(str(s).strip() for s in value if str(s).strip())
    return tuple(s.strip() for s in str(value).split("?") if s.strip())