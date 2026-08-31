#!/usr/bin/env python3
"""Write the markers in `markers/` as layered, CSS-colourable SVGs.

A marker comes out of its source font as one path holding every contour of the
glyph. `annotations.json` says which colour part each contour belongs to, and
this script bakes that assignment into the file itself: one `<g>` per part,
carrying `fill:var(--part, <default>)`, so a consumer colours a marker with CSS
and nothing has to be assembled at load time.

Splitting a path naively destroys its counters. A hole and the shape it punches
routinely sit in different parts by design, so every contour of an earlier part
that lies inside one of a part's own contours is re-included in that part's
path, with `fill-rule="evenodd"`, to punch the hole again. This is the same
rule `demo/app.js` applied at runtime before the files carried it themselves.

Every emitted path records the original contour indices it draws, in order, as
`data-contours`. That keeps `path-0-contour-N` in `annotations.json` meaningful
after the file is layered, lets this script run again over its own output, and
lets the font build recover the glyph's exact original outline.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from derive_number_box import parse_contours  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PARTS = ["fill-base", "fill-1", "fill-2", "fill-3", "ink-base", "ink-1", "ink-2"]
# The demo's own palette, so a marker opened on its own still looks like a
# marker. Any of these is overridden by setting the variable in CSS.
DEFAULTS = {
    "fill-base": "#fff8e7", "fill-1": "#f4e9bc", "fill-2": "#d6ad43",
    "fill-3": "#fffdf5", "ink-base": "#083a3a", "ink-1": "#0b7771",
    "ink-2": "#48a39b",
}
UNASSIGNED = "ink-base"


def source_contours(svg):
    """Every contour of the marker, in the glyph's original order.

    Reads a single-path marker and a layered one alike: in a layered file the
    contours are spread over the part groups and the shared ones appear more
    than once, so `data-contours` is what puts them back in order.
    """
    contours = {}
    order = 0
    for path in re.finditer(r"<path\b[^>]*>", svg):
        tag = path.group(0)
        d = re.search(r'\sd="([^"]+)"', tag)
        if not d:
            continue
        subpaths = re.findall(r"[Mm][^Mm]*", d.group(1))
        indices = re.search(r'\sdata-contours="([^"]*)"', tag)
        if indices:
            keys = [int(value) for value in indices.group(1).split()]
        else:
            keys = list(range(order, order + len(subpaths)))
            order += len(subpaths)
        for key, subpath in zip(keys, subpaths):
            contours.setdefault(key, subpath.strip())
    return [contours[key] for key in sorted(contours)]


def interior_point(polygon):
    """A point inside the contour, found the way the demo finds one."""
    xs, ys = polygon[:, 0], polygon[:, 1]
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    for row in range(1, 8):
        for column in range(1, 8):
            point = (x0 + (x1 - x0) * column / 8, y0 + (y1 - y0) * row / 8)
            if inside(polygon, point):
                return point
    return ((x0 + x1) / 2, (y0 + y1) / 2)


def inside(polygon, point):
    """Even-odd point-in-fill for one closed contour."""
    x, y = point
    hits = False
    ax, ay = polygon[:-1, 0], polygon[:-1, 1]
    bx, by = polygon[1:, 0], polygon[1:, 1]
    for x0, y0, x1, y1 in zip(ax, ay, bx, by):
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            hits = not hits
    return hits


def layers(contours, polygons, annotation):
    """Each part's contours, plus the holes it has to punch again."""
    assigned = {}
    for part, ids in (annotation.get("parts") or {}).items():
        for name in ids:
            match = re.fullmatch(r"path-\d+-contour-(\d+)", name)
            if match and int(match.group(1)) < len(contours):
                assigned[int(match.group(1))] = part
    points = [interior_point(polygon) for polygon in polygons]
    parts = [assigned.get(index, UNASSIGNED) for index in range(len(contours))]

    result = []
    for part in PARTS:
        own = [i for i, value in enumerate(parts) if value == part]
        if not own:
            continue
        contained = [
            i for i, value in enumerate(parts)
            if value != part and PARTS.index(value) < PARTS.index(part)
            and any(inside(polygons[o], points[i]) for o in own)
        ]
        holes = [i for i in contained
                 if not any(other != i and inside(polygons[other], points[i])
                            for other in contained)]
        result.append((part, own, holes))
    return result


def generated_shapes(annotation):
    for part, shapes in (annotation.get("generatedFills") or {}).items():
        for shape in shapes:
            attributes = " ".join(f'{name}="{value}"' for name, value
                                  in shape.items() if name != "type")
            yield part, f'<{shape["type"]} {attributes}/>'
    for part, ids in (annotation.get("interiorFills") or {}).items():
        for name in ids:
            yield part, name


def render(view_box, contours, polygons, annotation):
    body = []
    generated = {}
    for part, shape in generated_shapes(annotation):
        generated.setdefault(part, []).append(shape)
    for part, shapes in generated.items():
        body.append(
            f'<g data-part="{part}" data-generated-fill="true" fill-rule="evenodd" '
            f'style="fill:var(--{part},{DEFAULTS[part]})">{"".join(shapes)}</g>'
        )
    for part, own, holes in layers(contours, polygons, annotation):
        indices = own + holes
        d = " ".join(contours[i] for i in indices)
        body.append(
            f'<g data-part="{part}" fill-rule="evenodd" '
            f'style="fill:var(--{part},{DEFAULTS[part]})">'
            f'<path data-contours="{" ".join(str(i) for i in indices)}" d="{d}"/></g>'
        )
    return (f'<svg xmlns="http://www.w3.org/2000/svg" class="ayah-marker" '
            f'viewBox="{view_box}">{"".join(body)}</svg>\n')


def main():
    collection = json.load(open(os.path.join(ROOT, "collection.json")))
    annotations = json.load(open(os.path.join(ROOT, "annotations.json")))["markers"]
    written = 0
    for marker in collection["markers"]:
        path = os.path.join(ROOT, marker["file"])
        svg = open(path).read()
        view_box = re.search(r'viewBox="([^"]+)"', svg).group(1)
        contours = source_contours(svg)
        polygons = parse_contours(" ".join(contours))
        if len(polygons) != len(contours):
            raise SystemExit(f"{marker['id']}: {len(contours)} contours, "
                             f"{len(polygons)} polygons")
        annotation = annotations.get(marker["id"], {})
        output = render(view_box, contours, polygons, annotation)
        if output != svg:
            open(path, "w").write(output)
            written += 1
    print(f"Layered {len(collection['markers'])} markers ({written} changed).")


if __name__ == "__main__":
    main()
