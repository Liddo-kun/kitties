#!/usr/bin/env python3
"""Generate collar-buckle engraving artwork: QR code + cat name with hearts.

Usage: make_tag.py NAME DATA [EC] [OUTBASE] [LAYOUT]
  e.g. make_tag.py Black BIT.LY/MEOBLACK q black side

LAYOUT  side   – QR fills the height on the left, name runs vertically up the
                 right edge (largest modules; default)
        bottom – name centred under the QR

Outputs OUTBASE-tag.svg / .png (black = engrave).  For dark metal that marks
light, use OUTBASE-tag-inverted.* instead.  Artwork is exactly 16 x 14 mm.
"""
import sys
import segno
import cairosvg
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.boundsPen import BoundsPen
from PIL import Image
from pyzbar.pyzbar import decode

NAME, DATA = sys.argv[1], sys.argv[2]
EC = sys.argv[3] if len(sys.argv) > 3 else "q"
OUT = sys.argv[4] if len(sys.argv) > 4 else NAME.lower()
LAYOUT = sys.argv[5] if len(sys.argv) > 5 else "side"
FONT = "/usr/share/fonts/truetype/quicksand/Quicksand-Bold.ttf"

W, H = 16.0, 14.0          # mm, engraving area
MARGIN = 0.3               # mm kept clear at the outer edges
FONT_MAX = 3.1             # mm (em)
HEART_RATIO = 0.62         # heart height as a fraction of font size
GAP = 0.8                  # mm between heart and text

# ---------------- QR ----------------
qr = segno.make(DATA, error=EC, boost_error=False, micro=False)  # phones cannot read Micro QR
assert qr.version <= 2, f"QR too big (version {qr.version}); shorten the URL"
n = qr.symbol_size(border=0)[0]
matrix = [list(row) for row in qr.matrix]

# ---------------- font ----------------
font = TTFont(FONT)
upm = font["head"].unitsPerEm
cmap = font.getBestCmap()
gs = font.getGlyphSet()
xh = font["OS/2"].sxHeight

glyphs, adv, ymin, ymax = [], 0, 0, 0       # font units, y-up
for ch in NAME:
    g = cmap[ord(ch)]
    pen = SVGPathPen(gs)
    gs[g].draw(pen)
    if pen.getCommands():
        glyphs.append((adv, pen.getCommands()))
        bp = BoundsPen(gs)
        gs[g].draw(bp)
        ymin, ymax = min(ymin, bp.bounds[1]), max(ymax, bp.bounds[3])
    adv += gs[g].width

# Material "favorite" heart, 24x24 box (~18.3 wide x 18.35 tall)
HEART = ("M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3"
         "c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5"
         "c0 3.78-3.4 6.86-8.55 11.54L12 21.35z")


def group_metrics(fs):
    """(total length, thickness) in mm of '♥ NAME ♥' at font size fs."""
    s = fs / upm
    hh = fs * HEART_RATIO
    hw = hh * 20 / 18.35
    return hw + GAP + adv * s + GAP + hw, (ymax - ymin) * s


# ---------------- layout ----------------
if LAYOUT == "side":
    # name column runs along the right edge; QR gets the remaining width/height
    max_len = H - 2 * MARGIN
    fs = FONT_MAX
    while group_metrics(fs)[0] > max_len:
        fs -= 0.02
    length, thick = group_metrics(fs)
    # module size: margins + QR + 1-module gap + text column must fit W
    MODULE = min((W - 2 * MARGIN - thick) / (n + 1), (H - 2 * MARGIN) / n)
    qr_size = n * MODULE
    qx, qy = MARGIN, (H - qr_size) / 2
    col_left = qx + qr_size + MODULE
else:
    MODULE = {21: 0.46, 25: 0.40}[n]
    qr_size = n * MODULE
    qx, qy = (W - qr_size) / 2, 0.5
    avail = H - 0.4 - (qy + qr_size + 0.8)
    fs = min(FONT_MAX, avail / ((ymax - ymin) / upm))
    while group_metrics(fs)[0] > W - 1.0:
        fs -= 0.02
    length, thick = group_metrics(fs)

s = fs / upm
hh = fs * HEART_RATIO
hs = hh / 18.35
hw = hh * 20 / 18.35
heart_cy = -xh * s * 0.55          # local coords: baseline at y=0, y down


