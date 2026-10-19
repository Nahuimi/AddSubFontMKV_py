"""字体名称乱码修正。

从 name 表中的其它文本编码、必要时借助 chardet 推断，修复老旧字体的名称。
对应基线中的 fnReadCheck / fnReadCorrect / _detect_fallback。
"""

from __future__ import annotations

import re
from os import path

from chardet import detect

# 检测字体名称表乱码所用正则
CHAR_EXCEPTION = re.compile(
    r"[\U00020000-\U0003134F\u3400-\u4DBF\u2070-\u2BFF\u02B0-\u02FF\uE000-\uF8FF"
    r"\u0080-\u00B1\u00B4-\u00BF]")


class NameDecoder:
    """
    字体名称解码器。

    :param quiet: 为 True 时不输出修正过程信息（对应旧 startQuiet）
    """

    def __init__(self, quiet: bool = True):
        self.quiet = quiet

    def read(self, font, index: int, font_path: str) -> tuple:
        """读取第 index 条 name 记录并尽量修复乱码，返回 (字符串, 编码, 是否老旧字体)。"""
        names = font["name"].names
        name = names[index]
        is_warning = False
        encoding = name.getEncoding()
        try:
            try:
                text = name.toStr()
            except Exception:
                text, encoding = self._correct(font, index, font_path)
                is_warning = True

            if not CHAR_EXCEPTION.search(text):
                return text, encoding, is_warning

            fixed = None
            candidate_encodings = [n.getEncoding().lower() for n in names if not n.isUnicode()]
            for enc in candidate_encodings:
                if enc in ("mac_roman", "utf_16_be"):
                    continue
                try:
                    fixed = name.toBytes().decode(enc)
                    encoding = enc
                    break
                except Exception:
                    continue
            confidence = 1.0

            if fixed is None and "mac_roman" in candidate_encodings:
                fixed, detected = self._detect_fallback(name)
                if fixed is not None:
                    encoding, confidence = detected

            if fixed is not None and not CHAR_EXCEPTION.search(fixed):
                if encoding and not self.quiet:
                    print(f'\n\033[1;33m尝试修正字体"{path.basename(font_path)}"文本编码 '
                          f'"{name.getEncoding()}" >> "{encoding.lower()}" = "{fixed}"\033[0m')
                return fixed, encoding, is_warning
            if not self.quiet:
                print(f'\n\033[1;33m字体"{path.basename(font_path)}"文本编码修复失败 '
                      f'"{name.getEncoding()}" = "{text}"\033[0m')
            return text, encoding, is_warning
        except Exception as exc:
            if not self.quiet:
                print(exc)
            text, encoding = self._correct(font, index, font_path)
            return text, encoding, True

    @staticmethod
    def _detect_fallback(name) -> tuple:
        """从 mac_roman 原始字节探测真实编码，返回 (文本, (编码, 置信度))。"""
        raw = name.toBytes()
        # 旧实现把 repr() 后的十六进制转义用正则抓出来再拼回字节串（还重复拼接了一遍），
        # 既容易漏字节又会干扰 chardet 的统计；直接对原始字节做探测即可。
        try:
            detected = detect(raw)
        except Exception:
            return None, None
        encoding = detected.get("encoding")
        if not encoding or encoding.lower() in ("mac_roman", "windows-1252", "iso-8859-1", "ascii"):
            return None, None
        try:
            return raw.decode(encoding), (encoding, detected.get("confidence", 0.0))
        except Exception:
            return None, None

    def _correct(self, font, index: int, font_path: str) -> tuple:
        """强制修复字体名称读取。"""
        name = font["name"].names[index]
        encoding = "utf-16-be"
        text = name.toBytes().decode(encoding, errors="ignore")
        try:
            if not self.quiet:
                print("")
            raw = name.toBytes()
            if any(b == 0 for b in raw):
                if any(raw[i] != 0 for i in range(0, len(raw), 2)):
                    if not self.quiet:
                        print(f'\033[1;33m尝试修正字体"{path.basename(font_path)}"名称读取 >> "{text}"\033[0m')
                    return text, "\u0000"
                compact = bytes(b for b in raw if b > 0)
                text = compact.decode(name.getEncoding())
                encoding = name.getEncoding()
                if not self.quiet:
                    print(f'\033[1;33m已修正字体"{path.basename(font_path)}"名称读取 >> "{text}"\033[0m')
            else:
                text = raw.decode("utf-16-be", errors="ignore")
        except Exception:
            if not self.quiet:
                print(f'\033[1;33m尝试修正字体"{path.basename(font_path)}"名称读取 >> "{text}"\033[0m')
        return text, encoding