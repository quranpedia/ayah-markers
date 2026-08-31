#!/usr/bin/env python3
"""Materialize an Ayah Marker JSON export into this repository."""
from __future__ import annotations
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

WEIGHT_ORDER = ["thin", "extralight", "light", "regular", "medium", "semibold",
                "bold", "extrabold", "black", "regular-bold", "regular-black"]

def main(selection_path: str, source_manifest_path: str) -> None:
    selection = json.loads(Path(selection_path).read_text(encoding="utf-8"))
    source_manifest = json.loads(Path(source_manifest_path).read_text(encoding="utf-8"))
    by_id = {marker["id"]: marker for marker in source_manifest["markers"]}
    output = ROOT / "markers"; output.mkdir(parents=True, exist_ok=True)

    # One number per design group, densely renumbered from the gappy upstream
    # group numbers, and the weight tells the variants of a group apart. The id
    # IS the file name, so the number a reader sees in the demo, in the file
    # list and in `collection.json` is always the same number.
    upstream = [selected["id"] for selected in selection["selected"]]
    groups = {group: f"{index + 1:03d}" for index, group
              in enumerate(sorted({mid.split("-")[0] for mid in upstream}))}
    def marker_id(mid):
        group, _, weight = mid.partition("-")
        return f"{groups[group]}-{weight}"
    def order(mid):
        group, _, weight = mid.partition("-")
        return groups[group], WEIGHT_ORDER.index(weight) if weight in WEIGHT_ORDER else len(WEIGHT_ORDER)

    markers = []
    for index, upstream_id in enumerate(sorted(upstream, key=order)):
        source = by_id[upstream_id]
        destination = output / f"{marker_id(upstream_id)}.svg"
        shutil.copy2(Path(source_manifest_path).parent / source["file"], destination)
        markers.append({"id": marker_id(upstream_id), "codepoint": f"U+{0xE000 + index:04X}",
                        "file": str(destination.relative_to(ROOT)), "width": source["width"],
                        "upem": source["upem"], "sources": source["sources"]})
    manifest = {"name": "Ayah Markers", "character": "۝", "character_codepoint": "U+06DD",
                "selection_count": len(markers), "markers": markers}
    (ROOT / "collection.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Imported {len(markers)} selected SVGs.")

if __name__ == "__main__":
    if len(sys.argv) != 3: raise SystemExit("Usage: import_selection.py SELECTION_JSON SOURCE_MANIFEST")
    main(sys.argv[1], sys.argv[2])
