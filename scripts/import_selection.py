#!/usr/bin/env python3
"""Materialize an Ayah Marker JSON export into this repository."""
from __future__ import annotations
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main(selection_path: str, source_manifest_path: str) -> None:
    selection = json.loads(Path(selection_path).read_text(encoding="utf-8"))
    source_manifest = json.loads(Path(source_manifest_path).read_text(encoding="utf-8"))
    by_id = {marker["id"]: marker for marker in source_manifest["markers"]}
    output = ROOT / "markers"; output.mkdir(parents=True, exist_ok=True)
    markers = []
    for index, selected in enumerate(selection["selected"]):
        source = by_id[selected["id"]]
        destination = output / f"{index + 1:03d}-{selected['id']}.svg"
        shutil.copy2(Path(source_manifest_path).parent / source["file"], destination)
        markers.append({"id": selected["id"], "codepoint": f"U+{0xE000 + index:04X}",
                        "file": str(destination.relative_to(ROOT)), "width": source["width"],
                        "upem": source["upem"], "sources": source["sources"]})
    manifest = {"name": "Ayah Markers", "character": "۝", "character_codepoint": "U+06DD",
                "selection_count": len(markers), "markers": markers}
    (ROOT / "collection.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Imported {len(markers)} selected SVGs.")

if __name__ == "__main__":
    if len(sys.argv) != 3: raise SystemExit("Usage: import_selection.py SELECTION_JSON SOURCE_MANIFEST")
    main(sys.argv[1], sys.argv[2])
