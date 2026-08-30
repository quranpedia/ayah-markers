#!/usr/bin/env python3
"""Extract U+06DD as SVG from Google Fonts Arabic webfont variants."""
from __future__ import annotations
import argparse, hashlib, json, re, shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote_plus
import requests
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

METADATA = "https://fonts.google.com/metadata/fonts"
QURAN_FONTS = "https://fonts.quran.ws/fonts/"
CSS = "https://fonts.googleapis.com/css2?family={}:{}@{}&display=swap"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122 Safari/537.36"
EXCLUDED = {"Gulzar"}

WEIGHT_NAMES = {"100": "thin", "200": "extralight", "300": "light", "400": "regular", "500": "medium", "600": "semibold", "700": "bold", "800": "extrabold", "900": "black"}

def variant_label(variants):
    weights = sorted({re.match(r"\d+", value).group() for value in variants if re.match(r"\d+", value)}, key=int)
    if not weights: return "regular"
    names = [WEIGHT_NAMES.get(weight, weight) for weight in weights]
    label = names[0] if len(names) == 1 else f"{names[0]}-{names[-1]}"
    return label

def work_items():
    data = requests.get(METADATA, headers={"User-Agent": UA}, timeout=60).json()
    return [(x["family"], v) for x in data["familyMetadataList"]
            # This mirrors the Google Fonts catalogue's script=Arab filter.
            # `arabic` is the API's script/subset identifier for that filter.
            if x.get("primaryScript") == "Arab" and x["family"] not in EXCLUDED
            for v in x["fonts"] if not v.endswith("i")]

def quran_items():
    """Read the current public catalogue, avoiding page-template font URLs."""
    html = requests.get(QURAN_FONTS, headers={"User-Agent": UA}, timeout=60).text
    faces = re.findall(r"font-family: '([^']+)';\s*src: url\('([^']+)'\)", html)
    return [(name, requests.compat.urljoin(QURAN_FONTS, url)) for name, url in faces
            if "{" not in url]

def font_url(css):
    blocks = re.split(r"/\* ([^*]+) \*/", css)
    for i in range(1, len(blocks), 2):
        if blocks[i].strip() == "arabic":
            match = re.search(r"url\(([^)]+)\)", blocks[i + 1])
            return match.group(1) if match else None

def extract_binary(source, family, variant, url, cache):
    file = cache / (hashlib.sha256(url.encode()).hexdigest() + Path(url).suffix)
    if not file.exists():
        response = requests.get(url, headers={"User-Agent": UA}, timeout=90); response.raise_for_status(); file.write_bytes(response.content)
    font = TTFont(file)
    glyph = font.getBestCmap().get(0x06DD)
    if not glyph: return {"source": source, "family": family, "variant": variant, "status": "missing", "source_url": url}
    glyphset = font.getGlyphSet(); pen = SVGPathPen(glyphset); glyphset[glyph].draw(pen)
    bounds_pen = BoundsPen(glyphset); glyphset[glyph].draw(bounds_pen)
    width = font["hmtx"].metrics[glyph][0]; upem = font["head"].unitsPerEm
    x0, y0, x1, y1 = bounds_pen.bounds or (0, -upem, width, 0)
    padding = max(x1 - x0, y1 - y0) * 0.06
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0-padding:g} {y0-padding:g} {x1-x0+2*padding:g} {y1-y0+2*padding:g}"><path d="{pen.getCommands() or ""}"/></svg>\n'
    # Hash a translated and uniformly scaled outline. This merges shapes that
    # are visually identical but come from fonts with different UPEMs/metrics.
    recording = DecomposingRecordingPen(glyphset); glyphset[glyph].draw(recording)
    canonical_pen = SVGPathPen(None)
    scale = 1000 / max(x1 - x0, y1 - y0, 1)
    recording.replay(TransformPen(canonical_pen, (scale, 0, 0, scale, -x0 * scale, -y0 * scale)))
    canonical = canonical_pen.getCommands() or ""
    return {"source": source, "family": family, "variant": variant, "status": "found", "hash": hashlib.sha256(canonical.encode()).hexdigest(), "svg": svg, "width": width, "upem": upem, "source_url": url}

