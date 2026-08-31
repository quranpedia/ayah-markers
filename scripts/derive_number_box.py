#!/usr/bin/env python3
"""Derive the number placement box for every marker.

A marker holds the ayah number inside it. Centring the numeral on the marker's
overall bounding box is wrong whenever the design is asymmetric: 014's disc has
a pendant flourish hanging below it, so the bbox centre lands on the join
between disc and flourish rather than in the disc where the number belongs.

THE RULE, derived from the geometry rather than measured by hand:

  1. Rasterise the marker's single `<path>` exactly as a renderer would --
     nonzero winding, since no file sets `fill-rule`. That gives the INK.
  2. Everything that is not ink and does not touch the outside of the drawing is
     an ENCLOSED EMPTY REGION -- a counter of the design. A numeral can only
     live in one of those.
  3. `fill-base` in `annotations.json` already names the enclosed interior of
     the main body, which is exactly where the number belongs. So: pick the
     enclosed empty region that overlaps the `fill-base` region most.
  4. The number's centre is the CENTRE OF THAT REGION, and `r` is the radius of
     the largest circle inscribed in it. Grow the largest axis-aligned rectangle
     centred on that point that still fits: that is the `width x height` a
     numeral may occupy without touching the ornament.

FALLBACKS, in order:

  a. `fill-base` lists no contour (the 015 family) -> use the `generatedFills`
     ellipse the annotation records for `fill-base` as the region to match.
  b. No enclosed empty region overlaps the chosen region (a design whose base is
     a synthetic shape over solid ink) -> intersect the region itself with the
     non-ink area and use the largest connected piece of that.
  c. No annotated base at all -> the largest enclosed empty region of the whole
     outline.
  d. No enclosed empty region at all -> the outline's bounding-box centre, with
     the box inscribed in the bbox. (Not reached by any marker in this set.)

Why the largest region wins in step 3/c: a marker's counters are its main body
plus small decorative eyes (017 has six ~24k-unit eyes around a 1.5M-unit
body). Area separates them by two orders of magnitude, so "largest" is not a
tie-break, it is a proof.

Output: `number: {cx, cy, width, height, r, source}` per marker, in the same
coordinate space as the outline (viewBox units).
"""

import json
import math
import os
import re
import sys

import numpy as np
from scipy import ndimage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRID = 600  # raster samples across the longer viewBox axis


# ---------------------------------------------------------------- path parsing

TOKEN = re.compile(r"([MmLlHhVvCcQqSsTtZz])|(-?\d*\.?\d+(?:[eE][-+]?\d+)?)")


def _flatten_quad(p0, p1, p2, n=16):
    return [
        (
            (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
            (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1],
        )
        for t in (i / n for i in range(1, n + 1))
    ]


def _flatten_cubic(p0, p1, p2, p3, n=20):
    out = []
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        out.append(
            (
                u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
                u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1],
            )
        )
    return out


def parse_contours(d):
    """Split path data into flattened polygons, one per M-command subpath."""
    toks = TOKEN.findall(d)
    i = 0
    contours, cur = [], []
    pos = (0.0, 0.0)
    start = (0.0, 0.0)
    cmd = None

    def nums(k):
        nonlocal i
        vals = []
        while len(vals) < k:
            c, v = toks[i]
            if c:
                raise ValueError(f"expected number, got {c}")
            vals.append(float(v))
            i += 1
        return vals

    while i < len(toks):
        c, _ = toks[i]
        if c:
            cmd = c
            i += 1
            if cmd.upper() == "Z":
                if cur:
                    cur.append(start)
                    contours.append(cur)
                    cur = []
                pos = start
                continue
        elif cmd is None:
            raise ValueError("path starts with a number")
        rel = cmd.islower()
        C = cmd.upper()
        if C == "M":
            if cur:
                contours.append(cur)
            x, y = nums(2)
            pos = (pos[0] + x, pos[1] + y) if rel else (x, y)
            start = pos
            cur = [pos]
            cmd = "l" if rel else "L"
        elif C == "L":
            x, y = nums(2)
            pos = (pos[0] + x, pos[1] + y) if rel else (x, y)
            cur.append(pos)
        elif C == "H":
            (x,) = nums(1)
            pos = (pos[0] + x, pos[1]) if rel else (x, pos[1])
            cur.append(pos)
        elif C == "V":
            (y,) = nums(1)
            pos = (pos[0], pos[1] + y) if rel else (pos[0], y)
            cur.append(pos)
        elif C == "Q":
            x1, y1, x, y = nums(4)
            p1 = (pos[0] + x1, pos[1] + y1) if rel else (x1, y1)
            p2 = (pos[0] + x, pos[1] + y) if rel else (x, y)
            cur.extend(_flatten_quad(pos, p1, p2))
            pos = p2
        elif C == "C":
            x1, y1, x2, y2, x, y = nums(6)
            p1 = (pos[0] + x1, pos[1] + y1) if rel else (x1, y1)
            p2 = (pos[0] + x2, pos[1] + y2) if rel else (x2, y2)
            p3 = (pos[0] + x, pos[1] + y) if rel else (x, y)
            cur.extend(_flatten_cubic(pos, p1, p2, p3))
            pos = p3
        else:
            raise ValueError(f"unsupported command {cmd}")
    if cur:
        contours.append(cur)
    out = []
    for p in contours:
        if len(p) < 3:
            continue
        if p[0] != p[-1]:
            p = p + [p[0]]
        out.append(np.asarray(p, dtype=float))
    return out


