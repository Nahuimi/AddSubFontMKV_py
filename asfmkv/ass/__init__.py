"""ASS/SSA 子系统：模型、解析、写回、标签拆分与字体分析。"""

from .analyzer import ass_font_change, ass_font_list
from .embedded import decode_uue, encode_uue
from .models import new_ass_info, new_tag_lines
from .parser import ass_analyse
from .tags import ass_event_tags_split, split_tag_positions
from .writer import ass_file_write

# 兼容旧名称
assAnalyseV2 = ass_analyse
assFileWrite = ass_file_write
assFontList = ass_font_list
assFontChange = ass_font_change
eventTagsSplit = ass_event_tags_split
