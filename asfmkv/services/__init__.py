"""服务层：面向 UI/CLI 的高层用例。"""

from .list_fonts import collect_ass_fonts, list_ass_font_scan, write_embedded_fonts, write_non_subset
from .load_fonts import load_fonts, make_font_loader, temple_font_load
from .subset_mux import run_pipeline
from .transcode import detect_transcode, transcode_batch

# 兼容旧名称
templeFontLoad = temple_font_load
main = run_pipeline
tc_detect_transcode = detect_transcode
