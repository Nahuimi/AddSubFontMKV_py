"""封装子系统：mkvmerge / FFmpeg / 内嵌三种方式。"""

from .base import cleanup_after_mux, resolve_mux_outfile, subtitle_note
from .embedded import mux_embedded
from .ffmpeg import build_ffmpeg_args, mux_with_ffmpeg, probe_streams
from .mkvmerge import build_mkvmerge_args, mux_with_mkvmerge
from .models import MuxJob, MuxResult

# 兼容旧名称
asfmkv = mux_with_mkvmerge
ASFMKV = mux_with_mkvmerge
ff_asfmkv = mux_with_ffmpeg
ffASFMKV = mux_with_ffmpeg
