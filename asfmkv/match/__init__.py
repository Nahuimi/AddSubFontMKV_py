"""媒体-字幕匹配子系统。"""

from .media import list_media
from .rename import apply_rename, rename_preview
from .subtitles import (get_sub_name, get_subtitles, most_common, name_matching_progress,
                        name_position)

# 兼容旧名称
getSubtitles = get_subtitles
getSubName = get_sub_name
nameMatchingProgress = name_matching_progress
namePosition = name_position
renamePreview = rename_preview
