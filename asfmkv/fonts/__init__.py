"""字体子系统：扫描、解析、索引、缓存与子集化。"""

from .cache import CURRENT_FONT_CACHE_VER, FontCache
from .cmap import char_exists_check
from .index import (check_ass_font, merge_ass_font_entry, merge_font_index,
                    resolve_from_family, update_ass_font)
from .models import FontFile, FontIndex, FontInfo
from .name_decoder import NameDecoder
from .parser import LCID_FILTER, load_font_faces, progress_fonts, read_face_names
from .scanner import FONT_EXTS, get_font_file_list
from .subsetter import fix_ansi_cmap, name_str_for_subset, subset_crc, subset_fonts

# 兼容旧名称
fontProgress = progress_fonts
checkAssFont = check_ass_font
updateAssFont = update_ass_font
assFontSubset = subset_fonts
charExistCheck = char_exists_check
getFontFileList = get_font_file_list
fnGetFromFamilyName = resolve_from_family
