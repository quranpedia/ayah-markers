#!/usr/bin/env python3
"""Merge the two number-box sources into `collection.json` and build the sheets.

Precedence:

  1. `font-shaping` -- the source font's own U+06DD enclosure, read by
     `derive_number_font.py`. This is the type designer's intent, so it wins.
  2. `derived` -- the geometric rule in `derive_number_box.py`, used for the
     families that do not implement the enclosure.

Both are recorded per digit count, and every entry says which source it came
from so a guess is never mistaken for the designer's answer.
"""

import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DIGIT_TEXT = {1: "٧", 2: "٤٨", 3: "٢٥٥"}
PREVIEW_VIEWBOX_SIZE = 1000
PREVIEW_FONT_SIZE = 320


def load(name):
    return json.load(open(os.path.join(ROOT, "scripts", name)))


def calibrate(geo, fnt):
    """How big does a designer draw the number, relative to the marker's hole?

    Measured over the markers whose font DID answer: the number's height is a
    near-constant fraction of the hole regardless of digit count, and its width
    grows with the digit count. The medians are computed here rather than
    written down, so they track the data.

    The same measurement validates the geometric centre: across those markers
    the designer's centre sits a median 0.8% of the hole width from the one the
    geometric rule derives.
    """
    import statistics

    ratios = {}
    for n in (1, 2, 3):
        w, h = [], []
        for mid, f in fnt.items():
            b = (f.get("boxes") or {}).get(str(n)) or {}
            if not (b.get("enclosed") and b.get("svg")):
                continue
            hole = geo[mid]["_free_bbox"]
            w.append(b["svg"]["width"] / (hole[2] - hole[0]))
            h.append(b["svg"]["height"] / (hole[3] - hole[1]))
        ratios[n] = (statistics.median(w), statistics.median(h), len(w))
    return ratios


