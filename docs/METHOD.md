# How the markers are built

Reference for anyone working on this repository. Consumers want
[README.md](../README.md) and [USAGE.md](USAGE.md); nothing here is needed to
use a marker.

## Where the ayah number goes

A marker holds the ayah number **inside** it, and centring the number on the
marker's overall bounding box gets it wrong whenever the design is not
symmetric. `011-regular-bold` is a disc with a flourish hanging below it, so the
bbox centre lands 174 units low, on the join between disc and flourish, instead
of in the disc.

Every marker in `collection.json` therefore carries a `number` block, in the
same coordinate space as its outline:

```json
"number": { "cx": 862.5, "cy": 601.5, "width": 730.0, "height": 305.0, "r": 483.8 }
```

Five numbers, and no second opinion among them: where the centre is, how much
room there is, and nothing about where those came from. The provenance used to
be recorded per marker — `source`, `derived`, `placement`, `font` — and was
dropped once every centre had been placed by hand and the box had stopped being
a size instruction. The rest of this file is that provenance, told once.

- `cx`, `cy` — where to centre the numeral. One centre per marker: the number
  sits in the same place whether it is one digit or three.
- `width`, `height` — the widest box the marker holds, which is the three-digit
  case. It is there so a placement can be checked against the marker's own ink,
  not as an instruction about size. **Do not stretch a numeral to `width`** — a
  one-digit number would come out around 2.7× too wide. Size it by `height`,
  which barely varies with the digit count, and centre it.
- `r` — radius of the largest circle inscribed in the marker's interior, for
  consumers that want a circular badge rather than a box.

### `font-shaping`: the type designer already answered

U+06DD ARABIC END OF AYAH is a prefixed format control — it is defined to
enclose the digits that follow it — and 9 of the 26 source families implement
that in OpenType. Shaping `U+06DD` + digits in the real font shows exactly where
the digits land and how big they are drawn, which is the designer's own answer.
Three mechanisms appear, and all three are read:

| mechanism | what the font does | example |
| --- | --- | --- |
| `positioned-digits` | digit glyphs with no advance, offset onto the marker | Estedad, Amiri, `uni0667.small` |
| `ring-alternate` | as above, plus a wider ring as the number grows | Noto Sans Arabic `uni06DD.2`, `AyahEnd.alt3` |
| `precomposed` | the whole run becomes one glyph that already contains the number | DigitalKhatt V1 `endofaya255` |

A font counts as enclosing only when the digits carry essentially no advance of
their own. Over the 26 families the two cases do not overlap: enclosing fonts
spend 0–12% of the marker's advance on the digits, non-enclosing ones 100–130%.

24 of the 47 markers get their box this way; `001-regular` is a 25th whose
answer had to be refused — see the exception below.

### `derived`: the geometry, for the fonts that stay silent

For the other 23 markers the box is computed from the outline:

1. Rasterise the marker's path with the nonzero winding rule — the ink.
2. Any non-ink area that does not reach the outside of the drawing is an
   enclosed region, a counter of the design. A number can only live in one.
3. Pick the counter that overlaps the `fill-base` region named in
   `annotations.json` — that annotation already identifies the enclosed interior
   of the main body. Falling back, in order, to the `generatedFills` ellipse
   recorded for `fill-base` (the `012` family, which has no interior contour),
   then to the largest counter, then to the bounding box.
4. `cx, cy` is the **centre of that region**; `r` is the largest circle
   inscribed in it.
5. `width, height` scale with the digit count, using the ratios the designers
   who did answer actually use.

Two of those steps were decided by measurement against the 24 markers whose font
states the answer, not by taste:

- **Centre.** The centre of the region beats the centre of the largest inscribed
  circle: horizontal error median 0.4% of the region's width against 1.8%, mean
  0.6% against 6.0%, worst case 2.5% against 14.5%. The two differ only where an
  ornament intrudes on one side — the `004`, `007` and `008` families draw dots
  inside the ring — and there the designers never once agreed with the inscribed
  circle.
