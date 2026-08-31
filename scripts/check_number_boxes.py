#!/usr/bin/env python3
"""Gate: every recorded number box must be empty of the marker's own ink.

A centre without a size lets a consumer overflow the ornament, and a size that
is not checked against the artwork is just a number. So this rasterises each
marker exactly as a renderer would and reports, for every digit count, how much
of the recorded box is covered by ink.

Anything above zero is reported. A box is FLAGGED past 0.5% coverage, which is
above the rasteriser's own edge error (a box that merely grazes an outline picks
up a fraction of a percent from antialiasing at this grid).
"""

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from derive_number_box import GRID, nonzero_mask, read_marker  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    coll = json.load(open(os.path.join(ROOT, "collection.json")))
    worst = []
    bad = 0
    for m in coll["markers"]:
        vb, contours = read_marker(os.path.join(ROOT, m["file"]))
        x0, y0, w, h = vb
        step = max(w, h) / GRID
        xs = np.arange(x0, x0 + w + step, step)
        ys = np.arange(y0, y0 + h + step, step)
        ink = nonzero_mask(contours, xs, ys)
        b = m["number"]
        ix = (xs >= b["cx"] - b["width"] / 2) & (xs <= b["cx"] + b["width"] / 2)
        iy = (ys >= b["cy"] - b["height"] / 2) & (ys <= b["cy"] + b["height"] / 2)
        sub = ink[np.ix_(iy, ix)]
        cov = float(sub.mean()) if sub.size else 1.0
        if cov > 0.0:
            worst.append((cov, m["id"], b["source"]))
        if cov > 0.005:
            bad += 1
    worst.sort(reverse=True)
    for cov, mid, src in worst[:20]:
        mark = "FLAG" if cov > 0.005 else "ok  "
        print(f"{mark} {mid:22s} source={src:13s} ink coverage {cov * 100:.2f}%")
    print(f"\n{len(worst)} of {len(coll['markers'])} boxes touch any ink at all; "
          f"{bad} exceed 0.5%")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
