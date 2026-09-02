#!/usr/bin/env python3
"""Generate collar-buckle engraving artwork: QR code + cat name with hearts.

Usage: make_tag.py NAME DATA [EC] [OUTBASE]   e.g.  make_tag.py Black TINYURL.COM/MEOBLACK q
Outputs NAME-tag.svg / .png (dark = engrave, for light-marking-on-dark metal
use NAME-tag-inverted.*).  Artwork is exactly 16 x 14 mm.
"""
import sys
import segno
import cairosvg
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.boundsPen import BoundsPen
from PIL import Image
from pyzbar.pyzbar import decode

NAME, DATA = sys.argv[1], sys.argv[2]          # e.g. Black TINYURL.COM/MEOBLACK
EC = sys.argv[3] if len(sys.argv) > 3 else "q"  # error-correction level
OUT = sys.argv[4] if len(sys.argv) > 4 else NAME.lower()
FONT = "/usr/share/fonts/truetype/quicksand/Quicksand-Bold.ttf"

W, H = 16.0, 14.0          # mm, engraving area
MODULE = None              # mm per QR module (auto: 0.46 for v1, 0.40 for v2)
QR_TOP = 0.5               # mm quiet zone above QR
FONT_MAX = 3.1             # mm (em); shrinks automatically for names with descenders
TEXT_GAP = 0.8             # mm between QR bottom and tallest glyph
BOTTOM = 0.4               # mm margin below lowest glyph
HEART_H = 1.9              # mm
GAP = 0.8                  # mm between heart and text

# ---------------- QR ----------------
qr = segno.make(DATA, error=EC, boost_error=False)
assert qr.version <= 2, f"QR too big (version {qr.version}); shorten the URL"
n = qr.symbol_size(border=0)[0]
MODULE = MODULE or {21: 0.46, 25: 0.40}[n]
qr_size = n * MODULE
qx = (W - qr_size) / 2
matrix = [list(row) for row in qr.matrix]


def qr_rects(dark=True):
    out = []
    for r, row in enumerate(matrix):
        # merge horizontal runs into single rects → cleaner vector
        c = 0
        while c < n:
            if bool(row[c]) == dark:
                start = c
                while c < n and bool(row[c]) == dark:
                    c += 1
                out.append(
                    f'<rect x="{qx + start*MODULE:.4f}" y="{QR_TOP + r*MODULE:.4f}" '
                    f'width="{(c-start)*MODULE:.4f}" height="{MODULE:.4f}"/>'
                )
            else:
                c += 1
    return "\n".join(out)


# ---------------- text ----------------
font = TTFont(FONT)
upm = font["head"].unitsPerEm
cmap = font.getBestCmap()
gs = font.getGlyphSet()

# glyph outlines + vertical extent of the name (font units, y-up)
paths, x, ymin, ymax = [], 0, 0, 0
for ch in NAME:
    g = cmap[ord(ch)]
    pen = SVGPathPen(gs)
    gs[g].draw(pen)
    d = pen.getCommands()
    if d:
        paths.append((x, d))
        bp = BoundsPen(gs)
        gs[g].draw(bp)
        ymin, ymax = min(ymin, bp.bounds[1]), max(ymax, bp.bounds[3])
    x += gs[g].width

# fit the name into the band below the QR; baseline sits so descenders clear the edge
avail = H - BOTTOM - (QR_TOP + qr_size + TEXT_GAP)
FONT_SIZE = min(FONT_MAX, avail / ((ymax - ymin) / upm))
scale = FONT_SIZE / upm
BASELINE = H - BOTTOM + ymin * scale
text_w = x * scale

# ---------------- hearts ----------------
# Material "favorite" heart, 24x24 box, ~18.3 wide x 18.35 tall
HEART = ("M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3"
         "c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5"
         "c0 3.78-3.4 6.86-8.55 11.54L12 21.35z")
hs = HEART_H / 18.35
heart_w = 20 * hs
# vertically centre heart on the x-height band of the text
xh = font["OS/2"].sxHeight * scale
heart_cy = BASELINE - xh * 0.55

