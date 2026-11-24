#!/usr/bin/env python3
"""news-image-20261124 v1 — "The World in One Day, Tuesday Edition".

One-page newspaper, 1024x1024, summing up Tuesday 24 November 2026.
Everything is drawn in code from the bundled bitmap font atlas plus
five real Wikimedia photographs (lead stories) and one coded
illustration (the factory fire). Python 3.13 stdlib only. No network
at grading time: main.py reads atlas.bin.gz and photo_*.rgb.gz from
its own directory and writes $MAKEFUN_OUTPUT_DIR/entry.png
(or ./output/entry.png when the variable is unset).

Deterministic: fixed zlib level, no timestamps, no randomness, no
dict iteration over unordered data. Two runs write byte-identical PNGs.
"""
import gzip
import os
import struct
import sys
import zlib

W, H = 1024, 1024
HERE = os.path.dirname(os.path.abspath(__file__))

# Palette — paper, ink, one red accent, muted blues/greys.
PAPER = (247, 243, 234)
INK = (20, 20, 20)
RED = (176, 30, 36)
NAVY = (31, 58, 95)
GREY = (96, 96, 96)
FAINT = (216, 210, 196)
PALE = (238, 233, 220)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
SMOKE = (120, 120, 118)
FLAME = (214, 90, 20)
FLAME2 = (232, 150, 30)
STEEL = (74, 82, 92)
SKY2 = (186, 210, 228)


# ---------------------------------------------------------------- PNG out
def _chunk(ctype, data):
    out = struct.pack(">I", len(data)) + ctype + data
    out += struct.pack(">I", zlib.crc32(ctype + data) & 0xFFFFFFFF)
    return out


def write_png(path, w, h, rgb):
    """Write RGB bytes (row-major, 3 bytes/px) as a deterministic PNG."""
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 6)
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += _chunk(b"IDAT", comp)
    png += _chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


# ---------------------------------------------------------------- assets
def load_atlas(path):
    """Parse atlas.bin.gz into {name: (px, ascent, {cp: glyph})}.

    Glyph tuple: (advance, xoff, yoff, w, h, packed_rows).
    """
    raw = gzip.open(path, "rb").read()
    assert raw[:5] == b"ATLS2", "bad atlas magic"
    pos = 5
    nfonts = struct.unpack_from(">I", raw, pos)[0]
    pos += 4
    fonts = {}
    for _ in range(nfonts):
        nlen = raw[pos]
        pos += 1
        name = raw[pos:pos + nlen].decode("ascii")
        pos += nlen
        px, ascent, descent, ng = struct.unpack_from(">IHHH", raw, pos)
        pos += 10
        glyphs = {}
        for _ in range(ng):
            cp, adv, xoff, yoff, gw, gh = struct.unpack_from(">IHhhHH", raw, pos)
            pos += 14
            row_bytes = (gw + 7) // 8
            packed = raw[pos:pos + row_bytes * gh]
            pos += row_bytes * gh
            glyphs[cp] = (adv, xoff, yoff, gw, gh, packed)
        fonts[name] = (px, ascent, glyphs)
    return fonts


def load_photo(name):
    """Load a photo_<name>.rgb.gz as (w, h, rgb bytes)."""
    path = os.path.join(HERE, f"photo_{name}.rgb.gz")
    raw = gzip.open(path, "rb").read()
    return raw


# ---------------------------------------------------------------- canvas
class Page:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(bg * (w * h))

    def set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i:i + 3] = bytes(color)

    def rect(self, x0, y0, x1, y1, color):
        x0 = max(0, x0)
        y0 = max(0, y0)
        x1 = min(self.w, x1)
        y1 = min(self.h, y1)
        for y in range(y0, y1):
            i = (y * self.w + x0) * 3
            self.px[i:i + (x1 - x0) * 3] = bytes(color) * (x1 - x0)

    def hline(self, x0, x1, y, color, thick=1):
        for t in range(thick):
            self.rect(x0, y + t, x1, y + t + 1, color)

    def vline(self, x, y0, y1, color, thick=1):
        for t in range(thick):
            self.rect(x + t, y0, x + t + 1, y1, color)

    def disc(self, cx, cy, r, color):
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                if (x - cx) * (x - cx) + (y - cy) * (y - cy) <= r * r:
                    self.set(x, y, color)

    def blit(self, x0, y0, w, h, rgb):
        """Copy raw RGB rows onto the page, clipped."""
        for y in range(h):
            yy = y0 + y
            if yy < 0 or yy >= self.h:
                continue
            row = rgb[y * w * 3:(y + 1) * w * 3]
            sx0 = max(0, -x0)
            sx1 = min(w, self.w - x0)
            if sx1 <= sx0:
                continue
            i = (yy * self.w + x0 + sx0) * 3
            self.px[i:i + (sx1 - sx0) * 3] = row[sx0 * 3:sx1 * 3]


