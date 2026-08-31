#!/usr/bin/env python3
"""Build the Ayah Markers PUA TrueType font."""
from __future__ import annotations
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET
from fontTools.fontBuilder import FontBuilder
from fontTools.svgLib.path import parse_path
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.t2CharStringPen import T2CharStringPen

ROOT = Path(__file__).resolve().parents[1]
UPEM = 1000

def glyph_path(path: Path) -> str:
    """The glyph's contours, each once, in their original order.

    The markers are layered for CSS, so a contour that punches a hole in a
    part it does not belong to is drawn in both parts. Feeding those duplicates
    to a pen would double their winding and fill the counters in, so the
    `data-contours` indices the layering records are used to take each contour
    exactly once, back in the order the source font drew them.
    """
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    contours: dict[int, str] = {}
    order = 0
    for element in root.iter("{http://www.w3.org/2000/svg}path"):
        subpaths = re.findall(r"[Mm][^Mm]*", element.attrib.get("d", ""))
        indices = element.attrib.get("data-contours")
        if indices:
            keys = [int(value) for value in indices.split()]
        else:
            keys = list(range(order, order + len(subpaths))); order += len(subpaths)
        for key, subpath in zip(keys, subpaths):
            contours.setdefault(key, subpath)
    return " ".join(contours[key] for key in sorted(contours))


def outline(path: Path, source_upem: int):
    pen = TTGlyphPen(None); scale = UPEM / source_upem
    target = TransformPen(Cu2QuPen(pen, max_err=1.0), (scale, 0, 0, scale, 0, 0))
    parse_path(glyph_path(path), target)
    return pen.glyph()

def cff_outline(path: Path, source_upem: int, width: int):
    """Keep SVG cubic curves when producing the CFF-flavoured OTF."""
    pen = T2CharStringPen(width, None)
    scale = UPEM / source_upem
    target = TransformPen(pen, (scale, 0, 0, scale, 0, 0))
    parse_path(glyph_path(path), target)
    return pen.getCharString()

def main() -> None:
    data = json.loads((ROOT / "collection.json").read_text(encoding="utf-8")); markers = data["markers"]
    names = [".notdef"] + [f"marker{index + 1:03d}" for index in range(len(markers))]
    glyphs = {".notdef": TTGlyphPen(None).glyph()}; metrics = {".notdef": (UPEM, 0)}; cmap = {}
    for index, marker in enumerate(markers):
        name = names[index + 1]; glyphs[name] = outline(ROOT / marker["file"], marker["upem"])
        metrics[name] = (round(marker["width"] * UPEM / marker["upem"]), 0); cmap[0xE000 + index] = name
    font = FontBuilder(UPEM, isTTF=True); font.setupGlyphOrder(names); font.setupCharacterMap(cmap); font.setupGlyf(glyphs); font.setupHorizontalMetrics(metrics); font.setupHorizontalHeader(ascent=800, descent=-200)
    font.setupNameTable({"familyName":"Ayah Markers", "styleName":"Regular", "fullName":"Ayah Markers Regular", "uniqueFontIdentifier":"Ayah Markers Regular", "psName":"AyahMarkers-Regular", "version":"Version 1.0"})
    font.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=1000, usWinDescent=200); font.setupPost(); font.setupMaxp()
    destination = ROOT / "dist/AyahMarkers.ttf"; destination.parent.mkdir(exist_ok=True); font.save(destination)
    font_map = {
        "fonts": ["AyahMarkers.ttf", "AyahMarkers.otf"],
        "unicode_range": f"U+E000–U+{0xE000 + len(markers) - 1:04X}",
        "glyphs": [
            {"marker": marker["id"], "codepoint": f"U+{0xE000 + index:04X}", "character": chr(0xE000 + index)}
            for index, marker in enumerate(markers)
        ],
    }
    (ROOT / "dist/font-map.json").write_text(json.dumps(font_map, indent=2) + "\n", encoding="utf-8")
    cff_glyphs = {".notdef": T2CharStringPen(UPEM, None).getCharString()}
    for index, marker in enumerate(markers):
        width = round(marker["width"] * UPEM / marker["upem"])
        cff_glyphs[names[index + 1]] = cff_outline(ROOT / marker["file"], marker["upem"], width)
    otf = FontBuilder(UPEM, isTTF=False); otf.setupGlyphOrder(names); otf.setupCharacterMap(cmap)
    otf.setupHorizontalMetrics(metrics); otf.setupHorizontalHeader(ascent=800, descent=-200)
    otf.setupNameTable({"familyName":"Ayah Markers", "styleName":"Regular", "fullName":"Ayah Markers Regular", "uniqueFontIdentifier":"Ayah Markers Regular", "psName":"AyahMarkers-Regular", "version":"Version 1.0"})
    otf.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=1000, usWinDescent=200); otf.setupPost(); otf.setupMaxp()
    otf.setupCFF("AyahMarkers-Regular", {"FullName":"Ayah Markers Regular", "FamilyName":"Ayah Markers", "Weight":"Regular", "version":"1.0"}, cff_glyphs, {})
    otf_destination = ROOT / "dist/AyahMarkers.otf"; otf.save(otf_destination)
    print(f"Built {destination} with {len(markers)} marker glyphs (U+E000–U+{0xDFFF + len(markers):04X}).")

if __name__ == "__main__": main()
