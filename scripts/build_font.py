#!/usr/bin/env python3
"""Build a simple TrueType font, mapping each collected marker to U+E000+."""
from __future__ import annotations
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from fontTools.fontBuilder import FontBuilder
from fontTools.svgLib.path import parse_path
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.cu2quPen import Cu2QuPen

ROOT = Path(__file__).resolve().parents[1]; UPEM = 1000

def outline(path, source_upem):
    root = ET.fromstring(path.read_text(encoding="utf-8")); pen = TTGlyphPen(None)
    # TrueType glyf stores quadratic curves; source SVGs may contain cubics.
    destination = TransformPen(Cu2QuPen(pen, max_err=1.0), (UPEM / source_upem, 0, 0, UPEM / source_upem, 0, 0))
    for element in root.findall("{http://www.w3.org/2000/svg}path"):
        parse_path(element.attrib.get("d", ""), destination)
    return pen.glyph()

def main():
    manifest = ROOT / "collection/manifest.json"
    if not manifest.exists(): raise SystemExit("Run scripts/collect.py first.")
    markers = json.loads(manifest.read_text(encoding="utf-8"))["markers"]
    if not markers: raise SystemExit("No markers to build.")
    names = [".notdef"] + [x["id"] for x in markers]; glyphs = {".notdef": TTGlyphPen(None).glyph()}; metrics = {".notdef": (1000, 0)}; cmap = {}
    for index, marker in enumerate(markers):
        name = marker["id"]; glyphs[name] = outline(ROOT / "collection" / marker["file"], marker["upem"])
        metrics[name] = (round(marker["width"] * UPEM / marker["upem"]), 0); cmap[0xE000 + index] = name
    font = FontBuilder(UPEM, isTTF=True); font.setupGlyphOrder(names); font.setupCharacterMap(cmap); font.setupGlyf(glyphs); font.setupHorizontalMetrics(metrics); font.setupHorizontalHeader(ascent=800, descent=-200)
    font.setupNameTable({"familyName":"Ayah Markers", "styleName":"Regular", "fullName":"Ayah Markers Regular", "uniqueFontIdentifier":"Ayah Markers Regular", "psName":"AyahMarkers-Regular", "version":"Version 1.0"})
    font.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=1000, usWinDescent=200); font.setupPost(); font.setupMaxp()
    output = ROOT / "dist/AyahMarkers.ttf"; output.parent.mkdir(exist_ok=True); font.save(output)
    print(f"Built {output} — {len(markers)} variants mapped from U+E000.")
if __name__ == "__main__": main()
