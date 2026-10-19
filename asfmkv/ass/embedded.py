"""ASS/SSA 内嵌字体与图像的 UUEncoding 编解码。"""

from __future__ import annotations


def decode_uue(embedded: list) -> bytes:
    """
    解码 ASS/SSA 内嵌字体/图像的 UUEncoding 内容。

    该格式省略了标准 uuencode 的行首长度字符：每 3 字节编码为 4 个字符，
    末尾按剩余字符数推断原始字节数（2 字符 = 1 字节，3 字符 = 2 字节）。
    """
    if embedded and ("fontname" in embedded[0] or "filename" in embedded[0]):
        embedded.pop(0)
    content = [b - 33 for b in "".join(embedded).strip(" \n").encode("ascii") if b != 10]
    count = len(content)
    full = count - (count % 4)
    result = bytearray()
    for i in range(0, full, 4):
        bs = (content[i] << 18) | (content[i + 1] << 12) | (content[i + 2] << 6) | content[i + 3]
        result.extend(((bs >> 16) & 255, (bs >> 8) & 255, bs & 255))
    remainder = count - full
    if remainder == 2:
        bs = (content[full] << 18) | (content[full + 1] << 12)
        result.append((bs >> 16) & 255)
    elif remainder == 3:
        bs = (content[full] << 18) | (content[full + 1] << 12) | (content[full + 2] << 6)
        result.extend(((bs >> 16) & 255, (bs >> 8) & 255))
    return bytes(result)


def encode_uue(content: bytes, basename: str = "", is_font: bool = True) -> list:
    """将字节内容按规范编码为 UUEncoding 行列表。"""
    size = len(content)
    if basename:
        head = f"fontname: {basename}" if is_font else f"filename: {basename}"
        result = [head + "\n", ""]
    else:
        result = [""]

    def append_chunk(chunk: str) -> None:
        if len(result[-1]) < 80:
            result[-1] += chunk
        else:
            result[-1] += "\n"
            result.append(chunk)

    for i in range(0, size, 3):
        chunk = content[i:i + 3]
        bs = 0
        for j, byte in enumerate(chunk):
            bs |= byte << (16 - 8 * j)
        groups = ((bs >> 18) & 63, (bs >> 12) & 63, (bs >> 6) & 63, bs & 63)
        append_chunk("".join(chr(g + 33) for g in groups[:len(chunk) + 1]))

    if not result[-1].endswith("\n"):
        result[-1] += "\n"
    return result
