# Ayah Markers

A practical collection of Arabic end-of-ayah marks (`۝`, U+06DD) prepared as:

- 47 selected, source-preserving SVG markers;
- themed SVGs with a small, consistent colour contract;
- a Private Use Area TrueType font; and
- a browser demo for previewing and theming the visual parts.

The collection is assembled from Arabic-script Google Fonts and fonts.quran.ws. Gulzar is intentionally excluded.

## Start here

The project has no JavaScript build step. Serve the repository root:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
python3 -m http.server 8000
```

Then open:

- [Demo](http://localhost:8000/demo/) — choose and theme a marker.

## Use an SVG

Use files in `assets/standardized/` for a safe one-colour version, or use the demo's generated SVG output after a marker has been annotated. The marker's available colour classes are determined by its annotation; unused controls are deliberately hidden. The demo copies a ready-to-paste CSS block for the active marker.

```css
:root {
  --fill-base: #f8f0df;
  --fill-1: #d7b27a;
  --ink-base: #18322b;
  --ink-1: #216451;
  --mark-1: #c9792f;
}
```

The full layer contract is documented in [docs/USAGE.md](docs/USAGE.md).

## Use the font

Both `dist/AyahMarkers.otf` (CFF OpenType, cubic curves) and `dist/AyahMarkers.ttf` (TrueType, quadratic curves) contain one marker per Private Use Area codepoint, starting at U+E000. The exact, generated mapping is in `dist/font-map.json`.

```css
@font-face {
  font-family: "Ayah Markers";
  src: url("./dist/AyahMarkers.otf") format("opentype");
}
.ayah-mark { font-family: "Ayah Markers"; }
```

```html
<!-- First marker: U+E000 -->
<span class="ayah-mark">&#xE000;</span>
```

Rebuild it after changing `collection.json`:

```sh
python3 scripts/build_selected_font.py
```

## Repository layout

| Path | Purpose |
| --- | --- |
| `assets/markers/` | Original selected outlines, retained without visual rewriting. |
| `assets/standardized/` | Safe standardized wrappers and the gallery manifest. |
| `annotations.json` | Reviewed per-contour colour assignments and generated interior fills. |
| `collection.json` | The marker inventory, sources, dimensions, and font order. |
| `dist/` | Generated font and PUA mapping. |
| `demo/` | Interactive theme preview. |
| `scripts/` | Collection, standardization, and font-build utilities. |

## Maintain the collection

```sh
# Regenerate standardized SVG wrappers and their manifest
python3 scripts/standardize_svgs.py

# Build the selected PUA font and dist/font-map.json
python3 scripts/build_selected_font.py

# Run the lightweight regression check
python3 -m pytest -q
```

`annotations.json` stores the reviewed part assignments used by the demo.

## Licensing and attribution

Each outline remains derived from its source font. Review the source font's licence, attribution, and Reserved Font Name requirements before redistributing a modified font. Source metadata is preserved for every selected marker in `collection.json`; this repository does not grant a licence to the underlying outlines.