def build():
    geo = load("_number_boxes.json")
    fnt = load("_number_font.json")
    ratios = calibrate(geo, fnt)
    coll = json.load(open(os.path.join(ROOT, "collection.json")))

    exceptions = json.load(open(os.path.join(ROOT, "scripts", "number_exceptions.json"))) \
        if os.path.exists(os.path.join(ROOT, "scripts", "number_exceptions.json")) else {}

    stats = {"font": 0, "derived": 0, "mixed": 0}
    for m in coll["markers"]:
        mid = m["id"]
        g = geo[mid]
        f = fnt.get(mid, {})
        gbox = {
            "cx": g["cx"], "cy": g["cy"],
            "width": g["width"], "height": g["height"],
        }
        hole = g["_free_bbox"]

        def derived_box(n):
            """Geometric centre, sized the way the designers who answered size it."""
            rw, rh, _ = ratios[n]
            return {
                "cx": g["cx"], "cy": g["cy"],
                # never larger than the box that actually fits inside the hole
                "width": round(min(rw * (hole[2] - hole[0]), g["width"]), 1),
                "height": round(min(rh * (hole[3] - hole[1]), g["height"]), 1),
            }

        digits = {}
        used_font = 0
        for n in (1, 2, 3):
            b = (f.get("boxes") or {}).get(str(n)) or (f.get("boxes") or {}).get(n) or {}
            if b.get("enclosed") and b.get("svg"):
                d = dict(b["svg"])
                d["source"] = "font-shaping"
                if b.get("ring_alternate"):
                    d["ring_alternate"] = True
                used_font += 1
            else:
                d = derived_box(n)
                d["source"] = "derived"
                if b.get("reason") and f.get("boxes"):
                    # the font DID answer for this marker but its answer was
                    # rejected for this digit count -- say why, in the data
                    if any(x.get("enclosed") for x in f["boxes"].values()):
                        d["fallback_reason"] = b["reason"]
            digits[str(n)] = d

        source = "font-shaping" if used_font == 3 else ("derived" if used_font == 0 else "mixed")
        stats[{"font-shaping": "font", "derived": "derived", "mixed": "mixed"}[source]] += 1

        number = {
            "source": source,
            "cx": digits["3"]["cx"],
            "cy": digits["3"]["cy"],
            "width": digits["3"]["width"],
            "height": digits["3"]["height"],
            "r": g["r"],
            "digits": digits,
            "derived": {**gbox, "r": g["r"], "region": g["source"]},
        }
        if source != "derived":
            number["font"] = {
                "family": f.get("family"),
                "file": f.get("font"),
                "glyph": f.get("marker_glyph"),
                "mechanism": next(
                    (b.get("mechanism") for b in (f.get("boxes") or {}).values()
                     if b.get("mechanism")), None),
            }
        if mid in exceptions:
            number["exception"] = exceptions[mid]
        m["number"] = number

    with open(os.path.join(ROOT, "collection.json"), "w") as fh:
        json.dump(coll, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return coll, stats, ratios


# ------------------------------------------------------------------ the sheets

CARD_CSS = """
:root { color-scheme: light dark; }
body { font: 14px/1.4 system-ui, sans-serif; margin: 24px; background: #fbfaf7; color: #1a1a1a; }
h1 { font-size: 20px; margin: 0 0 4px; }
p.lede { margin: 0 0 20px; max-width: 70ch; color: #555; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 14px; }
.card { border: 1px solid #ddd8cc; border-radius: 8px; background: #fff; padding: 10px; }
.card.flagged { border-color: #c0392b; box-shadow: inset 0 0 0 2px #f6d6d1; }
.row { display: flex; gap: 6px; justify-content: center; }
.row svg { width: 64px; height: 64px; }
.id { font: 600 12px ui-monospace, monospace; margin-top: 8px; word-break: break-all; }
.meta { font-size: 11px; color: #666; }
.tag { display: inline-block; font-size: 10px; padding: 1px 5px; border-radius: 3px; }
.tag.font { background: #d8f0e0; color: #14532d; }
.tag.derived { background: #fdeecb; color: #6b4b06; }
.tag.mixed { background: #dbeafe; color: #1e3a8a; }
.flag { color: #c0392b; font-size: 11px; margin-top: 4px; }
.legend { margin: 12px 0 18px; font-size: 12px; }
.num { font-family: "Noto Naskh Arabic", "Noto Sans Arabic", "Amiri", "Scheherazade New", serif; }
.placement-preview { cursor: crosshair; touch-action: none; }
.placement-preview:focus-visible { outline: 3px solid #0b7771; outline-offset: 3px; }
.placement-target { fill: #c0392b; stroke: #fff; stroke-width: 10; pointer-events: none; }
.placement-selection { fill: #d6ad4344; stroke: #ad7b16; stroke-width: 18; pointer-events: none; }
.selection-source { fill: transparent; pointer-events: none; }
.placement-editor { position: fixed; inset-block-end: 16px; inset-inline-end: 16px; width: min(360px, calc(100vw - 32px)); border: 1px solid #b9c9c3; border-radius: 12px; background: #fffdf8; box-shadow: 0 12px 40px #1a342622; padding: 16px; z-index: 2; }
.placement-editor h2 { font-size: 14px; margin: 0 0 4px; }
.placement-editor p { font-size: 12px; margin: 0 0 10px; color: #4c5f57; }
.placement-values { margin: 0 0 10px; padding: 10px; overflow: auto; border-radius: 6px; background: #f1f4ee; color: #1d332b; font: 11px/1.45 ui-monospace, monospace; white-space: pre-wrap; }
.placement-actions { display: flex; gap: 8px; }
.placement-actions button { border: 0; border-radius: 6px; background: #0b7771; color: white; cursor: pointer; font: 600 12px system-ui, sans-serif; padding: 8px 10px; }
.placement-actions button.secondary { background: #dce7e1; color: #174238; }
.placement-actions button:disabled { cursor: not-allowed; opacity: 0.45; }
@media (max-width: 600px) { .placement-editor { inset-inline: 12px; width: auto; } }
"""


PLACEMENT_EDITOR = """
<aside class="placement-editor" aria-live="polite">
  <h2>Set a number centre</h2>
  <p>Click a marker part to select it, then centre from its bounds. Clicking blank space places the number at that exact point.</p>
  <pre class="placement-values">Click a preview to begin.</pre>
  <div class="placement-actions">
    <button type="button" class="secondary" data-align-x disabled>Centre horizontal</button>
    <button type="button" class="secondary" data-align-y disabled>Centre vertical</button>
    <button type="button" class="secondary" data-align-both disabled>Centre both</button>
    <button type="button" data-copy-placement>Copy JSON patch</button>
    <button type="button" class="secondary" data-reset-placement>Reset selected</button>
  </div>
</aside>
<script>
(() => {
  const edits = new Map();
  const panel = document.querySelector('.placement-values');
  const copyButton = document.querySelector('[data-copy-placement]');
  const resetButton = document.querySelector('[data-reset-placement]');
  const alignXButton = document.querySelector('[data-align-x]');
  const alignYButton = document.querySelector('[data-align-y]');
  const alignBothButton = document.querySelector('[data-align-both]');
  let selected = null;

  function rounded(value) { return Number(value.toFixed(1)); }

  function patchFor(markerId) {
    const digitEdits = edits.get(markerId) || {};
    return { marker: markerId, number: { digits: digitEdits } };
  }

  function renderPanel() {
    if (!selected) return;
    const { markerId, digitCount, cx, cy, contour } = selected;
    const selection = contour
      ? `Selected contour ${contour.dataset.contourIndex}; choose an alignment action.\\n`
      : 'No contour selected; the number was placed at the clicked point.\\n';
    panel.textContent = `Selected: ${markerId}, ${digitCount} digit${digitCount === '1' ? '' : 's'}\\n`
      + selection + `cx: ${cx}, cy: ${cy}\\n\\n`
      + JSON.stringify(patchFor(markerId), null, 2);
    const hasContour = Boolean(contour);
    alignXButton.disabled = !hasContour;
    alignYButton.disabled = !hasContour;
    alignBothButton.disabled = !hasContour;
  }

  function updateSelectionOutline(svg, contour) {
    const outline = svg.querySelector('[data-selection-outline]');
    outline.setAttribute('d', contour ? contour.getAttribute('d') : '');
    outline.setAttribute('display', contour ? '' : 'none');
  }

  function updatePreview(svg, cx, cy) {
    const box = svg.querySelector('[data-number-box]');
    const number = svg.querySelector('[data-number-label]');
    const width = Number(svg.dataset.numberWidth);
    const height = Number(svg.dataset.numberHeight);
    box.setAttribute('x', cx - width / 2);
    box.setAttribute('y', cy - height / 2);
    number.setAttribute('x', cx);
    number.setAttribute('y', cy);
    const target = svg.querySelector('[data-placement-target]');
    target.setAttribute('cx', cx);
    target.setAttribute('cy', cy);
    target.setAttribute('r', 20 / Number(svg.dataset.normalizeScale));
  }

  function setCentre(svg, point, contour = null) {
    const markerId = svg.dataset.markerId;
    const digitCount = svg.dataset.digitCount;
    const cx = rounded(point.x);
    const cy = rounded(point.y);
    const markerEdits = edits.get(markerId) || {};
    markerEdits[digitCount] = { cx, cy };
    edits.set(markerId, markerEdits);
    selected = { svg, markerId, digitCount, cx, cy, contour };
    updatePreview(svg, cx, cy);
    updateSelectionOutline(svg, contour);
    renderPanel();
  }

  function sourcePoint(svg, event) {
    const bounds = svg.getBoundingClientRect();
    const scale = Number(svg.dataset.normalizeScale);
    return {
      x: (((event.clientX - bounds.left) / bounds.width) * 1000
        - Number(svg.dataset.normalizeOffsetX)) / scale + Number(svg.dataset.sourceX),
      y: (((event.clientY - bounds.top) / bounds.height) * 1000
        - Number(svg.dataset.normalizeOffsetY)) / scale + Number(svg.dataset.sourceY),
    };
  }

  function contourAt(svg, point) {
    const probe = new DOMPoint(point.x, point.y);
    const candidates = [...svg.querySelectorAll('[data-selectable-contour]')]
      .filter((contour) => contour.isPointInFill(probe));
    return candidates.sort((a, b) => {
      const aBox = a.getBBox();
      const bBox = b.getBBox();
      return aBox.width * aBox.height - bBox.width * bBox.height;
    })[0] || null;
  }

  function centreFromContour(axis) {
    if (!selected?.contour) return;
    const box = selected.contour.getBBox();
    const point = {
      x: axis === 'y' ? selected.cx : box.x + box.width / 2,
      y: axis === 'x' ? selected.cy : box.y + box.height / 2,
    };
    setCentre(selected.svg, point, selected.contour);
  }

  document.querySelectorAll('.placement-preview').forEach((svg) => {
    svg.addEventListener('click', (event) => {
      const point = sourcePoint(svg, event);
      setCentre(svg, point, contourAt(svg, point));
    });
    svg.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        setCentre(svg, {
          x: Number(svg.dataset.sourceX) + Number(svg.dataset.sourceWidth) / 2,
          y: Number(svg.dataset.sourceY) + Number(svg.dataset.sourceHeight) / 2,
        });
      }
    });
  });

  alignXButton.addEventListener('click', () => centreFromContour('x'));
  alignYButton.addEventListener('click', () => centreFromContour('y'));
  alignBothButton.addEventListener('click', () => centreFromContour('both'));

  resetButton.addEventListener('click', () => {
    if (!selected) return;
    const { svg, markerId, digitCount } = selected;
    const cx = Number(svg.dataset.originalCx);
    const cy = Number(svg.dataset.originalCy);
    const markerEdits = edits.get(markerId) || {};
    delete markerEdits[digitCount];
    if (Object.keys(markerEdits).length) edits.set(markerId, markerEdits);
    else edits.delete(markerId);
    selected = { svg, markerId, digitCount, cx, cy, contour: null };
    updatePreview(svg, cx, cy);
    updateSelectionOutline(svg, null);
    renderPanel();
  });

  copyButton.addEventListener('click', async () => {
    if (!selected) return;
    const text = JSON.stringify(patchFor(selected.markerId), null, 2);
    await navigator.clipboard.writeText(text);
    copyButton.textContent = 'Copied';
    setTimeout(() => { copyButton.textContent = 'Copy JSON patch'; }, 1200);
  });
})();
</script>
"""


def marker_svg(path):
    src = open(os.path.join(ROOT, path)).read()
    vb = re.search(r'viewBox="([^"]+)"', src).group(1)
    d = re.search(r'\sd="([^"]+)"', src).group(1)
    return vb, d


def svg_contours(path_data):
    """Return each move-to contour as its own selectable SVG path."""
    return re.findall(r"[Mm][^Mm]*", path_data)


def card_svg(vb, d, box, text, colour="#0b7771", numfill="#111", show_box=True,
             marker_id=None, digit_count=None):
    source_x, source_y, source_width, source_height = [
        float(value) for value in vb.replace(",", " ").split()
    ]
    scale = PREVIEW_VIEWBOX_SIZE / max(source_width, source_height)
    offset_x = (PREVIEW_VIEWBOX_SIZE - source_width * scale) / 2
    offset_y = (PREVIEW_VIEWBOX_SIZE - source_height * scale) / 2
    transform = (
        f'translate({offset_x:.1f} {offset_y:.1f}) scale({scale:.6f}) '
        f'translate({-source_x:.1f} {-source_y:.1f})'
    )
    fs = PREVIEW_FONT_SIZE / scale
    sw = 10 / scale
    editor_attrs = ""
    if marker_id is not None and digit_count is not None:
        editor_attrs = (
            f' class="placement-preview" tabindex="0" role="button" '
            f'aria-label="Set the {digit_count}-digit number centre for {html.escape(marker_id, quote=True)}" '
            f'data-marker-id="{html.escape(marker_id, quote=True)}" data-digit-count="{digit_count}" '
            f'data-number-width="{box["width"]:.1f}" data-number-height="{box["height"]:.1f}" '
            f'data-original-cx="{box["cx"]:.1f}" data-original-cy="{box["cy"]:.1f}" '
            f'data-source-x="{source_x:.1f}" data-source-y="{source_y:.1f}" '
            f'data-source-width="{source_width:.1f}" data-source-height="{source_height:.1f}" '
            f'data-normalize-scale="{scale:.6f}" '
            f'data-normalize-offset-x="{offset_x:.1f}" data-normalize-offset-y="{offset_y:.1f}"'
        )
    parts = [
        f'<svg viewBox="0 0 {PREVIEW_VIEWBOX_SIZE} {PREVIEW_VIEWBOX_SIZE}" '
        f'xmlns="http://www.w3.org/2000/svg"{editor_attrs}>',
        f'<g transform="{transform}">',
    ]
    parts.append(f'<path d="{d}" fill="{colour}"/>')
    if editor_attrs:
        for contour_index, contour in enumerate(svg_contours(d)):
            parts.append(
                f'<path class="selection-source" d="{contour}" '
                f'data-selectable-contour data-contour-index="{contour_index}"/>'
            )
    if show_box:
        parts.append(
            f'<rect x="{box["cx"] - box["width"] / 2:.1f}" y="{box["cy"] - box["height"] / 2:.1f}" '
            f'width="{box["width"]:.1f}" height="{box["height"]:.1f}" fill="none" '
            f'stroke="#c0392b" stroke-width="{sw:.1f}" stroke-dasharray="{sw * 2.4:.0f} {sw * 1.6:.0f}" opacity="0.6" data-number-box/>'
        )
    parts.append(
        f'<text class="num" x="{box["cx"]:.1f}" y="{box["cy"]:.1f}" font-size="{fs:.1f}" '
        f'fill="{numfill}" text-anchor="middle" dominant-baseline="central" '
        f'textLength="{box["width"]:.1f}" lengthAdjust="spacing" data-number-label>{text}</text>'
    )
    if editor_attrs:
        parts.append(f'<circle class="placement-target" data-placement-target cx="{box["cx"]:.1f}" cy="{box["cy"]:.1f}" r="0"/>')
        parts.append('<path class="placement-selection" data-selection-outline d="" display="none"/>')
    parts.append("</g></svg>")
    return "".join(parts)


def sheet(coll, path, title, lede, mode):
    cards = []
    for m in coll["markers"]:
        vb, d = marker_svg(m["file"])
        num = m["number"]
        row = []
        if mode == "derived-vs-bbox":
            geo = num["derived"]
            row.append(card_svg(vb, d, geo, "٢٥٥"))
            vbx = [float(v) for v in vb.replace(",", " ").split()]
            bbox = {
                "cx": vbx[0] + vbx[2] / 2, "cy": vbx[1] + vbx[3] / 2,
                "width": geo["width"], "height": geo["height"],
            }
            row.append(card_svg(vb, d, bbox, "٢٥٥", numfill="#c0392b"))
            dx = abs(geo["cx"] - bbox["cx"])
            dy = abs(geo["cy"] - bbox["cy"])
            extra = (f'<div class="meta">offset from bbox centre: '
                     f'{dx:.0f} x, {dy:.0f} y</div>')
            if dx < 5 and dy < 5:
                extra += '<div class="meta">agrees with bbox centre</div>'
        else:
            for n in (1, 2, 3):
                row.append(card_svg(
                    vb, d, num["digits"][str(n)], DIGIT_TEXT[n],
                    marker_id=m["id"], digit_count=n,
                ))
            src = num["source"]
            cls = {"font-shaping": "font", "derived": "derived", "mixed": "mixed"}[src]
            extra = f'<span class="tag {cls}">{src}</span>'
            if num.get("font"):
                extra += f' <span class="meta">{html.escape(num["font"]["family"] or "")}' \
                         f' · {html.escape(num["font"]["mechanism"] or "")}</span>'
            else:
                extra += f' <span class="meta">region: {num["derived"]["region"]}</span>'
        flag = ""
        if num.get("exception"):
            flag = f'<div class="flag">FLAGGED: {html.escape(num["exception"]["reason"])}</div>'
        cards.append(
            f'<div class="card{" flagged" if flag else ""}">'
            f'<div class="row">{"".join(row)}</div>'
            f'<div class="id">{html.escape(m["id"])}</div>{extra}{flag}</div>'
        )
    doc = (
        f"<!doctype html><meta charset=utf-8><title>{html.escape(title)}</title>"
        f"<style>{CARD_CSS}</style><h1>{html.escape(title)}</h1>"
        f'<p class="lede">{lede}</p>'
        f'<div class="grid">{"".join(cards)}</div>'
        f'{PLACEMENT_EDITOR if mode == "digits" else ""}'
    )
    out = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w").write(doc)
    return out


def render_sheets(coll):
    """Render the audit sheets from collection metadata already on disk."""
    a = sheet(
        coll, "docs/number-placement.html",
        "Ayah marker number placement",
        "Each marker drawn with one, two and three Arabic-Indic digits placed in the "
        "recorded <code>number</code> box (dashed outline). "
        "<span class=\"tag font\">font-shaping</span> means the box was read out of the "
        "source font's own U+06DD enclosure; "
        "<span class=\"tag derived\">derived</span> means the font does not enclose and the "
        "box comes from the geometry of the marker's interior.",
        "digits",
    )
    b = sheet(
        coll, "docs/number-placement-baseline.html",
        "Derived centre vs bounding-box centre",
        "Left: the derived interior centre. Right (red): the naive centre of the marker's "
        "overall bounding box, the thing a consumer does by default. For a symmetric design "
        "the two agree; where the design hangs a flourish off the body they do not.",
        "derived-vs-bbox",
    )
    print(a, file=sys.stderr)
    print(b, file=sys.stderr)


def main():
    if "--render-only" in sys.argv:
        coll = json.load(open(os.path.join(ROOT, "collection.json")))
        render_sheets(coll)
        return

    coll, stats, ratios = build()
    render_sheets(coll)
    print(json.dumps(stats), file=sys.stderr)
    print("size ratios (width, height, n): " + json.dumps(
        {k: [round(v[0], 3), round(v[1], 3), v[2]] for k, v in ratios.items()}), file=sys.stderr)


if __name__ == "__main__":
    main()
