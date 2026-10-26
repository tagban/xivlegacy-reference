#!/usr/bin/env python3
"""Read FFXIV 1.x GTEX textures and write PNGs (no image library needed).

GTEX layout (header big-endian, pixel data as the PC's D3D formats):
    0x00  "GTEX"
    0x06  format: 0x18 DXT1, 0x1A DXT5, 0x04 A8R8G8B8 (B,G,R,A bytes)
    0x0A  width  u16
    0x0C  height u16
    0x1C  data size u32
    0x20  pixel data (top mip first)

A client file's id is its path: data/1C/61/01/81.DAT is file 0x1C610181,
which is how ZAM named its icon images.
"""
import struct, zlib

DXT1, DXT5, ARGB = 0x18, 0x1A, 0x04


def read(path):
    """(width, height, RGBA bytes) or None when it isn't a texture we read."""
    data = open(path, "rb").read()
    if data[:4] != b"GTEX":
        return None
    fmt = data[6]
    w, h = struct.unpack(">HH", data[10:14])
    size = struct.unpack(">I", data[0x1C:0x20])[0]
    px = data[0x20:0x20 + size]
    if fmt == DXT1:
        return w, h, dxt(px, w, h, alpha=False)
    if fmt == DXT5:
        return w, h, dxt(px, w, h, alpha=True)
    if fmt == ARGB:
        out = bytearray(w * h * 4)
        for i in range(w * h):
            b, g, r, a = px[i * 4:i * 4 + 4]
            out[i * 4:i * 4 + 4] = bytes((r, g, b, a))
        return w, h, bytes(out)
    return None


def _565(c):
    r, g, b = (c >> 11) & 31, (c >> 5) & 63, c & 31
    return (r << 3 | r >> 2, g << 2 | g >> 4, b << 3 | b >> 2)


def dxt(px, w, h, alpha):
    out = bytearray(w * h * 4)
    step = 16 if alpha else 8
    pos = 0
    for by in range(0, h, 4):
        for bx in range(0, w, 4):
            block = px[pos:pos + step]
            pos += step
            if len(block) < step:
                return bytes(out)
            if alpha:
                a0, a1 = block[0], block[1]
                abits = int.from_bytes(block[2:8], "little")
                if a0 > a1:
                    alphas = [a0, a1] + [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)]
                else:
                    alphas = [a0, a1] + [((5 - i) * a0 + i * a1) // 5 for i in range(1, 5)] + [0, 255]
                color = block[8:16]
            else:
                color = block
            c0, c1 = struct.unpack("<HH", color[:4])
            bits = struct.unpack("<I", color[4:8])[0]
            p0, p1 = _565(c0), _565(c1)
            if c0 > c1 or alpha:
                p2 = tuple((2 * a + b) // 3 for a, b in zip(p0, p1))
                p3 = tuple((a + 2 * b) // 3 for a, b in zip(p0, p1))
                pal = [p0 + (255,), p1 + (255,), p2 + (255,), p3 + (255,)]
            else:
                p2 = tuple((a + b) // 2 for a, b in zip(p0, p1))
                pal = [p0 + (255,), p1 + (255,), p2 + (255,), (0, 0, 0, 0)]
            for i in range(16):
                x, y = bx + (i & 3), by + (i >> 2)
                if x >= w or y >= h:
                    continue
                r, g, b, a = pal[(bits >> (2 * i)) & 3]
                if alpha:
                    a = alphas[(abits >> (3 * i)) & 7]
                o = (y * w + x) * 4
                out[o:o + 4] = bytes((r, g, b, a))
    return bytes(out)


def png(w, h, rgba):
    raw = b"".join(b"\x00" + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
