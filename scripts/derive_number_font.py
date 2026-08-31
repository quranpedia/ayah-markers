#!/usr/bin/env python3
"""Read the NUMBER BOX out of each marker's own source font.

U+06DD ARABIC END OF AYAH is a prefixed format control: by definition it
encloses the digits that follow it. Fonts that implement it shape
`U+06DD` + digits so the digit glyphs carry NO advance of their own and are
offset on top of the marker glyph -- and several go further, swapping in a
wider ring (`uni06DD.2`, `AyahEnd.alt3`) as the number grows. That is the type
designer's own answer to "where does the number go", so this script reads it
rather than inventing one from the outline.

Method, per marker:

  1. Find the source font for the marker (family + weight from
     `collection.json`), instantiated at that weight if it is variable.
  2. Shape `U+06DD`, and `U+06DD` + one, two and three Arabic-Indic digits.
     The glyph carrying the advance is the marker; every zero-advance glyph is
     part of the number.
  3. Place the number glyphs and take their combined ink bounding box in the
     marker glyph's own coordinate frame. HarfBuzz's RTL run leaves a
     ±advance ambiguity in where the cluster origin sits, so BOTH hypotheses
     are tried and the one whose box lands inside the marker's ink is taken --
     a geometric test, not a guess. If neither does, the font does not enclose
     and the marker falls back to the geometric derivation.
  4. Register the font glyph onto the shipped SVG outline by matching the two
     ink bounding boxes under an identity and a y-flip transform (the SVG
     export may mirror). The winning transform must match to within a unit or
     two, which also proves the SVG really is that font's U+06DD glyph.
  5. Emit the number box in SVG coordinates.

Output: `scripts/_number_font.json`, keyed by marker id, with a per-digit-count
box and the font/glyph it came from.
"""

import io
import json
import os
import re
import sys

import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTDIR = os.environ.get("AYAH_FONT_DIR", "/tmp/amfonts")

AYAH = "۝"
DIGITS = {1: "٧", 2: "٤٨", 3: "٢٥٥"}

# family -> (subdirectory, {weight-or-None: filename})
FONTS = {
    "Alkalami": ("gf", {None: "Alkalami-Regular.ttf"}),
    "Amiri": ("gf", {400: "Amiri-Regular.ttf", 700: "Amiri-Bold.ttf"}),
    "Amiri Quran": ("gf", {None: "AmiriQuran-Regular.ttf"}),
    "Estedad": ("gf", {"var": "Estedad[wght].ttf"}),
    "IBM Plex Sans Arabic": ("gf", {
        100: "IBMPlexSansArabic-Thin.ttf",
        200: "IBMPlexSansArabic-ExtraLight.ttf",
        300: "IBMPlexSansArabic-Light.ttf",
        400: "IBMPlexSansArabic-Regular.ttf",
        500: "IBMPlexSansArabic-Medium.ttf",
        600: "IBMPlexSansArabic-SemiBold.ttf",
        700: "IBMPlexSansArabic-Bold.ttf",
    }),
    "Jomhuria": ("gf", {None: "Jomhuria-Regular.ttf"}),
    "Katibeh": ("gf", {None: "Katibeh-Regular.ttf"}),
    "Kufam": ("gf", {"var": "Kufam[wght].ttf"}),
    "Mada": ("gf", {"var": "Mada[wght].ttf"}),
    "Mirza": ("gf", {None: "Mirza-Regular.ttf"}),
    "Noto Naskh Arabic": ("gf", {"var": "NotoNaskhArabic[wght].ttf"}),
    "Noto Nastaliq Urdu": ("gf", {"var": "NotoNastaliqUrdu[wght].ttf"}),
    "Noto Sans Arabic": ("gf", {"var": "NotoSansArabic[wdth,wght].ttf"}),
    "Scheherazade New": ("gf", {
        400: "ScheherazadeNew-Regular.ttf",
        500: "ScheherazadeNew-Medium.ttf",
        600: "ScheherazadeNew-SemiBold.ttf",
        700: "ScheherazadeNew-Bold.ttf",
    }),
    "DigitalKhattIndoPak": ("ws", {None: "digital-khatt-indopak.otf"}),
    "Indopak": ("ws", {None: "digital-khatt-indopak.otf"}),
    "IndopakNastaleeq": ("ws", {None: "indopak-nastaleeq.ttf"}),
    "HafsNastaleeq": ("ws", {None: "hafs-nastaleeq.otf"}),
    "DigitalKhattV1": ("ws", {None: "digital-khatt-v1.otf"}),
    "UthmanicBazzi": ("ws", {None: "uthmanic-bazzi-v20.ttf"}),
    "UthmanicDouri": ("ws", {None: "uthmanic-douri-v20.ttf"}),
    "UthmanicQaloun": ("ws", {None: "uthmanic-qaloun-v21.ttf"}),
    "UthmanicQunbul": ("ws", {None: "uthmanic-qunbul-v20.ttf"}),
    "UthmanicShuba": ("ws", {None: "uthmanic-shuba-v20.ttf"}),
    "UthmanicSousi": ("ws", {None: "uthmanic-sousi-v20.ttf"}),
    "UthmanicWarsh": ("ws", {None: "uthmanic-warsh-v21.ttf"}),
}

