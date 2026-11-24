#!/usr/bin/env python3
"""Build-time asset builder for news-image-20261124 v1 (local use only).

Reads the raw Wikimedia photos in ../work/raw_photos and the system
DejaVu fonts, and writes two kinds of binary asset into this repo dir:
  atlas.bin.gz   - bitmap glyphs for every font size the page needs
  photo_<k>.rgb.gz - one lead photo each, centre-cropped to display size

The graded program (main.py) is stdlib-only and reads only these
binaries plus its own embedded story data. No network at grade time.

Run from the repo directory:  python3 build_assets.py
All output is deterministic: gzip mtime=0, fixed crop boxes, fixed
font render order. Re-running produces byte-identical assets.
"""
import gzip
import io
import os
import struct
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "work", "raw_photos")
FONT_DIR = "/usr/share/fonts/truetype/dejavu"

# (atlas name, ttf file, pixel size)
FONTS = [
    ("mast", "DejaVuSerif-Bold.ttf", 44),
    ("date", "DejaVuSans-Bold.ttf", 26),
    ("head30", "DejaVuSerif-Bold.ttf", 30),
    ("head24", "DejaVuSerif-Bold.ttf", 24),
    ("deck15", "DejaVuSans.ttf", 15),
    ("deck13", "DejaVuSans.ttf", 13),
    ("kick13", "DejaVuSans-Bold.ttf", 13),
    ("stat22", "DejaVuSans-Bold.ttf", 22),
    ("stat11", "DejaVuSans-Bold.ttf", 11),
    ("strip12", "DejaVuSans-Bold.ttf", 12),
]

# (asset name, raw file, crop box (x0, y0, x1, y1), target (w, h))
PHOTOS = [
    ("huang", "huang.jpg", (560, 220, 1280, 646), (460, 260)),
    ("f15k", "f15k.jpg", (0, 100, 1507, 829), (310, 128)),
    ("corvette", "corvette.jpg", (0, 500, 4000, 2435), (310, 128)),
    ("zelensky", "zelensky.jpg", (200, 140, 600, 420), (200, 140)),
    ("guterres", "guterres.jpg", (1800, 600, 5200, 2240), (310, 128)),
]

# Codepoints baked into the atlas: printable ASCII + common punctuation.
CODEPOINTS = list(range(32, 127)) + [
    0x2014, 0x2013, 0x2019, 0x2018, 0x201C, 0x201D,
    0x2022, 0x00B7, 0x00E9, 0x00FC, 0x00F6, 0x00E4,
    0x00F1, 0x00E7, 0x00E0, 0x00A0, 0x2019,
]


def pack_glyph(img, bbox):
    """Pack a cropped greyscale glyph bitmap to 1 bit/px, MSB first."""
    x0, y0, x1, y1 = bbox
    w, h = x1 - x0, y1 - y0
    crop = img.crop(bbox)
    px = crop.load()
    row_bytes = (w + 7) // 8
    packed = bytearray()
    for y in range(h):
        for bx in range(row_bytes):
            byte = 0
            for bit in range(8):
                xx = bx * 8 + bit
                if xx < w and px[xx, y] > 110:
                    byte |= 0x80 >> bit
            packed.append(byte)
    return w, h, bytes(packed)


def build_atlas(path):
    """Write atlas.bin.gz.

    Format: magic b"ATLS2", u32 nfonts; per font: u8 namelen, name,
    u32 px, u16 ascent, u16 descent, u16 nglyphs; per glyph:
    u32 cp, u16 advance, i16 xoff, i16 yoff, u16 w, u16 h, then the
    packed rows. Glyph ink lands at (pen_x + xoff, baseline + yoff).
    """
    out = io.BytesIO()
    out.write(b"ATLS2")
    out.write(struct.pack(">I", len(FONTS)))
    for name, ttf, px in FONTS:
        font = ImageFont.truetype(os.path.join(FONT_DIR, ttf), px)
        ascent, descent = font.getmetrics()
        glyphs = []
        for cp in CODEPOINTS:
            ch = chr(cp)
            canvas = Image.new("L", (px * 3, px * 3), 0)
            d = ImageDraw.Draw(canvas)
            d.text((px, px), ch, font=font, fill=255)
            bbox = canvas.getbbox()
            adv = int(round(font.getlength(ch)))
            if bbox is None:
                glyphs.append((cp, adv, 0, 0, 0, 0, b""))
                continue
            x0, y0, x1, y1 = bbox
            w, h, packed = pack_glyph(canvas, bbox)
            xoff = x0 - px
            yoff = (y0 - px) - ascent
            glyphs.append((cp, adv, xoff, yoff, w, h, packed))
        nb = name.encode("ascii")
        out.write(struct.pack(">B", len(nb)))
        out.write(nb)
        out.write(struct.pack(">IHHH", px, ascent, descent, len(glyphs)))
        for cp, adv, xoff, yoff, w, h, packed in glyphs:
            out.write(struct.pack(">I Hhh HH", cp, adv, xoff, yoff, w, h))
            out.write(packed)
        print(f"  font {name}: {px}px ascent={ascent} glyphs={len(glyphs)}")
    blob = out.getvalue()
    with gzip.GzipFile(path, "wb", compresslevel=9, mtime=0) as f:
        f.write(blob)
    print(f"wrote {path}: {os.path.getsize(path)} bytes")


def build_photo(name, raw_file, crop, target):
    """Centre-crop a raw photo to the target aspect, resize, gzip raw RGB."""
    src = os.path.join(RAW, raw_file)
    img = Image.open(src).convert("RGB")
    x0, y0, x1, y1 = crop
    img = img.crop((x0, y0, x1, y1))
    tw, th = target
    sw, sh = img.size
    want = tw / th
    cur = sw / sh
    if cur > want:  # too wide: trim sides
        nw = int(sh * want)
        ox = (sw - nw) // 2
        img = img.crop((ox, 0, ox + nw, sh))
    else:  # too tall: trim top/bottom
        nh = int(sw / want)
        oy = (sh - nh) // 2
        img = img.crop((0, oy, sw, oy + nh))
    img = img.resize((tw, th), Image.LANCZOS)
    rgb = img.tobytes()
    path = os.path.join(HERE, f"photo_{name}.rgb.gz")
    with gzip.GzipFile(path, "wb", compresslevel=9, mtime=0) as f:
        f.write(rgb)
    print(f"wrote {path}: {tw}x{th} raw={len(rgb)} gz={os.path.getsize(path)}")


def main():
    build_atlas(os.path.join(HERE, "atlas.bin.gz"))
    for name, raw_file, crop, target in PHOTOS:
        build_photo(name, raw_file, crop, target)
    print("assets done")


if __name__ == "__main__":
    sys.exit(main())