def local_group():
    """'♥ NAME ♥' laid out horizontally, origin at left end on the baseline."""
    parts = []
    for cx in (hw / 2, length - hw / 2):
        parts.append(f'<path transform="translate({cx - 12*hs:.4f} {heart_cy - 12.2*hs:.4f}) scale({hs:.5f})" d="{HEART}"/>')
    tx = hw + GAP
    for gx, d in glyphs:
        parts.append(f'<path transform="translate({tx + gx*s:.4f} 0) scale({s:.6f} {-s:.6f})" d="{d}"/>')
    return "\n".join(parts)


if LAYOUT == "side":
    # rotate -90°: reads bottom-to-top, letter tops face the QR
    ox = col_left + ymax * s
    oy = (H + length) / 2
    text_transform = f"translate({ox:.4f} {oy:.4f}) rotate(-90)"
else:
    ox = (W - length) / 2
    oy = H - 0.4 + ymin * s
    text_transform = f"translate({ox:.4f} {oy:.4f})"


def qr_rects(dark=True):
    out = []
    for r, row in enumerate(matrix):
        c = 0
        while c < n:                     # merge horizontal runs → cleaner vector
            if bool(row[c]) == dark:
                start = c
                while c < n and bool(row[c]) == dark:
                    c += 1
                out.append(f'<rect x="{qx + start*MODULE:.4f}" y="{qy + r*MODULE:.4f}" '
                           f'width="{(c-start)*MODULE:.4f}" height="{MODULE:.4f}"/>')
            else:
                c += 1
    return "\n".join(out)


def quiet_zone_rects():
    """Inverted metal needs the quiet zone engraved (light) too – as much as fits."""
    l = max(0, qx - 2 * MODULE)
    t = max(0, qy - 2 * MODULE)
    r = min(W, qx + qr_size + (MODULE if LAYOUT == "side" else 2 * MODULE))
    b = min(H, qy + qr_size + 2 * MODULE)
    return "\n".join([
        f'<rect x="{l:.4f}" y="{t:.4f}" width="{r-l:.4f}" height="{qy-t:.4f}"/>',
        f'<rect x="{l:.4f}" y="{qy+qr_size:.4f}" width="{r-l:.4f}" height="{b-qy-qr_size:.4f}"/>',
        f'<rect x="{l:.4f}" y="{t:.4f}" width="{qx-l:.4f}" height="{b-t:.4f}"/>',
        f'<rect x="{qx+qr_size:.4f}" y="{t:.4f}" width="{r-qx-qr_size:.4f}" height="{b-t:.4f}"/>',
    ])


def svg(inverted):
    body = qr_rects(dark=not inverted)
    if inverted:
        body = quiet_zone_rects() + "\n" + body
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" height="{H}mm" viewBox="0 0 {W} {H}">
<!-- {NAME} collar tag · {DATA} · QR v{qr.version}-{qr.error} {qr.mode}, {MODULE:.3f} mm modules · black = engrave -->
<rect width="{W}" height="{H}" fill="#fff"/>
<g id="qr" fill="#000">
{body}
</g>
<g id="name" fill="#000" transform="{text_transform}">
{local_group()}
</g>
</svg>
"""


for inv in (False, True):
    fn = f"{OUT}-tag{'-inverted' if inv else ''}"
    src = svg(inv)
    open(f"{fn}.svg", "w").write(src)
    px_w = round(W / 25.4 * 1200)
    cairosvg.svg2png(bytestring=src.encode(), write_to=f"{fn}.png",
                     output_width=px_w, output_height=round(px_w * H / W))
    # pure black/white, 1200 dpi metadata so it imports at exactly 16x14 mm
    im = Image.open(f"{fn}.png").convert("L").point(lambda v: 255 if v > 128 else 0)
    im.convert("1").save(f"{fn}.png", dpi=(1200, 1200))
    if not inv:
        small = im.resize((im.width // 8, im.height // 8), Image.LANCZOS)
        print(f"{fn}: full={[d.data.decode() for d in decode(im)]} "
              f"150dpi={[d.data.decode() for d in decode(small)]}")

print(f"QR: version {qr.version}, EC {qr.error}, mode {qr.mode}, {n}x{n} @ {MODULE:.3f} mm = {n*MODULE:.2f} mm")
print(f"name: font {fs:.2f} mm, group {length:.2f} x {thick:.2f} mm")