total_w = heart_w + GAP + text_w + GAP + heart_w
if total_w > W - 1.0:  # keep >=0.5 mm side margin for long names
    GAP = max(0.4, GAP - (total_w - (W - 1.0)) / 2)
    total_w = heart_w + GAP + text_w + GAP + heart_w
x0 = (W - total_w) / 2


def heart_at(cx):
    tx = cx - 12 * hs
    ty = heart_cy - 12.2 * hs
    return f'<path transform="translate({tx:.4f} {ty:.4f}) scale({hs:.5f})" d="{HEART}"/>'


text_x = x0 + heart_w + GAP
text_svg = "\n".join(
    f'<path transform="translate({text_x + gx*scale:.4f} {BASELINE:.4f}) scale({scale:.6f} {-scale:.6f})" d="{d}"/>'
    for gx, d in paths
)
hearts_svg = heart_at(x0 + heart_w / 2) + "\n" + heart_at(x0 + total_w - heart_w / 2)


def quiet_zone_rects():
    # inverted metal needs the quiet zone engraved (light) as well
    side = 2 * MODULE
    top = QR_TOP
    bottom = min(2 * MODULE, BASELINE - FONT_SIZE * 0.78 - (QR_TOP + qr_size) - 0.2)
    x1, y1 = qx - side, 0
    x2, y2 = qx + qr_size + side, QR_TOP + qr_size + bottom
    return "\n".join([
        f'<rect x="{x1:.4f}" y="{y1:.4f}" width="{x2-x1:.4f}" height="{top:.4f}"/>',
        f'<rect x="{x1:.4f}" y="{QR_TOP + qr_size:.4f}" width="{x2-x1:.4f}" height="{bottom:.4f}"/>',
        f'<rect x="{x1:.4f}" y="{y1:.4f}" width="{side:.4f}" height="{y2-y1:.4f}"/>',
        f'<rect x="{qx + qr_size:.4f}" y="{y1:.4f}" width="{side:.4f}" height="{y2-y1:.4f}"/>',
    ])


def svg(inverted):
    body = qr_rects(dark=not inverted)
    if inverted:
        body = quiet_zone_rects() + "\n" + body
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" height="{H}mm" viewBox="0 0 {W} {H}">
<!-- {NAME} collar tag · {DATA} · QR v{qr.version}-{qr.error} alphanumeric, {MODULE} mm modules · black = engrave -->
<rect width="{W}" height="{H}" fill="#fff"/>
<g id="qr" fill="#000">
{body}
</g>
<g id="hearts" fill="#000">
{hearts_svg}
</g>
<g id="name" fill="#000">
{text_svg}
</g>
</svg>
"""


base = OUT
for inv in (False, True):
    fn = f"{base}-tag{'-inverted' if inv else ''}"
    s = svg(inv)
    open(f"{fn}.svg", "w").write(s)
    px_w = round(W / 25.4 * 1200)
    cairosvg.svg2png(bytestring=s.encode(), write_to=f"{fn}.png", output_width=px_w,
                     output_height=round(px_w * H / W))
    # pure black/white, 1200 dpi metadata so it imports at exactly 16x14 mm
    im = Image.open(f"{fn}.png").convert("L").point(lambda v: 255 if v > 128 else 0)
    im.convert("1").save(f"{fn}.png", dpi=(1200, 1200))
    # verification: decode at full res and at a crude 150-dpi downscale
    small = im.resize((im.width // 8, im.height // 8), Image.LANCZOS)
    res_full = [d.data.decode() for d in decode(im)]
    res_small = [d.data.decode() for d in decode(small)]
    print(f"{fn}: full={res_full} small={res_small}")

print(f"QR: version {qr.version}, EC {qr.error}, mode {qr.mode}, {n}x{n} modules @ {MODULE} mm = {qr_size:.2f} mm")
print(f"text width {text_w:.2f} mm, group width {total_w:.2f} mm")