- **Size.** A designer draws the number at a near-constant 0.39–0.41 of the
  region's height whatever the digit count, and at 0.77 of its width for the
  three-digit case the box records. Those medians size a derived box, and a
  derived box is never allowed to exceed the largest rectangle that actually
  fits the region.

The derived centre then agrees with the designers to a median 0.5% of the region
horizontally and 2% vertically.

### Exceptions

`001-regular` (Alkalami) is the one marker whose font answer had to be refused.
Alkalami swaps in a wider ring (`uni06DD.2`, `uni06DD.3`) for two and three
digits, and that wider ring's number box covers 15% ink on the outline this
repository ships. Its box falls back to the derived rule, and the build prints
that refusal when it runs.

`scripts/number_exceptions.json`, if present, is reported by the build rather
than written into `collection.json`.

### Hand-placed centres

The box above is computed and never touched. The **centres** are not: every
one of the 47 markers was centred by eye on the placement sheet, and those
centres are the product this repository ships.

They live in `scripts/number_placement.json`, one centre per marker — the number
sits in the same place at any digit count, so there is one entry, not three:

```json
"011-regular-bold": { "cx": 862.5, "cy": 601.5 }
```

`build_number_boxes.py` applies that file last. It moves the centre and never
resizes a box, so the computed width and height survive intact. Delete an entry
and that marker falls back to its computed centre; delete the file and the whole
collection does.

The centres are set in [number-placement.html](number-placement.html):
click a part of a marker to select it, centre the number on that part's bounds
horizontally, vertically or both, and the sheet saves each placement to the
browser as you go. **Copy JSON patch** emits the entry for the selected marker
in the shape above.

### Checking it

```sh
python3 scripts/fetch_source_fonts.py        # the real TTF/OTFs, not the woff2 subsets
python3 scripts/derive_number_box.py         # the geometric rule
python3 scripts/derive_number_font.py        # the fonts' own answer
python3 scripts/build_number_boxes.py        # merge into collection.json + the sheets
python3 scripts/check_number_boxes.py        # gate: no box may sit on ink
```

`check_number_boxes.py` rasterises every marker and measures how much of each
recorded box is covered by the marker's own ink. All 47 boxes pass, and since
the centres were placed by hand none of them touches ink at all.

Two contact sheets render the result:

- [number-placement.html](number-placement.html) — all 47 markers with
  one, two and three digits drawn in the one recorded box, labelled with the
  the family it came from. This is also the editor the centres are set in.
- [number-placement-baseline.html](number-placement-baseline.html) —
  the derived centre against the naive bounding-box centre. They agree on 32
  markers, as they should for a symmetric design, and disagree by up to 174 units
  on the rest.

> **Note on orientation.** The files in `markers/` are the fonts' U+06DD outlines
> with the y axis *not* flipped, so they render vertically mirrored relative to
> the source font — `011`'s flourish is above the disc in Noto Nastaliq Urdu and
> below it in the SVG. That is a pre-existing property of the artwork and nothing
> here changes it; the `number` boxes are in the SVG's own space, so they land
> correctly on the marker as shipped.

## Run it locally

```sh
python3 -m http.server 8000   # then open localhost:8000/demo/
```

## Build

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/build_layered_markers.py  # re-layer markers/ from annotations.json
.venv/bin/python scripts/build_selected_font.py    # OTF, TTF, font map
```

## Layout

```text
markers/          the markers, layered: one <g> per colour part, CSS variables
annotations.json  which contour belongs to which part, the record the layering is built from
collection.json   order, sizes, number placement, source attribution and licences
scripts/number_placement.json
                  the hand-placed number centres the build applies
LICENSES.md       the source families' terms, in full
demo/             the customizer
dist/             OTF, TTF, font map
scripts/          collection and font build tools
```
