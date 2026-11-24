"""Reproducible pixel-template exercise for a separate synthetic SOS placard."""

import struct
import zlib
from pathlib import Path


ASSET = Path(__file__).resolve().parents[1] / "public" / "scene" / "sos.png"
LETTERS = ("111100111001111", "100000101001000", "111100101001111",
           "000100101000001", "111100111001111")
WIDTH, HEIGHT, SCALE = 240, 112, 12
X, Y = 30, 26


def chunk(kind, content):
    return (struct.pack(">I", len(content)) + kind + content
            + struct.pack(">I", zlib.crc32(kind + content)))


def write_placard(path=ASSET):
    rows = bytearray()
    for y in range(HEIGHT):
        rows.append(0)
        for x in range(WIDTH):
            col, row = (x - X) // SCALE, (y - Y) // SCALE
            ink = 0 <= row < 5 and 0 <= col < 15 and LETTERS[row][col] == "1"
            rows.append(24 if ink else 234)
    header = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 0, 0, 0, 0)
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
                           + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def inspect_placard(path=ASSET):
    """Inspect a fixed-position placard in the bundled grayscale PNG format."""
    data = Path(path).read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Expected a PNG placard")
    pos, compressed = 8, bytearray()
    header = None
    while pos + 12 <= len(data):
        size = int.from_bytes(data[pos:pos + 4], "big")
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + size]
        if kind == b"IHDR":
            header = body
        elif kind == b"IDAT":
            compressed.extend(body)
        pos += size + 12
    if header != struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 0, 0, 0, 0):
        raise ValueError("Expected a 240 by 112 grayscale exercise image")
    pixels = zlib.decompress(compressed)
    stride = WIDTH + 1
    if len(pixels) != HEIGHT * stride or any(pixels[y * stride] for y in range(HEIGHT)):
        raise ValueError("Expected unfiltered grayscale rows")
    agreement = sum(
        (pixels[(Y + y*SCALE + SCALE//2)*stride + 1 + X + x*SCALE + SCALE//2] < 128)
        == (bit == "1")
        for y, row in enumerate(LETTERS) for x, bit in enumerate(row)
    ) / 75
    detected = agreement >= 0.96
    return {"label": "SOS" if detected else None, "detected": detected,
            "template_agreement": round(agreement, 3), "provenance": "synthetic_placard_template",
            "review_status": "pending", "asset": "/scene/sos.png" if Path(path) == ASSET else None}


if __name__ == "__main__":
    write_placard()
    print(inspect_placard())