_cache = {}


def load(family, weight):
    sub, table = FONTS[family]
    if "var" in table:
        path, wght = os.path.join(FONTDIR, sub, table["var"]), weight
    elif weight in table:
        path, wght = os.path.join(FONTDIR, sub, table[weight]), None
    else:
        key = min(table, key=lambda k: abs((k or 400) - (weight or 400)))
        path, wght = os.path.join(FONTDIR, sub, table[key]), None
    ck = (path, wght)
    if ck in _cache:
        return _cache[ck]
    tt = TTFont(path)
    if "fvar" in tt and wght is not None:
        axes = {a.axisTag: a for a in tt["fvar"].axes}
        if "wght" in axes:
            a = axes["wght"]
            tt = instancer.instantiateVariableFont(
                tt, {"wght": max(a.minValue, min(a.maxValue, float(wght)))},
                inplace=False, updateFontNames=False,
            )
    buf = io.BytesIO()
    tt.save(buf)
    data = buf.getvalue()
    res = (data, TTFont(io.BytesIO(data)), os.path.basename(path), wght)
    _cache[ck] = res
    return res


def shape(data, text):
    face = hb.Face(data)
    font = hb.Font(face)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    buf.direction = "rtl"
    buf.script = "Arab"
    buf.language = "ar"
    hb.shape(font, buf)
    return list(zip(buf.glyph_infos, buf.glyph_positions))


