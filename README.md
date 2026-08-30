# Ayah Markers

<p align="center">
  <strong>A carefully selected collection of Qur’anic end-of-ayah marks.</strong><br>
  20 designs · 47 weights · layered SVGs you recolour from CSS · OTF and TTF fonts
</p>

<p align="center">
  <a href="https://quranpedia.github.io/ayah-markers/demo/"><strong>Open the live demo →</strong></a> ·
  <a href="dist/AyahMarkers.otf">Download OTF</a> ·
  <a href="dist/AyahMarkers.ttf">Download TTF</a> ·
  <a href="docs/USAGE.md">Read the SVG guide</a>
</p>

---

`۝` **Ayah Markers** is a practical library of **20 end-of-ayah designs in 47 weights**, collected from Arabic-script Google Fonts and fonts.quran.ws. Every marker ships three ways: a source SVG, a safe standardized SVG wrapper, and a glyph in the included Private Use Area font.

The markers are not flat icons. Each one is split into named layers — base fill, inner fills, ink outlines, ornament marks — so a single SVG can be recoloured to match any mushaf, app, or print palette from CSS alone.

> Gulzar is intentionally excluded. Source metadata remains in `collection.json` for every marker.

## What you get

| | |
| --- | --- |
| **20 designs, 47 weights** | Curated shapes, from Thin through Black where the source family provides them. |
| **Interactive demo** | Browse by design, switch weight, recolour live, copy the CSS. |
| **Layered SVGs** | Fills render beneath ink, with interiors correctly cut out — no flat silhouettes. |
| **SVG colour contract** | A consistent set of fill, ink, and mark variables. |
| **OpenType + TrueType** | `AyahMarkers.otf` keeps cubic curves; `AyahMarkers.ttf` maximizes compatibility. |
| **PUA font map** | A generated, stable mapping from U+E000 to U+E02E. |

## Quick start

The demo is published at **[quranpedia.github.io/ayah-markers](https://quranpedia.github.io/ayah-markers/demo/)**. To run it locally:

```sh
git clone https://github.com/quranpedia/ayah-markers.git
cd ayah-markers
python3 -m http.server 8000
```

Open [localhost:8000/demo](http://localhost:8000/demo/).

## Use the SVGs

Open the demo, pick a design, choose its weight, set the colours, then hit **Copy CSS**. You get only the variables that marker actually supports — nothing to trim:

```css
/* 001-regular */
.ayah-marker {
  --fill-base: #fff8e7;
  --fill-1: #f4e9bc;
  --fill-2: #d6ad43;
  --ink-base: #083a3a;
}
```

The default palette is Qur’an-inspired: parchment base fills, deep teal ink, and antique gold details. Drop the SVG in your page, set the variables, and the marker restyles itself — no re-export. See [the full SVG contract](docs/USAGE.md) for every available class.

## Use the font

The font maps markers to the Unicode Private Use Area, starting at U+E000. Use the generated [font map](dist/font-map.json) to select a specific glyph.

```css
@font-face {
  font-family: "Ayah Markers";
  src: url("./AyahMarkers.otf") format("opentype");
}

.ayah-mark { font-family: "Ayah Markers"; }
```

```html
<!-- First marker: U+E000 -->
<span class="ayah-mark">&#xE000;</span>
```

| Download | Format | Best for |
| --- | --- | --- |
| [AyahMarkers.otf](dist/AyahMarkers.otf) | CFF OpenType | Modern design and publishing workflows; retains cubic curves. |
| [AyahMarkers.ttf](dist/AyahMarkers.ttf) | TrueType | Broad platform and webfont-tool compatibility. |

## Repository map

```text
assets/markers/       original selected outlines
assets/standardized/  safe standardized SVG wrappers
annotations.json      reviewed fill / ink / mark assignments
collection.json       marker order, dimensions, and source attribution
dist/                  OTF, TTF, and PUA font-map.json
demo/                  live SVG customizer
scripts/               collection and font build utilities
```

## Build and maintain

```sh
# Optional: only needed for collection and font tooling
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Rebuild standardized SVG wrappers
.venv/bin/python scripts/standardize_svgs.py

# Rebuild both the OTF and TTF, plus the PUA map
.venv/bin/python scripts/build_selected_font.py

# Validate the local project
.venv/bin/python -m pytest -q
```

Every push to `main` deploys the static demo to GitHub Pages.

## Attribution and licensing

The source outlines remain subject to the licences, attribution requirements, and Reserved Font Name terms of their original font families. Before redistributing a modified font, review each source entry in `collection.json`. This repository does not grant a licence to the underlying source outlines.
