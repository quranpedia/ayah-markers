# SVG theming contract

Every marker in `markers/` is layered: one `<g data-part="…">` per colour part, each filled with `var(--part, <default>)`. Colouring a marker is setting those variables on it or on any ancestor; unset variables fall back to the default palette baked into the file. A marker exposes only the parts it actually uses, which keeps a simple marker simple and lets an ornate one carry more detail without a different API.

| Class | Intended use |
| --- | --- |
| `fill-base` | Main interior or generated base fill. |
| `fill-1`, `fill-2`, `fill-3` | Additional filled regions, from largest to most decorative. |
| `ink-base` | Primary outline or dominant dark shape. |
| `ink-1`, `ink-2` | Secondary outline and detail levels, including dots and small accent marks. |

The variables are `--fill-base`, `--fill-1`, `--fill-2`, `--fill-3`, `--ink-base`, `--ink-1`, and `--ink-2`. The demo shows only the variables with visible geometry in the selected marker.

## How a marker is stored

**The files in `markers/` are layered.** Each one carries one `<g>` per colour
part, filled through a CSS variable with the default palette as its fallback, so
a marker is coloured by setting variables and nothing has to be assembled at
load time:

```svg
<svg class="ayah-marker" viewBox="151.44 -107.56 1421.12 1765.12">
  <g data-part="fill-base" fill-rule="evenodd" style="fill:var(--fill-base,#fff8e7)">
    <path data-contours="3" d="M862 111Q1066 111 …Z"/></g>
  <g data-part="ink-1" fill-rule="evenodd" style="fill:var(--ink-1,#0b7771)">
    <path data-contours="2 3" d="M863 …Z M862 111…Z"/></g>
</svg>
```

```css
.ayah-marker { --fill-base: #fdf6e3; --ink-1: #7b341e; }
```

Opened on its own the file already draws in the default palette; every part
listed in this guide that a marker actually uses appears as a
`data-part` group, and the ones it does not use simply are not there.

The assignment behind the layering is recorded in **`annotations.json`**, which
names each contour of the original glyph by index:

```json
"011-regular-bold": {
  "parts": {
    "fill-base": ["path-0-contour-3"],
    "ink-1":     ["path-0-contour-2"],
    "ink-2":     ["path-0-contour-0"]
  }
}
```

`path-0-contour-N` is the Nth `M`-command subpath of the glyph as the source font
drew it. That file is the editing record — where the colours were decided — and
`scripts/build_layered_markers.py` bakes it into the SVGs. Change an assignment,
re-run the script, and the markers are rewritten.

**Splitting a path naively destroys the counters.** A hole and the shape it
punches routinely sit in different parts by design, so every contour of an
earlier part that lies inside one of a part's own contours is re-included in that
part's path, with `fill-rule="evenodd"`, to punch the hole again. Containment is
decided by real point-in-path testing, not by bounding boxes, which overlap for
concentric ornaments. That is why a contour can appear in two groups, and why
each path lists the original contour indices it draws in `data-contours`: the
glyph's exact outline, each contour once and in its original order, can always be
recovered from the layered file. `scripts/build_selected_font.py` builds the font
that way, and the script is idempotent over its own output.

Two further details worth knowing:

- A contour listed in no part is drawn as `ink-base`.
- The demo (`demo/app.js`) just loads these files and sets variables. It also
  offers **Download SVG**, which writes the marker out with the colours you chose
  substituted for the variables, for a standalone file that needs no CSS.

## Annotation data

`annotations.json` is the record of which contour was assigned to which part; `scripts/build_layered_markers.py` bakes it into the SVGs, so consumers never need to read it. It identifies source contours in this stable form:

```json
"path-0-contour-3"
```

`path-0-contour-N` numbers the `M`-command subpaths of the glyph as the source font drew it; each layered path records the indices it draws in `data-contours`, so the original outline stays recoverable. `parts` assigns a source contour to a colour class. `interiorFills` reuses a closed contour behind the source ink. `generatedFills` is for a deliberate base shape where the original outline has no suitable interior contour; it currently supports standard SVG element names and attributes, for example:

```json
{
  "generatedFills": {
    "fill-base": [
      { "type": "ellipse", "cx": "685", "cy": "257", "rx": "500", "ry": "500" }
    ]
  }
}
```

## Where the number goes

`collection.json` records one `number` per marker: `cx`/`cy` is where to centre the numeral, `width`/`height` is the widest box that marker holds, and `r` is the largest circle inscribed in its interior. Centre the numeral at `cx`/`cy` and choose its size — sizing by `height` is safe at any digit count; stretching a short number to `width` is not, because `width` is the three-digit case.

## Weight families

Markers sharing the numeric prefix are a design family, such as `012-regular-black`, `012-thin`, and `012-light`. Where a weight has no review record of its own, it is layered from an annotated sibling of the same family.

How the number centres and the layer assignments were arrived at is in [METHOD.md](METHOD.md).
