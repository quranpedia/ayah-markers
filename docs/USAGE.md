# SVG theming contract

Every marker in `markers/` is layered: one `<g data-part="…">` per colour part, each filled with `var(--part, <default>)`. Colouring a marker is setting those variables on it or on any ancestor; unset variables fall back to the default palette baked into the file. A marker exposes only the parts it actually uses, which keeps a simple marker simple and lets an ornate one carry more detail without a different API.

| Class | Intended use |
| --- | --- |
| `fill-base` | Main interior or generated base fill. |
| `fill-1`, `fill-2`, `fill-3` | Additional filled regions, from largest to most decorative. |
| `ink-base` | Primary outline or dominant dark shape. |
| `ink-1`, `ink-2` | Secondary outline and detail levels, including dots and small accent marks. |

The variables are `--fill-base`, `--fill-1`, `--fill-2`, `--fill-3`, `--ink-base`, `--ink-1`, and `--ink-2`. The demo shows only the variables with visible geometry in the selected marker.

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
