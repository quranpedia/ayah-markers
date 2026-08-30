# SVG theming contract

Each reviewed marker can expose only the classes it actually uses. This keeps a simple marker simple and allows ornate markers to have more detail without a different API.

| Class | Intended use |
| --- | --- |
| `fill-base` | Main interior or generated base fill. |
| `fill-1`, `fill-2`, `fill-3` | Additional filled regions, from largest to most decorative. |
| `ink-base` | Primary outline or dominant dark shape. |
| `ink-1`, `ink-2`, `ink-3` | Secondary outline/detail levels. |
| `mark-1`, `mark-2`, `mark-3` | Dots, numerals, or small accent marks. |

The variables are `--fill-base`, `--fill-1`, through to `--mark-3`. The demo shows only variables with visible geometry in the selected marker.

## Annotation data

`annotations.json` identifies source contours in this stable form:

```json
"path-0-contour-3"
```

`parts` assigns a source contour to a colour class. `interiorFills` reuses a closed contour behind the source ink. `generatedFills` is for a deliberate base shape where the original outline has no suitable interior contour; it currently supports standard SVG element names and attributes, for example:

```json
{
  "generatedFills": {
    "fill-base": [
      { "type": "ellipse", "cx": "685", "cy": "257", "rx": "500", "ry": "500" }
    ]
  }
}
```

## Weight families

Markers sharing the numeric prefix are a design family, such as `015-regular-black`, `015-thin`, and `015-light`. The annotator presents one representative design and synchronizes its annotations to all available weights. The demo also falls back to an annotated sibling when a weight has no explicit review record.