# ---------------------------------------------------------------- text
class Typer:
    def __init__(self, fonts):
        self.fonts = fonts

    def width(self, font_name, text):
        _, _, glyphs = self.fonts[font_name]
        total = 0
        for ch in text:
            g = glyphs.get(ord(ch))
            if g is None:
                g = glyphs.get(32)
            total += g[0]
        return total

    def draw(self, page, font_name, x, baseline, text, color):
        _, _, glyphs = self.fonts[font_name]
        pen = x
        for ch in text:
            g = glyphs.get(ord(ch))
            if g is None:
                g = glyphs.get(32)
            adv, xoff, yoff, gw, gh, packed = g
            if gw and gh:
                row_bytes = (gw + 7) // 8
                for gy in range(gh):
                    for gx in range(gw):
                        byte = packed[gy * row_bytes + gx // 8]
                        if byte & (0x80 >> (gx % 8)):
                            page.set(pen + xoff + gx, baseline + yoff + gy, color)
            pen += adv
        return pen

    def draw_centred(self, page, font_name, cx, baseline, text, color):
        w = self.width(font_name, text)
        return self.draw(page, font_name, cx - w // 2, baseline, text, color)

    def wrap(self, font_name, text, max_w):
        """Greedy word wrap; returns a list of lines fitting max_w."""
        words = text.split(" ")
        lines = []
        cur = ""
        for word in words:
            trial = word if not cur else cur + " " + word
            if self.width(font_name, trial) <= max_w:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines

    def draw_wrapped(self, page, font_name, x, baseline, text, color,
                     max_w, line_h):
        lines = self.wrap(font_name, text, max_w)
        y = baseline
        for line in lines:
            self.draw(page, font_name, x, y, line, color)
            y += line_h
        return y


# ---------------------------------------------------------------- stories
# Every number below appears in exactly one version on the page.
# Wires read to 07:00 UTC, Tuesday 24 November 2026.

MASTHEAD = "THE WORLD IN ONE DAY"
DATE_LINE = "TUESDAY, 24 NOVEMBER 2026"

STATS = [
    ("7", "SEA DRONES"),
    ("5", "MINUTES"),
    ("24", "DEAD"),
    ("30", "MISSING"),
    ("$2B", "INTEL BET"),
    ("50M", "CHILDREN"),
]

STRIP = ("07:52 KST — KADIZ ALERT — 07:57 — LIFTED AFTER 5 MINUTES — "
         "CANBERRA — MEGASPEED PROBE GOES ON — CIKANDE — 24 DEAD, 30 MISSING")

LEAD = {
    "kicker": "TECH / ESPIONAGE — CONFIRMED",
    "headline": "US BLACKLISTS MEGASPEED IN NVIDIA SPY SCANDAL",
    "deck": ("Washington puts the Singapore chip firm and six related "
             "companies on its Entity List; Singapore's PM says the probe "
             "goes on; Nvidia reinstates Jensen Huang as chief executive; "
             "an Alibaba unit is listed too."),
    "photo": "huang",
    "caption": "Jensen Huang, Nvidia chief executive (file photo)",
}

CARDS = [
    {
        "kicker": "KOREA — CONFIRMED",
        "headline": "RUSSIAN JETS SET OFF 5-MINUTE ALERT",
        "deck": ("Several Russian warplanes enter South Korea's air defence "
                 "zone near Ulleung Island; the alert sounds at 07:52, "
                 "ends 07:57."),
        "photo": "f15k",
        "caption": "ROKAF F-15K (file photo)",
    },
    {
        "kicker": "UKRAINE WAR — KYIV'S CLAIM",
        "headline": "UKRAINE SINKS RUSSIAN SHIP",
        "deck": ("Seven sea drones strike the corvette Merkury at Benghazi; "
                 "Zelensky says it sank; the cargo ship MV Angara is "
                 "also hit."),
        "photo": "corvette",
        "caption": "Steregushchiy-class corvette (file photo)",
    },
    {
        "kicker": "CLIMATE — CONFIRMED",
        "headline": "SUMMIT DIES ON FOSSIL FUELS",
        "deck": ("Two weeks of talks in Antalya end with no deal — the first "
                 "collapse since Copenhagen in 2009; the EU rejects "
                 "the text."),
        "photo": "guterres",
        "caption": "Antonio Guterres at COP31 (file photo)",
    },
]

ROW2 = [
    {
        "kicker": "DIPLOMACY — REPORTED",
        "headline": "KYIV: TALKS \"TOMORROW\"",
        "deck": ("Zelensky tells NATO lawmakers Ukraine will meet Russia, "
                 "the US and Europe as early as Tuesday."),
        "photo": "zelensky",
        "caption": "Zelensky in Canada, Sep 2026 (file photo)",
    },
    {
        "kicker": "INDONESIA — CONFIRMED",
        "headline": "24 DEAD IN FACTORY FIRE",
        "deck": ("Fire guts the PT Fonusa Agung Mulia plant in Cikande; "
                 "about 300 were inside; 15 rescued alive."),
        "photo": None,  # drawn in code: factory, smoke, flames
        "caption": "Factory fire, drawn from reports",
    },
]

ALSO = [
    "ICE — FATHER, DAUGHTER HELD AT SEA-TAC",
    "TRADE — TRUMP HAILS JAPAN DEAL",
    "CANADA — PENTAGON REBUKES F-35 REVIEW",
    "CHINA — DEATH FOR SPYING OFFICIAL",
    "INDIA — KEEPS 3RD IN ASIA POWER LIST",
    "HEALTH — BANGLADESH SHOTS FOR 50M KIDS",
    "CHIPS — SOFTBANK PLANS $2B FOR INTEL",
    "TRUCE — THAI-CAMBODIA FIGHT ON HOLD",
    "FLOOD — 4 DEAD, 100 MISSING IN HIMALAYAS",
    "BRAZIL — DEADLY STORM DISPLACES 1,000S",
    "GAZA — DRONE STRIKE KILLS 3 AT POST",
    "WEST BANK — US VOICE: \"TERRIBLE\"",
    "MEXICO — 'EL CHAPO ISIDRO' TRIED AT HOME",
    "AI RULES — GUTERRES: DEAL WITHIN A YEAR",
    "ROBOT ARMS — UN TALKS END, NO DEAL",
    "CRICKET — INDIA-NZ TEST ENDS IN DRAW",
    "FOOTBALL — TRESOLDI TREBLE, 7 GOALS",
    "NORWAY — COURT VOIDS OIL LICENCES",
    "EBOLA — KENYA CLEAR; DRC TOLL 5,300",
    "S. AFRICA — VOTERS TEST ANC ON SERVICES",
    "CONGO — TSHISEKEDI SIGNS REFORM LAW",
    "JOBS — KENYA WINS 293,600 SAUDI SLOTS",
    "GEORGIA — TOTAL SURROGACY BAN PLANNED",
    "SUDAN — RSF DRONES BLACK OUT GRID",
]

FOOTER = ("All stories first reported on Tuesday 24 November 2026 — "
          "sources: Reuters, AP, Yonhap, CNN, WSJ")


# ---------------------------------------------------------------- layout
MX = 28            # left margin
CW = 968           # content width (28..996)


def draw_fire_scene(page, x, y, w, h):
    """Flat illustration: a factory in flames under a smoke plume."""
    page.rect(x, y, x + w, y + h, SKY2)
    # smoke plume: three stacked discs, darkest at the base
    page.disc(x + w // 2 - 28, y + 34, 22, SMOKE)
    page.disc(x + w // 2 + 6, y + 22, 26, (140, 140, 138))
    page.disc(x + w // 2 + 34, y + 40, 18, SMOKE)
    page.disc(x + w // 2 - 6, y + 12, 16, (160, 160, 158))
    # factory block with sawtooth roof
    bx, by = x + 18, y + h - 62
    bw, bh = w - 36, 62
    page.rect(bx, by, bx + bw, by + bh, STEEL)
    for i in range(4):
        sx = bx + i * (bw // 4)
        page.rect(sx, by - 12, sx + bw // 4, by, STEEL)
    # lit windows
    for i in range(5):
        wx = bx + 12 + i * (bw // 5)
        page.rect(wx, by + 14, wx + 14, by + 30, (232, 190, 60))
    # flames licking the roofline
    for i, fx in enumerate([bx + 26, bx + 78, bx + 128, bx + 168]):
        fh = [26, 34, 24, 30][i]
        page.rect(fx, by - 12 - fh, fx + 16, by - 12, FLAME2 if i % 2 else FLAME)
    # ground line + label inside the scene
    page.rect(x, y + h - 4, x + w, y + h, (60, 60, 60))


def draw_masthead(page, t):
    t.draw_centred(page, "mast", W // 2, 56, MASTHEAD, INK)
    page.hline(MX, MX + CW, 66, RED, 3)
    t.draw_centred(page, "date", W // 2, 96, DATE_LINE, RED)


def draw_stats(page, t, y0):
    n = len(STATS)
    bw = 158
    gap = 4
    for i, (num, label) in enumerate(STATS):
        x0 = MX + i * (bw + gap)
        page.rect(x0, y0, x0 + bw, y0 + 42, PALE)
        page.hline(x0, x0 + bw, y0, RED, 2)
        t.draw_centred(page, "stat22", x0 + bw // 2, y0 + 26, num, INK)
        t.draw_centred(page, "stat11", x0 + bw // 2, y0 + 39, label, GREY)
    return y0 + 42


def draw_strip(page, t, y0):
    t.draw_centred(page, "strip12", W // 2, y0 + 13, STRIP, NAVY)
    return y0 + 18


def draw_lead(page, t, y0):
    photo_w, photo_h = 460, 260
    page.blit(MX, y0, photo_w, photo_h, load_photo(LEAD["photo"]))
    page.rect(MX, y0 + photo_h - 18, MX + photo_w, y0 + photo_h, BLACK)
    t.draw(page, "deck13", MX + 6, y0 + photo_h - 5, LEAD["caption"], WHITE)
    tx = MX + photo_w + 16
    tw = MX + CW - tx
    t.draw(page, "kick13", tx, y0 + 16, LEAD["kicker"], RED)
    y = t.draw_wrapped(page, "head30", tx, y0 + 52, LEAD["headline"],
                       INK, tw, 36)
    y = t.draw_wrapped(page, "deck15", tx, y + 22, LEAD["deck"],
                       INK, tw, 20)
    return y0 + photo_h


def draw_card(page, t, x, y0, w, card):
    photo_w, photo_h = w - 2, 128
    page.blit(x + 1, y0, photo_w, photo_h, load_photo(card["photo"]))
    t.draw(page, "kick13", x, y0 + photo_h + 16, card["kicker"], RED)
    y = t.draw_wrapped(page, "head24", x, y0 + photo_h + 44,
                       card["headline"], INK, w, 25)
    y = t.draw_wrapped(page, "deck13", x, y + 6, card["deck"],
                       GREY, w, 16)
    return y


def draw_row2_card(page, t, x, y0, w, card):
    photo_w, photo_h = 200, 140
    if card["photo"] is None:
        draw_fire_scene(page, x, y0, photo_w, photo_h)
    else:
        page.blit(x, y0, photo_w, photo_h, load_photo(card["photo"]))
    tx = x + photo_w + 12
    tw = x + w - tx
    t.draw(page, "kick13", tx, y0 + 14, card["kicker"], RED)
    y = t.draw_wrapped(page, "head24", tx, y0 + 42, card["headline"],
                       INK, tw, 26)
    y = t.draw_wrapped(page, "deck13", tx, y + 8, card["deck"],
                       GREY, tw, 16)
    return y0 + photo_h


def draw_list(page, t, y0):
    t.draw(page, "kick13", MX, y0 + 12, "ALSO ON — TUESDAY 24 NOVEMBER", RED)
    page.hline(MX, MX + CW, y0 + 18, RED, 2)
    cols = 3
    rows = 8
    col_w = CW // cols
    y = y0 + 34
    for r in range(rows):
        for c in range(cols):
            idx = r * cols + c
            if idx >= len(ALSO):
                continue
            item = ALSO[idx]
            t.draw(page, "deck13", MX + c * col_w, y, item, INK)
        y += 14
    return y


def render():
    fonts = load_atlas(os.path.join(HERE, "atlas.bin.gz"))
    t = Typer(fonts)
    page = Page(W, H, PAPER)
    draw_masthead(page, t)               # 14..96
    draw_stats(page, t, 100)             # 100..142
    draw_strip(page, t, 146)             # 146..164
    draw_lead(page, t, 172)              # 172..432
    # three photo cards: 442..704
    card_w = 312
    gap = 16
    cy = 442
    for i, card in enumerate(CARDS):
        draw_card(page, t, MX + i * (card_w + gap), cy, card_w, card)
    # two wide cards (Zelensky photo + Serang illustration): 714..854
    ry = 714
    half = (CW - gap) // 2
    for i, card in enumerate(ROW2):
        draw_row2_card(page, t, MX + i * (half + gap), ry, half, card)
    ly = draw_list(page, t, 862)         # header 862..878, rows to ~994
    t.draw_centred(page, "deck13", W // 2, 1012, FOOTER, GREY)
    return page


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or os.path.join(HERE, "output")
    os.makedirs(out_dir, exist_ok=True)
    page = render()
    out_path = os.path.join(out_dir, "entry.png")
    write_png(out_path, W, H, bytes(page.px))
    print(f"wrote {out_path}: {os.path.getsize(out_path)} bytes")


if __name__ == "__main__":
    main()
