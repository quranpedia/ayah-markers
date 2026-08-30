# Ayah Markers

<p align="center">
  <strong>Qur’anic end-of-ayah marks as layered SVGs and a font.</strong><br>
  20 designs · 47 weights · recolour from CSS
</p>

<p align="center">
  <a href="https://quranpedia.github.io/ayah-markers/demo/"><strong>Open the demo →</strong></a> ·
  <a href="dist/AyahMarkers.otf">OTF</a> ·
  <a href="dist/AyahMarkers.ttf">TTF</a> ·
  <a href="docs/USAGE.md">SVG guide</a>
</p>

---

Each marker is split into named layers — base fill, inner fills, ink outlines, ornament marks — so one SVG restyles itself from CSS variables.

## Use the SVGs

Pick a design in the demo, choose its weight, set the colours, then **Copy CSS**:

```css
/* 001-regular */
.ayah-marker {
  --fill-base: #fff8e7;
  --fill-1: #f4e9bc;
  --fill-2: #d6ad43;
  --ink-base: #083a3a;
}
```

Every available variable is listed in [docs/USAGE.md](docs/USAGE.md).

## Use the font

Markers are mapped to the Private Use Area from U+E000. See [font-map.json](dist/font-map.json) for the glyph you want.

```css
@font-face {
  font-family: "Ayah Markers";
  src: url("./AyahMarkers.otf") format("opentype");
}

.ayah-mark { font-family: "Ayah Markers"; }
```

```html
<span class="ayah-mark">&#xE000;</span>
```

## Run it locally

```sh
python3 -m http.server 8000   # then open localhost:8000/demo/
```

## Build

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/standardize_svgs.py      # standardized SVGs
.venv/bin/python scripts/build_selected_font.py   # OTF, TTF, font map
```

## Licensing

The source outlines keep the licences, attribution requirements, and Reserved Font Name terms of their original families — see `collection.json` before redistributing. This repository does not grant a licence to those outlines.
