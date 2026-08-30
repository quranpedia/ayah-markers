#!/usr/bin/env python3
"""Convert selected SVGs to a shared, editable five-part marker contract."""
from __future__ import annotations
import json
import re
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET
from fontTools.pens.boundsPen import BoundsPen
from fontTools.svgLib.path import parse_path

ROOT = Path(__file__).resolve().parents[1]
PARTS = ("fill-base", "fill-1", "fill-2", "fill-3", "ink-base", "ink-1", "ink-2", "ink-3", "mark-1", "mark-2", "mark-3")
LEGACY_TO_CLASS = {"frame": "fill-base", "center": "fill-1", "main-ink": "ink-base", "ornament": "ink-1", "dots": "mark-1"}
SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

def bounds(path: str):
    pen = BoundsPen(None)
    try: parse_path(path, pen)
    except Exception: return None
    return pen.bounds

def split_subpaths(path: str):
    return re.findall(r"M[^M]*", path)

def classify(paths: list[str]):
    """Assign disconnected outlines to portable semantic layers.

    This conservative geometry pass identifies a full-size enclosure and tiny
    detached dot-like pieces; all remaining drawing stays editable as main ink.
    The manifest records the result for later hand-tuning.
    """
    entries = [(path, bounds(path)) for path in paths]
    valid = [box for _, box in entries if box]
    if not valid: return {"main-ink": paths}
    x0, y0 = min(box[0] for box in valid), min(box[1] for box in valid)
    x1, y1 = max(box[2] for box in valid), max(box[3] for box in valid)
    full_w, full_h = max(x1 - x0, 1), max(y1 - y0, 1); full_area = full_w * full_h
    result = defaultdict(list); frame_taken = False
    for path, box in entries:
        if not box: result["main-ink"].append(path); continue
        bx0, by0, bx1, by1 = box; width, height = bx1 - bx0, by1 - by0
        area = width * height
        covers = width / full_w > .88 and height / full_h > .88
        centered = abs((bx0 + bx1) / 2 - (x0 + x1) / 2) < full_w * .12 and abs((by0 + by1) / 2 - (y0 + y1) / 2) < full_h * .12
        if covers and not frame_taken:
            result["frame"].append(path); frame_taken = True
        elif area / full_area < .018:
            result["dots"].append(path)
        elif centered and area / full_area < .15:
            result["center"].append(path)
        else:
            result["main-ink"].append(path)
    return {LEGACY_TO_CLASS[name]: values for name, values in result.items()}

def contains(outer, inner):
    return outer[0] <= inner[0] and outer[1] <= inner[1] and outer[2] >= inner[2] and outer[3] >= inner[3] and outer != inner

def classify_layers(paths: list[str]):
    """Classify complete contour compounds while preserving counters/holes."""
    contours = [{"path": path, "box": bounds(path)} for raw in paths for path in split_subpaths(raw)]
    contours = [item for item in contours if item["box"]]
    if not contours: return {"main-ink": paths}
    for item in contours:
        parents = [other for other in contours if contains(other["box"], item["box"])]
        item["parent"] = min(parents, key=lambda other: (other["box"][2]-other["box"][0])*(other["box"][3]-other["box"][1]), default=None)
    roots = [item for item in contours if item["parent"] is None]
    x0, y0 = min(x["box"][0] for x in contours), min(x["box"][1] for x in contours)
    x1, y1 = max(x["box"][2] for x in contours), max(x["box"][3] for x in contours)
    full_w, full_h = max(x1-x0, 1), max(y1-y0, 1); full_area = full_w * full_h
    def descendants(root):
        found = [root]; changed = True
        while changed:
            changed = False
            for item in contours:
                if item not in found and item["parent"] in found: found.append(item); changed = True
        return found
    result = defaultdict(list)
    for root in roots:
        bx0, by0, bx1, by1 = root["box"]; width, height = bx1-bx0, by1-by0; area = width*height
        children = [item for item in contours if item["parent"] is root]
        central = abs((bx0+bx1)/2-(x0+x1)/2) < full_w*.15 and abs((by0+by1)/2-(y0+y1)/2) < full_h*.15
        compound = "".join(item["path"] for item in descendants(root))
        if area / full_area < .025:
            part = "dots"
        elif width/full_w > .82 and height/full_h > .82 and children:
            part = "frame"
            # The largest directly-contained contour is the editable centre;
            # keep it in frame too so even-odd filling retains the cut-out.
            center = max(children, key=lambda item: (item["box"][2]-item["box"][0])*(item["box"][3]-item["box"][1]))
            result["center"].append("".join(item["path"] for item in descendants(center)))
        elif (by1-y0 < full_h*.32 or y1-by0 < full_h*.32) and width/full_w > .35:
            part = "ornament"
        elif central or area / full_area > .12:
            part = "main-ink"
        else:
            part = "ornament"
        result[part].append(compound)
    # `classify_layers` works in descriptive legacy names.  Translate them
    # before writing so no contour is silently omitted from the standard SVG.
    return {LEGACY_TO_CLASS.get(name, name): values for name, values in result.items()}

def main():
    collection = json.loads((ROOT / "collection.json").read_text(encoding="utf-8"))
    output = ROOT / "assets/standardized"; output.mkdir(parents=True, exist_ok=True)
    records = []
    for marker in collection["markers"]:
        source = ROOT / marker["file"]; root = ET.fromstring(source.read_text(encoding="utf-8"))
        all_paths = [element.attrib.get("d", "") for element in root.findall(f"{{{SVG_NS}}}path")]
        # Keep the original compound paths intact by default.  Splitting a
        # compound path can turn its counters into filled shapes (notably
        # 019-regular's ornament).  The annotation tool supplies the precise
        # per-contour classes when a marker has been reviewed; unreviewed SVGs
        # remain an accurate, single-colour ink layer.
        layers = {"ink-base": all_paths}
        svg = ET.Element(f"{{{SVG_NS}}}svg", {"viewBox": root.attrib["viewBox"], "class": "ayah-marker", "data-marker": marker["id"]})
        for part in PARTS:
            group = ET.SubElement(svg, f"{{{SVG_NS}}}g", {"data-part": part, "style": f"fill:var(--{part},currentColor)"})
            for path in layers.get(part, []): ET.SubElement(group, f"{{{SVG_NS}}}path", {"d": path})
        file = output / f"{marker['id']}.svg"; ET.ElementTree(svg).write(file, encoding="unicode", xml_declaration=False)
        records.append({"id": marker["id"], "file": str(file.relative_to(ROOT)), "parts": {part: bool(layers.get(part)) for part in PARTS}})
    (output / "manifest.json").write_text(json.dumps({"parts": list(PARTS), "markers": records}, indent=2) + "\n", encoding="utf-8")
    print(f"Standardized {len(records)} SVGs into {output}.")

if __name__ == "__main__": main()