def union(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def inside(inner, outer, slack):
    return (
        inner[0] >= outer[0] - slack and inner[1] >= outer[1] - slack
        and inner[2] <= outer[2] + slack and inner[3] <= outer[3] + slack
    )


def name_base(name):
    return name.split(".")[0]


def contour_boxes(glyphset, name):
    """Bounding box of each contour of a glyph, so two glyphs can be diffed."""
    from fontTools.pens.recordingPen import DecomposingRecordingPen

    pen = DecomposingRecordingPen(glyphset)
    glyphset[name].draw(pen)
    boxes, pts = [], []
    for op, args in pen.value:
        if op == "moveTo":
            if pts:
                boxes.append(_bbox(pts))
            pts = [args[0]]
        elif op == "closePath":
            if pts:
                boxes.append(_bbox(pts))
            pts = []
        elif args:
            pts.extend(a for a in args if isinstance(a, tuple))
    if pts:
        boxes.append(_bbox(pts))
    return boxes


def _bbox(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def _close(a, b, tol):
    return all(abs(a[i] - b[i]) <= tol for i in range(4))


def measure(family, weight):
    """Number boxes in font units, in the base marker glyph's frame.

    Three enclosure mechanisms are found in the wild and all three are read:

      * POSITIONED digits -- zero-advance digit glyphs offset onto the marker
        (Noto Sans Arabic `uni0667.small`, Estedad, Amiri).
      * A RING ALTERNATE -- as above, but the marker glyph is swapped for a
        wider ring as the number grows (`uni06DD.2`, `AyahEnd.alt3`).
      * A PRECOMPOSED glyph -- the whole run becomes one glyph that already
        contains the number (DigitalKhatt V1's `endofaya255`). Here the number
        is recovered by diffing the composed glyph's contours against the bare
        marker's: the contours that are not in both ARE the number.

    Each candidate box is returned under every plausible origin (HarfBuzz's RTL
    run leaves the cluster origin ambiguous by one advance); the caller picks
    the one that actually lands in the marker's hole.
    """
    data, tt, fname, wght = load(family, weight)
    glyphset = tt.getGlyphSet()
    order = tt.getGlyphOrder()

    def gbounds(gid):
        pen = BoundsPen(glyphset)
        glyphset[order[gid]].draw(pen)
        return pen.bounds

    base = shape(data, AYAH)
    if len(base) != 1:
        return {"font": fname, "reason": f"marker shaped to {len(base)} glyphs", "boxes": {}}
    base_gid = base[0][0].codepoint
    base_name = order[base_gid]
    base_bounds = gbounds(base_gid)
    base_adv = base[0][1].x_advance

    res = {
        "font": fname,
        "instance_wght": wght,
        "upem": tt["head"].unitsPerEm,
        "marker_glyph": base_name,
        "marker_bounds": [round(v, 1) for v in base_bounds] if base_bounds else None,
        "marker_advance": base_adv,
        "boxes": {},
    }
    if base_bounds is None:
        res["reason"] = "marker glyph has no outline"
        return res
    base_contours = contour_boxes(glyphset, base_name)

    for n, digits in DIGITS.items():
        glyphs = shape(data, AYAH + digits)
        # pen positions, left to right
        x = 0.0
        placed = []
        for info, pos in glyphs:
            placed.append((order[info.codepoint], info.codepoint, x + pos.x_offset, pos.y_offset))
            x += pos.x_advance

        marker = [g for g in placed if name_base(g[0]) == name_base(base_name)]
        number = [g for g in placed if name_base(g[0]) != name_base(base_name)]

        if len(placed) == 1 and not marker:
            # precomposed: diff the composed glyph's contours against the bare marker
            name = placed[0][0]
            tol = 0.01 * (base_bounds[2] - base_bounds[0])
            extra = [
                b for b in contour_boxes(glyphset, name)
                if not any(_close(b, c, tol) for c in base_contours)
            ]
            if not extra:
                res["boxes"][n] = {"enclosed": False, "reason": "composed glyph adds no contour"}
                continue
            box = None
            for b in extra:
                box = union(box, b)
            res["boxes"][n] = {
                "mechanism": "precomposed",
                "ring_glyph": name,
                "ring_alternate": True,
                "candidates": [[round(v, 1) for v in box]],
            }
            continue

        if not marker or not number:
            res["boxes"][n] = {"enclosed": False, "reason": "no separate number glyphs"}
            continue

        # THE TEST FOR ENCLOSURE. A font that implements U+06DD gives the digit
        # glyphs essentially no advance of their own -- they ride on the marker.
        # A font that does not simply appends them at full width. Measured over
        # all 26 source families the two cases do not overlap: enclosing fonts
        # spend 0-12% of the marker's advance on the digits (Alkalami's three
        # digits total 145 of 1250), non-enclosing ones spend 100-130% (Mada
        # 1491 of 1276, the Uthmanic family exactly 100%). The threshold sits in
        # an empty band, so this is a proof rather than a prior.
        spend = sum(abs(p.x_advance) for _, p in glyphs
                    if name_base(order[_.codepoint]) != name_base(base_name))
        if spend > 0.20 * abs(base_adv):
            res["boxes"][n] = {
                "enclosed": False,
                "reason": f"digits carry their own advance ({spend:.0f} of {base_adv})",
            }
            continue

        mx = marker[0][2]
        ring_name = marker[0][0]
        box = None
        for name, gid, gx, gy in number:
            b = gbounds(gid)
            if b:
                box = union(box, (b[0] + gx, b[1] + gy, b[2] + gx, b[3] + gy))
        if box is None:
            res["boxes"][n] = {"enclosed": False, "reason": "number glyphs draw nothing"}
            continue
        cands = []
        for shift in (0.0, base_adv, -base_adv):
            cands.append([round(box[0] - mx + shift, 1), round(box[1], 1),
                          round(box[2] - mx + shift, 1), round(box[3], 1)])
        res["boxes"][n] = {
            "mechanism": "ring-alternate" if ring_name != base_name else "positioned-digits",
            "ring_glyph": ring_name,
            "ring_alternate": ring_name != base_name,
            "candidates": cands,
        }
    return res


# ------------------------------------------------------ font -> SVG registration

def ink_grid(path):
    """The marker's ink, rasterised as a renderer would draw it."""
    import numpy as np

    from derive_number_box import GRID, nonzero_mask, read_marker

    vb, contours = read_marker(path)
    x0, y0, w, h = vb
    step = max(w, h) / GRID
    xs = np.arange(x0, x0 + w + step, step)
    ys = np.arange(y0, y0 + h + step, step)
    return xs, ys, nonzero_mask(contours, xs, ys)


def ink_coverage(grid, box):
    import numpy as np

    xs, ys, ink = grid
    ix = (xs >= box["cx"] - box["width"] / 2) & (xs <= box["cx"] + box["width"] / 2)
    iy = (ys >= box["cy"] - box["height"] / 2) & (ys <= box["cy"] + box["height"] / 2)
    sub = ink[np.ix_(iy, ix)]
    return float(sub.mean()) if sub.size else 1.0


def svg_bbox(path):
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from derive_number_box import read_marker

    vb, contours = read_marker(path)
    xs = [c[:, 0] for c in contours]
    ys = [c[:, 1] for c in contours]
    return (
        min(x.min() for x in xs), min(y.min() for y in ys),
        max(x.max() for x in xs), max(y.max() for y in ys),
    )


def register(font_bounds, svg):
    """Find the transform from font units to SVG units. Returns (fn, flip, err)."""
    fx0, fy0, fx1, fy1 = font_bounds
    sx0, sy0, sx1, sy1 = svg
    fw, fh = fx1 - fx0, fy1 - fy0
    sw, sh = sx1 - sx0, sy1 - sy0
    if fw <= 0 or fh <= 0:
        return None, None, 1e9
    s = ((sw / fw) + (sh / fh)) / 2
    best = None
    for flip in (False, True):
        # x maps directly; y either directly or mirrored
        tx = sx0 - s * fx0
        ty = sy0 - s * (-fy1) if flip else sy0 - s * fy0
        def make(s=s, tx=tx, ty=ty, flip=flip):
            return lambda x, y: (s * x + tx, s * (-y if flip else y) + ty)
        fn = make()
        p0 = fn(fx0, fy1 if flip else fy0)
        p1 = fn(fx1, fy0 if flip else fy1)
        err = max(abs(p0[0] - sx0), abs(p0[1] - sy0), abs(p1[0] - sx1), abs(p1[1] - sy1))
        if best is None or err < best[2]:
            best = (fn, flip, err)
    return best


def fits(box, hole, slack):
    """Does the number box land in the marker's hole (with slack)?"""
    hw = (hole[2] - hole[0]) * slack
    hh = (hole[3] - hole[1]) * slack
    return (
        box[0] >= hole[0] - hw and box[1] >= hole[1] - hh
        and box[2] <= hole[2] + hw and box[3] <= hole[3] + hh
    )


def main():
    coll = json.load(open(os.path.join(ROOT, "collection.json")))
    geo = json.load(open(os.path.join(ROOT, "scripts", "_number_boxes.json")))
    out = {}
    for m in coll["markers"]:
        src = m["sources"][0]
        fam = src["family"]
        weight = int(src["variant"]) if str(src.get("variant", "")).isdigit() else None
        try:
            meas = measure(fam, weight)
        except Exception as exc:  # noqa: BLE001
            out[m["id"]] = {"family": fam, "reason": f"{type(exc).__name__}: {exc}", "boxes": {}}
            continue
        rec = {"family": fam, "variant": weight, **meas}
        hole = geo[m["id"]]["_free_bbox"]
        if meas.get("marker_bounds"):
            grid = ink_grid(os.path.join(ROOT, m["file"]))
            sb = svg_bbox(os.path.join(ROOT, m["file"]))
            fn, flip, err = register(meas["marker_bounds"], sb)
            rec["svg_bbox"] = [round(v, 1) for v in sb]
            rec["registration"] = {"flip_y": flip, "max_error": round(float(err), 2)}
            if err < 2.0:
                for n, b in list(meas["boxes"].items()):
                    if "candidates" not in b:
                        continue
                    best = None
                    for cand in b["candidates"]:
                        x0, y0 = fn(cand[0], cand[1])
                        x1, y1 = fn(cand[2], cand[3])
                        sbox = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
                        if fits(sbox, hole, 0.10):
                            # prefer the candidate best centred in the hole
                            d = abs((sbox[0] + sbox[2]) / 2 - (hole[0] + hole[2]) / 2)
                            if best is None or d < best[0]:
                                best = (d, sbox)
                    if best is None:
                        b["enclosed"] = False
                        b["reason"] = "the number does not land in the marker's hole"
                        continue
                    _, sbox = best
                    cand_svg = {
                        "cx": round((sbox[0] + sbox[2]) / 2, 1),
                        "cy": round((sbox[1] + sbox[3]) / 2, 1),
                        "width": round(sbox[2] - sbox[0], 1),
                        "height": round(sbox[3] - sbox[1], 1),
                    }
                    # A font may swap in a WIDER ring for a longer number
                    # (Alkalami's `uni06DD.3`). The box then belongs to a glyph
                    # we do not ship, and can land on our outline's ink. Check it
                    # against the artwork and refuse it if it collides -- the
                    # geometric derivation takes over for that digit count.
                    cov = ink_coverage(grid, cand_svg)
                    if cov > 0.005:
                        b["enclosed"] = False
                        b["reason"] = (
                            f"the font's box for {n} digits belongs to a wider ring "
                            f"({b.get('ring_glyph')}) and covers {cov * 100:.0f}% ink "
                            f"on the outline we ship"
                        )
                        b.pop("candidates", None)
                        continue
                    b["enclosed"] = True
                    b["ink_coverage"] = round(cov, 4)
                    b["svg"] = cand_svg
                    b.pop("candidates", None)
            else:
                rec["reason"] = f"outline does not register onto the font glyph (err {err:.1f})"
        rec["enclosed_counts"] = sum(1 for b in rec["boxes"].values() if b.get("enclosed"))
        out[m["id"]] = rec
        b3 = rec["boxes"].get(3, {})
        print(
            f"{m['id']:22s} {fam:22s} {meas.get('font',''):34s} "
            f"enc={rec['enclosed_counts']}/3 mech={b3.get('mechanism','-'):18s} "
            f"svg3={b3.get('svg')}",
            file=sys.stderr,
        )
    with open(os.path.join(ROOT, "scripts", "_number_font.json"), "w") as f:
        json.dump(out, f, indent=2)


if __name__ == "__main__":
    main()