def read_marker(path):
    src = open(path).read()
    vb = [float(x) for x in re.search(r'viewBox="([^"]+)"', src).group(1).replace(",", " ").split()]
    ds = re.findall(r'\sd="([^"]+)"', src)
    if len(ds) != 1:
        raise ValueError(f"{path}: expected one path, found {len(ds)}")
    return vb, parse_contours(ds[0])


# ------------------------------------------------------------- rasterisation

def _crossings(poly, xs, ys, signed):
    """Ray-cast crossing counts of one closed polygon over a grid."""
    X, Y = np.meshgrid(xs, ys)
    acc = np.zeros(X.shape, dtype=np.int32)
    ax, ay = poly[:-1, 0], poly[:-1, 1]
    bx, by = poly[1:, 0], poly[1:, 1]
    for x0, y0, x1, y1 in zip(ax, ay, bx, by):
        if y0 == y1:
            continue
        cond = (y0 > Y) != (y1 > Y)
        xint = (x1 - x0) * (Y - y0) / (y1 - y0) + x0
        hit = cond & (X < xint)
        if signed:
            acc += np.where(hit, 1 if y1 > y0 else -1, 0)
        else:
            acc += hit
    return acc


def nonzero_mask(polys, xs, ys):
    """Fill the whole path with the nonzero winding rule, as a renderer does."""
    w = np.zeros((len(ys), len(xs)), dtype=np.int32)
    for p in polys:
        w += _crossings(p, xs, ys, signed=True)
    return w != 0


def evenodd_mask(polys, xs, ys):
    a = np.zeros((len(ys), len(xs)), dtype=np.int32)
    for p in polys:
        a += _crossings(p, xs, ys, signed=False)
    return (a % 2) == 1


def poly_area(p):
    x, y = p[:, 0], p[:, 1]
    return abs(np.dot(x[:-1], y[1:]) - np.dot(x[1:], y[:-1])) / 2.0


def ellipse_poly(cx, cy, rx, ry, n=192):
    t = np.linspace(0, 2 * math.pi, n + 1)
    return np.stack([cx + rx * np.cos(t), cy + ry * np.sin(t)], axis=1)


# --------------------------------------------------------------- the derivation

def component_index(name):
    return int(name.rsplit("-", 1)[1])


def base_polys(marker_id, ann, contours):
    """The polygons of the marker's annotated base region, and where they came from."""
    rec = ann["markers"].get(marker_id)
    if rec:
        fb = rec.get("parts", {}).get("fill-base") or []
        polys = [contours[component_index(n)] for n in fb if component_index(n) < len(contours)]
        if polys:
            return polys, "fill-base"
        gen = (rec.get("generatedFills") or {}).get("fill-base") or []
        polys = [
            ellipse_poly(float(g["cx"]), float(g["cy"]), float(g["rx"]), float(g["ry"]))
            for g in gen
            if g.get("type") == "ellipse"
        ]
        if polys:
            return polys, "generatedFill"
    return [], "none"


def largest_rect(free, ix, iy, step):
    """Largest axis-aligned rectangle inside `free` centred on (ix, iy)."""

    def fits(hw, hh):
        a, b = ix - hw, ix + hw + 1
        c, d = iy - hh, iy + hh + 1
        if a < 0 or c < 0 or b > free.shape[1] or d > free.shape[0]:
            return False
        return free[c:d, a:b].all()

    hw = hh = 0
    grew = True
    while grew:
        grew = False
        if fits(hw + 1, hh):
            hw += 1
            grew = True
        if fits(hw, hh + 1):
            hh += 1
            grew = True
    for _ in range(3):
        while fits(hw + 1, hh):
            hw += 1
        while fits(hw, hh + 1):
            hh += 1
    return (2 * hw + 1) * step, (2 * hh + 1) * step