def extract_google(item, cache):
    family, variant = item
    weight, italic = re.fullmatch(r"(\d+)(i?)", variant).groups()
    axis, value = ("ital,wght", f"1,{weight}") if italic else ("wght", weight)
    session = requests.Session(); session.headers["User-Agent"] = UA
    url = font_url(session.get(CSS.format(quote_plus(family), axis, value), timeout=45).text)
    if not url: return {"source": "Google Fonts", "family": family, "variant": variant, "status": "no-arabic-binary"}
    return extract_binary("Google Fonts", family, variant, url, cache)

def extract_quran(item, cache):
    return extract_binary("fonts.quran.ws", item[0], "regular", item[1], cache)

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, default=Path("collection")); parser.add_argument("--cache", type=Path, default=Path(".cache/fonts")); parser.add_argument("--workers", type=int, default=8); parser.add_argument("--limit", type=int)
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True); args.cache.mkdir(parents=True, exist_ok=True)
    google = work_items(); quran = quran_items()
    items = [("google", x) for x in google] + [("quran", x) for x in quran]
    items = items[:args.limit] if args.limit else items
    print(f"Examining {len(google)} Google script=Arab variants and {len(quran)} Quran fonts (Gulzar excluded)…", flush=True)
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(extract_google if kind == "google" else extract_quran, item, args.cache) for kind, item in items]
        for n, future in enumerate(as_completed(futures), 1):
            try: results.append(future.result())
            except Exception as error: results.append({"status": "error", "error": str(error)})
            if n % 25 == 0 or n == len(items): print(f"  {n}/{len(items)}", flush=True)
    found = [x for x in results if x["status"] == "found"]; groups = {}
    for x in found: groups.setdefault(x["hash"], []).append(x)
    svgdir = args.output / "svg"; shutil.rmtree(svgdir, ignore_errors=True); svgdir.mkdir()
    markers = []
    for n, (digest, sources) in enumerate(sorted(groups.items()), 1):
        first = sources[0]; filename = f"marker-{n:03d}-{digest[:10]}.svg"; (svgdir / filename).write_text(first["svg"], encoding="utf-8")
        marker_sources = sorted(({k:v for k,v in x.items() if k not in {"svg", "hash", "status"}} for x in sources), key=lambda x: (x["source"], x["family"], x["variant"]))
        markers.append({"file": f"svg/{filename}", "hash": digest, "width": first["width"], "upem": first["upem"], "sources": marker_sources})
    # A group is a font design family; its members are the distinct outlines
    # across that family's weights. An outline shared by several fonts remains
    # one card and is assigned to its first deterministic source family.
    buckets = {}
    for marker in markers:
        primary = marker["sources"][0]
        buckets.setdefault((primary["source"], primary["family"]), []).append(marker)
    groups = []
    for group_number, ((source, family), members) in enumerate(sorted(buckets.items()), 1):
        used_labels = {}
        for marker in members:
            labels = [x["variant"] for x in marker["sources"] if x["source"] == source and x["family"] == family]
            label = variant_label(labels); used_labels[label] = used_labels.get(label, 0) + 1
            suffix = "" if used_labels[label] == 1 else f"-{used_labels[label]}"
            marker["id"] = f"{group_number:03d}-{label}{suffix}"
        members.sort(key=lambda marker: marker["id"])
        groups.append({"id": f"{group_number:03d}", "source": source, "family": family, "members": [marker["id"] for marker in members]})
    (args.output / "manifest.json").write_text(json.dumps({"character":"۝", "codepoint":"U+06DD", "excluded":sorted(EXCLUDED), "sources":{"google_fonts":"script=Arab", "quran_fonts":QURAN_FONTS}, "variants_examined":len(items), "groups":groups, "markers":markers}, indent=2, ensure_ascii=False) + "\n")
    (args.output / "missing.json").write_text(json.dumps([x for x in results if x["status"] != "found"], indent=2, ensure_ascii=False) + "\n")
    print(f"Collected {len(found)} matching variants and {len(markers)} distinct marker outlines.")
if __name__ == "__main__": main()