def derive(marker_id, ann, vb, contours):
    x0, y0, w, h = vb
    x1, y1 = x0 + w, y0 + h
    step = max(w, h) / GRID
    xs = np.arange(x0, x1 + step, step)
    ys = np.arange(y0, y1 + step, step)

    ink = nonzero_mask(contours, xs, ys)
    empty = ~ink
    lab, n = ndimage.label(empty)
    # a region that reaches the edge of the drawing is outside the marker
    border = set(lab[0, :]) | set(lab[-1, :]) | set(lab[:, 0]) | set(lab[:, -1])
    enclosed = [k for k in range(1, n + 1) if k not in border]

    bpolys, source = base_polys(marker_id, ann, contours)
    basemask = evenodd_mask(bpolys, xs, ys) if bpolys else None

    free = None
    if enclosed:
        if basemask is not None:
            overlap = {k: int((basemask & (lab == k)).sum()) for k in enclosed}
            best = max(overlap, key=overlap.get)
            if overlap[best] > 0:
                free = lab == best
        if free is None:
            sizes = {k: int((lab == k).sum()) for k in enclosed}
            best = max(sizes, key=sizes.get)
            free = lab == best
            source = source + "+largest-counter" if basemask is None else source + "+no-counter-overlap"
    if free is None and basemask is not None:
        # the base is a synthetic shape over solid ink (015): use it minus the ink
        cand = basemask & empty
        if cand.any():
            l2, n2 = ndimage.label(cand)
            sizes = ndimage.sum(cand, l2, range(1, n2 + 1))
            free = l2 == (int(np.argmax(sizes)) + 1)
            source += "+region-minus-ink"
    if free is None:
        source = "outline-bbox"
        free = np.ones((len(ys), len(xs)), dtype=bool)

    padded = np.pad(free, 1, constant_values=False)
    dist = ndimage.distance_transform_edt(padded)[1:-1, 1:-1]
    iy, ix = np.unravel_index(np.argmax(dist), dist.shape)
    r = float(dist[iy, ix]) * step

    # WHERE the number goes: the CENTRE OF THE HOLE, not the centre of the
    # largest circle that fits in it. The two differ whenever an ornament
    # intrudes on one side (the 005/008/010 families draw dots inside the ring),
    # and the intruded side pushes the inscribed circle off to the other side.
    #
    # This was decided by measurement, not taste. Against the 24 markers whose
    # own font states where the designer put the number, the horizontal error is
    #
    #     inscribed-circle centre   median 0.018   mean 0.060   max 0.145
    #     hole bounding-box centre  median 0.004   mean 0.006   max 0.025
    #
    # of the hole's width -- an order of magnitude better, and the designers
    # never once agreed with the inscribed circle where the two disagreed.
    # Vertically the two are identical, so nothing is lost.
    fy, fx = np.nonzero(free)
    hx0, hx1 = int(fx.min()), int(fx.max())
    hy0, hy1 = int(fy.min()), int(fy.max())
    tx, ty = (hx0 + hx1) // 2, (hy0 + hy1) // 2
    centre = "hole-centre"
    if not free[ty, tx]:
        # the hole's own centre is covered by ink: fall back to the inscribed one
        tx, ty = int(ix), int(iy)
        centre = "inscribed-circle"
    cx, cy = float(xs[tx]), float(ys[ty])
    bw, bh = largest_rect(free, tx, ty, step)

    fbbox = [
        round(float(xs[hx0]), 1), round(float(ys[hy0]), 1),
        round(float(xs[hx1]), 1), round(float(ys[hy1]), 1),
    ]
    return {
        "cx": round(cx, 1),
        "cy": round(cy, 1),
        "width": round(bw, 1),
        "height": round(bh, 1),
        "r": round(r, 1),
        "source": source,
        "centre": centre,
        "_bbox_cx": round(x0 + w / 2, 1),
        "_bbox_cy": round(y0 + h / 2, 1),
        "_counters": len(enclosed),
        "_free_bbox": fbbox,
    }


def main():
    ann = json.load(open(os.path.join(ROOT, "annotations.json")))
    coll = json.load(open(os.path.join(ROOT, "collection.json")))
    out = {}
    for m in coll["markers"]:
        vb, contours = read_marker(os.path.join(ROOT, m["file"]))
        res = derive(m["id"], ann, vb, contours)
        out[m["id"]] = res
        dx = res["cx"] - res["_bbox_cx"]
        dy = res["cy"] - res["_bbox_cy"]
        print(
            f"{m['id']:22s} {res['source']:22s} c=({res['cx']:8.1f},{res['cy']:8.1f}) "
            f"r={res['r']:7.1f} box={res['width']:7.1f}x{res['height']:7.1f} "
            f"counters={res['_counters']:2d} d=({dx:7.1f},{dy:7.1f})",
            file=sys.stderr,
        )
    with open(os.path.join(ROOT, "scripts", "_number_boxes.json"), "w") as f:
        json.dump(out, f, indent=2)


if __name__ == "__main__":
    main()
