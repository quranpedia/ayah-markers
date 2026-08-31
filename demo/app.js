const parts = ['fill-base','fill-1','fill-2','fill-3','ink-base','ink-1','ink-2'];
const renderOrder = ['fill-base','fill-1','fill-2','fill-3','ink-base','ink-1','ink-2'];

const colors = document.querySelector('#colors');
const canvas = document.querySelector('#canvas');
const status = document.querySelector('#status');
const weights = document.querySelector('#weights');
const palettesContainer = document.querySelector('#palettes');

let records = [], svgCache = [], families = [], selectedFamily = 0, selectedVariant = 0;
let annotations = { markers: {} };
let activeView = 'mushaf';
let currentSurahKey = 'fatihah';
let mushafFontSize = 28;

const defaultTheme = Object.fromEntries(parts.map(part => [part, getComputedStyle(document.documentElement).getPropertyValue(`--${part}`).trim()]));

function theme() {
  return Object.fromEntries(parts.map(part => [part, getComputedStyle(document.documentElement).getPropertyValue(`--${part}`).trim()]));
}

function setColor(part, value) {
  document.documentElement.style.setProperty(`--${part}`, value);
}

function applyPalette(paletteColors) {
  Object.entries(paletteColors).forEach(([part, value]) => {
    setColor(part, value);
  });
  render();
}

function splitContours(path) {
  return path.match(/M[^M]*/g) || [];
}

const measureSvg = (() => {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('style', 'position:absolute;width:0;height:0;overflow:hidden');
  document.body.append(svg);
  return svg;
})();

function measured(contour) {
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', contour);
  path.setAttribute('fill-rule', 'evenodd');
  measureSvg.append(path);
  return path;
}

function interiorPoint(path) {
  const box = path.getBBox();
  for (let row = 1; row < 8; row++) {
    for (let column = 1; column < 8; column++) {
      const point = { x: box.x + box.width * column / 8, y: box.y + box.height * row / 8 };
      if (path.isPointInFill(point)) return point;
    }
  }
  return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
}

function hasAssignments(annotation) {
  return annotation && ['parts', 'interiorFills', 'generatedFills'].some(bucket => Object.values(annotation[bucket] || {}).some(values => values.length));
}

function localAnnotations() {
  try {
    return JSON.parse(localStorage.getItem('ayah-marker-annotations-v1')) || { markers: {} };
  } catch {
    return { markers: {} };
  }
}

function mergedAnnotations(fileAnnotations) {
  const local = localAnnotations();
  const ids = new Set([...Object.keys(fileAnnotations.markers || {}), ...Object.keys(local.markers || {})]);
  const markers = Object.fromEntries([...ids].map(id => {
    const fileMarker = fileAnnotations.markers?.[id] || {};
    const localMarker = local.markers?.[id] || {};
    return [id, {
      ...fileMarker,
      ...localMarker,
      parts: { ...(fileMarker.parts || {}), ...(localMarker.parts || {}) },
      interiorFills: { ...(fileMarker.interiorFills || {}), ...(localMarker.interiorFills || {}) },
      generatedFills: { ...(fileMarker.generatedFills || {}), ...(localMarker.generatedFills || {}) }
    }];
  }));
  return { ...fileAnnotations, markers };
}

function familyAnnotation(record) {
  const own = annotations.markers[record.id];
  if (hasAssignments(own)) return own;
  const family = record.id.split('-')[0];
  return Object.entries(annotations.markers).find(([id, annotation]) => id.split('-')[0] === family && hasAssignments(annotation))?.[1] || own;
}

function layerStyle(part) {
  return `fill:var(--${part},currentColor)`;
}

function availableParts(record) {
  const annotation = familyAnnotation(record);
  const assigned = annotation ? ['parts', 'interiorFills', 'generatedFills'].flatMap(bucket => Object.entries(annotation[bucket] || {}).filter(([, values]) => values.length).map(([part]) => part)) : [];
  return [...new Set(assigned.length ? assigned : parts.filter(part => record.parts?.[part]))];
}

function renderColorControls(record) {
  colors.replaceChildren();
  availableParts(record).forEach(part => {
    const label = document.createElement('label');
    label.className = 'color';
    label.textContent = part;
    const input = document.createElement('input');
    input.type = 'color';
    input.value = theme()[part] || '#083a3a';
    input.oninput = () => setColor(part, input.value);
    label.append(input);
    colors.append(label);
  });
}

function markerCss(record) {
  const variables = availableParts(record).map(part => `  --${part}: ${theme()[part]};`).join('\n');
  return `/* ${record.id} */\n.ayah-marker {\n${variables}\n}`;
}

function annotatedSvg(raw, annotation) {
  const source = new DOMParser().parseFromString(raw, 'image/svg+xml').documentElement;
  const documentSvg = document.implementation.createDocument('http://www.w3.org/2000/svg', 'svg', null);
  const svg = documentSvg.documentElement;
  svg.setAttribute('viewBox', source.getAttribute('viewBox'));
  svg.setAttribute('class', 'ayah-marker');
  const contours = new Map();
  let pathIndex = 0;
  source.querySelectorAll('path').forEach(path => {
    splitContours(path.getAttribute('d')).forEach((contour, contourIndex) => contours.set(`path-${pathIndex}-contour-${contourIndex}`, contour));
    pathIndex++;
  });

  const addGroup = (part, generated = false) => {
    const group = documentSvg.createElementNS(svg.namespaceURI, 'g');
    group.setAttribute('data-part', part);
    group.setAttribute('fill-rule', 'evenodd');
    group.setAttribute('style', layerStyle(part));
    if (generated) group.setAttribute('data-generated-fill', 'true');
    svg.append(group);
    return group;
  };

  const generatedGroups = Object.fromEntries(parts.map(part => [part, addGroup(part, true)]));
  const appendShape = (part, shape) => {
    if (!generatedGroups[part] || !shape?.type) return;
    const element = documentSvg.createElementNS(svg.namespaceURI, shape.type);
    Object.entries(shape).forEach(([name, value]) => {
      if (name !== 'type') element.setAttribute(name, value);
    });
    generatedGroups[part].append(element);
  };

  Object.entries(annotation.generatedFills || {}).forEach(([part, shapes]) => shapes.forEach(shape => appendShape(part, shape)));
  Object.entries(annotation.interiorFills || {}).forEach(([part, ids]) => ids.forEach(id => {
    const contour = contours.get(id);
    if (!contour) return;
    const output = documentSvg.createElementNS(svg.namespaceURI, 'path');
    output.setAttribute('d', contour);
    generatedGroups[part].append(output);
  }));

  const groups = Object.fromEntries(renderOrder.map(part => [part, addGroup(part)]));
  const assignments = new Map();
  Object.entries(annotation.parts).forEach(([part, ids]) => ids.forEach(id => assignments.set(id, part)));
  const placements = [];
  contours.forEach((contour, id) => {
    const part = assignments.get(id) || 'ink-base', path = measured(contour);
    placements.push({ part, contour, path, point: interiorPoint(path) });
  });

  renderOrder.forEach(part => {
    const own = placements.filter(placement => placement.part === part);
    if (!own.length) return;
    const contained = placements.filter(other => other.part !== part && renderOrder.indexOf(other.part) < renderOrder.indexOf(part) && own.some(placement => placement.path.isPointInFill(other.point)));
    const holes = contained.filter(other => !contained.some(outer => outer !== other && outer.path.isPointInFill(other.point)));
    const output = documentSvg.createElementNS(svg.namespaceURI, 'path');
    output.setAttribute('d', [...own, ...holes].map(placement => placement.contour).join(' '));
    groups[part].append(output);
  });

  placements.forEach(placement => placement.path.remove());
  return new XMLSerializer().serializeToString(svg);
}

const weightOrder = ['thin','extralight','light','regular','medium','semibold','bold','extrabold','black','regular-bold','regular-black'];
function weightRank(weight) {
  const rank = weightOrder.indexOf(weight);
  return rank < 0 ? weightOrder.length : rank;
}
const weightNames = { thin:'Thin', extralight:'ExtraLight', light:'Light', regular:'Regular', medium:'Medium', semibold:'SemiBold', bold:'Bold', extrabold:'ExtraBold', black:'Black' };
function weightLabel(weight) {
  return weight.split('-').map(word => weightNames[word] || word).join(' ');
}

function buildFamilies() {
  const grouped = new Map();
  records.forEach((record, index) => {
    const key = record.id.split('-')[0];
    if (!grouped.has(key)) grouped.set(key, { key, variants: [] });
    grouped.get(key).variants.push({ index, record, weight: record.id.slice(key.length + 1) });
  });
  const result = [...grouped.values()].sort((a, b) => a.key.localeCompare(b.key));
  result.forEach(family => {
    family.variants.sort((a, b) => weightRank(a.weight) - weightRank(b.weight));
    family.cover = family.variants.find(variant => variant.weight === 'regular') || family.variants[Math.floor(family.variants.length / 2)];
  });
  return result;
}

function currentFamily() { return families[selectedFamily]; }
function currentVariant() { return currentFamily().variants[selectedVariant]; }

function renderWeights() {
  const family = currentFamily();
  weights.replaceChildren();
  weights.hidden = family.variants.length < 2;
  family.variants.forEach((variant, index) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'weight';
    button.textContent = weightLabel(variant.weight);
    button.setAttribute('aria-pressed', index === selectedVariant);
    button.onclick = () => {
      selectedVariant = index;
      render();
    };
    weights.append(button);
  });
}

function filterGallery() {
  const query = document.querySelector('#search').value.trim().toLowerCase();
  let visible = 0;
  document.querySelectorAll('.marker-card').forEach(card => {
    const matches = card.dataset.search.includes(query);
    card.hidden = !matches;
    if (matches) visible++;
  });
  document.querySelector('#gallery-count').textContent = `${visible} of ${families.length} designs · ${records.length} weights total`;
}

function select(familyIndex, variantIndex = 0) {
  selectedFamily = familyIndex;
  selectedVariant = variantIndex;
  render();
}

// ----------------------------------------------------
// Quranic Mushaf Data & Rendering
// ----------------------------------------------------

const surahData = {
  fatihah: {
    name: "سُورَةُ الفَاتِحَةِ",
    meta: "مَكِّيَّةٌ · آيَاتُهَا ٧",
    bismillah: true,
    verses: [
      { text: "ٱلْحَمْدُ لِلَّهِ رَبِّ ٱلْعَٰلَمِينَ", num: 1 },
      { text: "ٱلرَّحْمَٰنِ ٱلرَّحِيمِ", num: 2 },
      { text: "مَٰلِكِ يَوْمِ ٱلدِّينِ", num: 3 },
      { text: "إِيَّاكَ نَعْبُدُ وَإِيَّاكَ نَسْتَعِينُ", num: 4 },
      { text: "ٱهْدِنَا ٱلصِّرَٰطَ ٱلْمُسْتَقِيمَ", num: 5 },
      { text: "صِرَٰطَ ٱلَّذِينَ أَنْعَمْتَ عَلَيْهِمْ", num: 6 },
      { text: "غَيْرِ ٱلْمَغْضُوبِ عَلَيْهِمْ وَلَا ٱلضَّآلِّينَ", num: 7 }
    ]
  },
  muawwidhat: {
    name: "المُعَوِّذَاتُ وَالإِخْلَاصُ",
    meta: "مَكِّيَّةٌ · قِصَارُ السُّوَرِ",
    bismillah: false,
    composite: [
      {
        title: "سُورَةُ الإِخْلَاصِ",
        bismillah: true,
        verses: [
          { text: "قُلْ هُوَ ٱللَّهُ أَحَدٌ", num: 1 },
          { text: "ٱللَّهُ ٱلصَّمَدُ", num: 2 },
          { text: "لَمْ يَلِدْ وَلَمْ يُولَدْ", num: 3 },
          { text: "وَلَمْ يَكُن لَّهُۥ كُفُوًا أَحَدٌۢ", num: 4 }
        ]
      },
      {
        title: "سُورَةُ الفَلَقِ",
        bismillah: true,
        verses: [
          { text: "قُلْ أَعُوذُ بِرَبِّ ٱلْفَلَقِ", num: 1 },
          { text: "مِن شَرِّ مَا خَلَقَ", num: 2 },
          { text: "وَمِن شَرِّ غَاسِقٍ إِذَا وَقَبَ", num: 3 },
          { text: "وَمِن شَرِّ ٱلنَّفَّٰثَٰتِ فِى ٱلْعُقَدِ", num: 4 },
          { text: "وَمِن شَرِّ حَاسِدٍ إِذَا حَسَدَ", num: 5 }
        ]
      },
      {
        title: "سُورَةُ النَّاسِ",
        bismillah: true,
        verses: [
          { text: "قُلْ أَعُوذُ بِرَبِّ ٱلنَّاسِ", num: 1 },
          { text: "مَلِكِ ٱلنَّاسِ", num: 2 },
          { text: "إِلَٰهِ ٱلنَّاسِ", num: 3 },
          { text: "مِن شَرِّ ٱلْوَسْوَاسِ ٱلْخَنَّاسِ", num: 4 },
          { text: "ٱلَّذِى يُوَسْوِسُ فِى صُدُورِ ٱلنَّاسِ", num: 5 },
          { text: "مِنَ ٱلْجِنَّةِ وَٱلنَّاسِ", num: 6 }
        ]
      }
    ]
  },
  kursi: {
    name: "آيَةُ الكُرْسِيِّ وخَوَاتِيمُ البَقَرَةِ",
    meta: "مَدَنِيَّةٌ · مِنْ سُورَةِ البَقَرَةِ",
    bismillah: true,
    verses: [
      { text: "ٱللَّهُ لَآ إِلَٰهَ إِلَّا هُوَ ٱلْحَىُّ ٱلْقَيُّومُ ۚ لَا تَأْخُذُهُۥ سِنَةٌ وَلَا نَوْمٌ ۚ لَّهُۥ مَا فِى ٱلسَّمَٰوَٰتِ وَمَا فِى ٱلْأَرْضِ ۗ مَن ذَا ٱلَّذِى يَشْفَعُ عِندَهُۥٓ إِلَّا بِإِذْنِهِۦ ۚ يَعْلَمُ مَا بَيْنَ أَيْدِيهِمْ وَمَا خَلْفَهُمْ ۖ وَلَا يُحِيطُونَ بِشَىْءٍ مِّنْ عِلْمِهِۦٓ إِلَّا بِمَا شَآءَ ۚ وَسِعَ كُرْسِيُّهُ ٱلسَّمَٰوَٰتِ وَٱلْأَرْضَ ۖ وَلَا يَـُٔودُهُۥ حِفْظُهُمَا ۚ وَهُوَ ٱلْعَلِىُّ ٱلْعَظِيمُ", num: 255 },
      { text: "ءَامَنَ ٱلرَّسُولُ بِمَآ أُنزِلَ إِلَيْهِ مِن رَّبِّهِۦ وَٱلْمُؤْمِنُونَ ۚ كُلٌّ ءَامَنَ بِٱللَّهِ وَمَلَٰٓئِكَتِهِۦ وَكُتُبِهِۦ وَرُسُلِهِۦ لَا نُفَرِّقُ بَيْنَ أَحَدٍ مِّن رُّسُلِهِۦ ۚ وَقَالُوا۟ سَمِعْنَا وَأَطَعْنَا ۖ غُفْرَانَكَ رَبَّنَا وَإِلَيْكَ ٱلْمَصِيرُ", num: 285 },
      { text: "لَا يُكَلِّفُ ٱللَّهُ نَفْسًا إِلَّا وُسْعَهَا ۚ لَهَا مَا كَسَبَتْ وَعَلَيْهَا مَا ٱكْتَسَبَتْ ۗ رَبَّنَا لَا تُؤَاخِذْنَآ إِن نَّسِينَآ أَوْ أَخْطَأْنَا ۚ رَبَّنَا وَلَا تَحْمِلْ عَلَيْنَآ إِصْرًا كَمَا حَمَلْتَهُۥ عَلَى ٱلَّذِينَ مِن قَبْلِنَا ۚ رَبَّنَا وَلَا تُحَمِّلْنَا مَا لَا طَاقَةَ لَنَا بِهِۦ ۖ وَٱعْفُ عَنَّا وَٱغْفِرْ لَنَا وَٱرْحَمْنَآ ۚ أَنتَ مَوْلَىٰنَا فَٱنصُرْنَا عَلَى ٱلْقَوْمِ ٱلْكَٰفِرِينَ", num: 286 }
    ]
  },
  naba: {
    name: "سُورَةُ النَّبَإِ",
    meta: "مَكِّيَّةٌ · الآيَات ١ - ١٢",
    bismillah: true,
    verses: [
      { text: "عَمَّ يَتَسَآءَلُونَ", num: 1 },
      { text: "عَنِ ٱلنَّبَإِ ٱلْعَظِيمِ", num: 2 },
      { text: "ٱلَّذِى هُمْ فِيهِ مُخْتَلِفُونَ", num: 3 },
      { text: "كَلَّا سَيَعْلَمُونَ", num: 4 },
      { text: "ثُمَّ كَلَّا سَيَعْلَمُونَ", num: 5 },
      { text: "أَلَمْ نَجْعَلِ ٱلْأَرْضَ مِهَٰدًا", num: 6 },
      { text: "وَٱلْجِبَالَ أَوْتَادًا", num: 7 },
      { text: "وَخَلَقْنَٰكُمْ أَزْوَٰجًا", num: 8 },
      { text: "وَجَعَلْنَا نَوْمَكُمْ سُبَاتًا", num: 9 },
      { text: "وَجَعَلْنَا ٱلَّيْلَ لِبَاسًا", num: 10 },
      { text: "وَجَعَلْنَا ٱلنَّهَارَ مَعَاشًا", num: 11 },
      { text: "وَبَنَيْنَا فَوْقَكُمْ سَبْعًا شِدَادًا", num: 12 }
    ]
  }
};

const palettes = [
  {
    name: 'Teal & Gold',
    dots: ['#0b7771', '#d6ad43', '#fff8e7'],
    colors: { 'fill-base': '#fff8e7', 'fill-1': '#f4e9bc', 'fill-2': '#d6ad43', 'fill-3': '#fffdf5', 'ink-base': '#083a3a', 'ink-1': '#0b7771', 'ink-2': '#48a39b' }
  },
  {
    name: 'Madinah Green',
    dots: ['#1b6337', '#c39b38', '#f8f9f0'],
    colors: { 'fill-base': '#f8f9f0', 'fill-1': '#e2ebd8', 'fill-2': '#c39b38', 'fill-3': '#fffef9', 'ink-base': '#0d381e', 'ink-1': '#1b6337', 'ink-2': '#3b8c56' }
  },
  {
    name: 'Royal Navy',
    dots: ['#1b263b', '#cfa13d', '#faf8f5'],
    colors: { 'fill-base': '#faf8f5', 'fill-1': '#f0e6ce', 'fill-2': '#cfa13d', 'fill-3': '#ffffff', 'ink-base': '#0d1b2a', 'ink-1': '#1b263b', 'ink-2': '#415a77' }
  },
  {
    name: 'Warm Ruby',
    dots: ['#78281f', '#c4823f', '#fdfaf6'],
    colors: { 'fill-base': '#fdfaf6', 'fill-1': '#fae8dc', 'fill-2': '#c4823f', 'fill-3': '#fffefc', 'ink-base': '#3d1308', 'ink-1': '#78281f', 'ink-2': '#aa4a30' }
  },
  {
    name: 'Night Gold',
    dots: ['#d4af37', '#56c2a6', '#182226'],
    colors: { 'fill-base': '#182226', 'fill-1': '#24343a', 'fill-2': '#d4af37', 'fill-3': '#10171a', 'ink-base': '#e6c57e', 'ink-1': '#56c2a6', 'ink-2': '#8be0cf' }
  },
  {
    name: 'Monochrome',
    dots: ['#151515', '#888888', '#ffffff'],
    colors: { 'fill-base': '#ffffff', 'fill-1': '#f0f0f0', 'fill-2': '#888888', 'fill-3': '#ffffff', 'ink-base': '#151515', 'ink-1': '#3a3a3a', 'ink-2': '#707070' }
  }
];

function toArabicDigits(num) {
  const digits = ['٠', '١', '٢', '٣', '٤', '٥', '٦', '٧', '٨', '٩'];
  return String(num).replace(/[0-9]/g, d => digits[+d]);
}

// The number does not sit in the middle of a marker. `collection.json` records
// where it does sit -- one centre per marker, in the SVG's own space -- so the
// numeral is drawn inside the artwork rather than centred over its box. Only
// the size of the box changes with the digit count.
function numberBox(record, numStr) {
  const number = record?.number;
  if (!number) return null;
  const size = number.digits?.[String(numStr.length)] || number.digits?.['3'] || number;
  return { ...size, cx: number.cx, cy: number.cy };
}

function withAyahNumber(svgString, record, numStr) {
  const box = numberBox(record, numStr);
  const viewBox = /viewBox="([^"]+)"/.exec(svgString)?.[1];
  if (!box || !viewBox) return svgString;
  const [, , width, height] = viewBox.replace(/,/g, ' ').trim().split(/\s+/).map(Number);
  // the size the placement sheet draws the numeral at, in the marker's units
  const fontSize = 0.32 * Math.max(width, height);
  const text = `<text class="ayah-number" x="${box.cx}" y="${box.cy}" font-size="${fontSize.toFixed(1)}"`
    + ` text-anchor="middle" dominant-baseline="central"`
    + ` textLength="${box.width.toFixed(1)}" lengthAdjust="spacing">${numStr}</text>`;
  return svgString.replace(/<\/svg>\s*$/, `${text}</svg>`);
}

function buildMarkerHtml(svgString, ayahNumber, record = currentVariant().record) {
  const numStr = toArabicDigits(ayahNumber);
  return `<span class="mushaf-ayah-marker" title="آية ${numStr}"><span class="ayah-svg-wrap">${withAyahNumber(svgString, record, numStr)}</span></span>`;
}

function renderPalettes() {
  palettesContainer.replaceChildren();
  palettes.forEach((palette, idx) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = `palette-btn ${idx === 0 ? 'active' : ''}`;
    btn.innerHTML = `
      <div class="palette-dots">
        ${palette.dots.map(d => `<span class="palette-dot" style="background:${d}"></span>`).join('')}
      </div>
      <span class="palette-name">${palette.name}</span>
    `;
    btn.onclick = () => {
      document.querySelectorAll('.palette-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      applyPalette(palette.colors);
    };
    palettesContainer.append(btn);
  });
}

function renderMushafContent() {
  const surah = surahData[currentSurahKey];
  const variant = currentVariant();
  const activeSvg = svgCache[variant.index];

  document.querySelector('#surah-name-ar').textContent = surah.name;
  document.querySelector('#surah-meta-ar').textContent = surah.meta;

  const bismillahEl = document.querySelector('#mushaf-bismillah');
  if (surah.bismillah) {
    bismillahEl.style.display = 'block';
  } else {
    bismillahEl.style.display = 'none';
  }

  const versesFlow = document.querySelector('#mushaf-verses-flow');

  if (surah.composite) {
    let html = '';
    surah.composite.forEach((section, sIndex) => {
      if (sIndex > 0) {
        html += `<div style="text-align:center;margin:24px 0 16px;border-top:1px dashed var(--mushaf-header-border,#c9a44c);padding-top:16px;">
          <span style="font-size:1.3rem;font-weight:700;">${section.title}</span>
        </div>`;
      }
      if (section.bismillah) {
        html += `<div style="text-align:center;font-size:1.35rem;margin-bottom:14px;">بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ</div>`;
      }
      section.verses.forEach(v => {
        html += `${v.text} ${buildMarkerHtml(activeSvg, v.num)} `;
      });
    });
    versesFlow.innerHTML = html;
  } else {
    let html = '';
    surah.verses.forEach(v => {
      html += `${v.text} ${buildMarkerHtml(activeSvg, v.num)} `;
    });
    versesFlow.innerHTML = html;
  }
}

function renderFlowView() {
  const variant = currentVariant();
  const activeSvg = svgCache[variant.index];
  document.querySelectorAll('.flow-marker-slot').forEach(slot => {
    const num = slot.dataset.num || '١';
    slot.innerHTML = `<span class="mushaf-ayah-marker"><span class="ayah-svg-wrap">${withAyahNumber(activeSvg, variant.record, num)}</span></span>`;
  });
}

function render() {
  const family = currentFamily(), variant = currentVariant();
  canvas.innerHTML = svgCache[variant.index];
  renderWeights();
  renderColorControls(variant.record);
  const layers = availableParts(variant.record);
  status.textContent = `${variant.record.id} · ${layers.length ? layers.join(', ') : 'no assigned layers'}`;
  document.querySelectorAll('.marker-card').forEach(card => card.setAttribute('aria-pressed', +card.dataset.family === selectedFamily));
  renderMushafContent();
  renderFlowView();
}

function switchView(viewName) {
  activeView = viewName;
  document.querySelectorAll('.tab-btn').forEach(btn => {
    const isTarget = btn.dataset.view === viewName;
    btn.classList.toggle('active', isTarget);
    btn.setAttribute('aria-selected', isTarget);
  });
  document.querySelectorAll('.view-panel').forEach(panel => {
    panel.classList.toggle('active', panel.id === `view-${viewName}`);
  });
}

// ----------------------------------------------------
// Initialization
// ----------------------------------------------------

Promise.all([
  fetch('../collection.json?v=collection-47-2').then(r => r.json()),
  fetch('../annotations.json?v=collection-47-2').then(r => r.json())
]).then(async ([collection, fileAnnotations]) => {
  annotations = mergedAnnotations(fileAnnotations);
  records = collection.markers;
  svgCache = await Promise.all(records.map(async record => {
    const raw = await fetch(`../${record.file}?v=source-safe-1`).then(r => r.text());
    const annotation = familyAnnotation(record);
    return hasAssignments(annotation) ? annotatedSvg(raw, annotation) : raw;
  }));
  families = buildFamilies();
  document.querySelector('#marker-count').textContent = `${families.length} designs · ${records.length} weights`;

  const gallery = document.querySelector('#gallery');
  families.forEach((family, index) => {
    const button = document.createElement('button');
    button.className = 'marker-card';
    button.dataset.family = index;
    button.dataset.search = `${family.key} ${family.variants.map(variant => variant.record.id).join(' ')}`.toLowerCase();
    button.setAttribute('aria-pressed', 'false');
    button.innerHTML = `<span class="thumb">${svgCache[family.cover.index]}</span><small>${family.key}</small><em>${family.variants.length} weight${family.variants.length > 1 ? 's' : ''}</em>`;
    button.onclick = () => {
      select(index, family.variants.indexOf(family.cover));
      document.querySelector('.workbench').scrollIntoView({ block: 'start', behavior: 'smooth' });
    };
    gallery.append(button);
  });

  renderPalettes();
  select(0, families[0].variants.indexOf(families[0].cover));
  filterGallery();
});

// View tabs
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.onclick = () => switchView(btn.dataset.view);
});

// Surah selector
document.querySelector('#mushaf-surah-select').onchange = (e) => {
  currentSurahKey = e.target.value;
  renderMushafContent();
};

// Theme selector
document.querySelector('#mushaf-theme-select').onchange = (e) => {
  const container = document.querySelector('#mushaf-container');
  container.className = `mushaf-wrapper theme-${e.target.value}`;
};

// Numbers toggle
document.querySelector('#mushaf-numbers-toggle').onchange = (e) => {
  const isChecked = e.target.checked;
  document.querySelector('#mushaf-verses-flow').classList.toggle('hide-numbers', !isChecked);
  document.querySelectorAll('.flow-sample').forEach(el => el.classList.toggle('hide-numbers', !isChecked));
};

// Font size scaling
document.querySelector('#font-increase').onclick = () => {
  if (mushafFontSize < 48) {
    mushafFontSize += 2;
    document.documentElement.style.setProperty('--mushaf-font-size', `${mushafFontSize}px`);
    document.querySelector('#font-size-label').textContent = `${mushafFontSize}px`;
  }
};

document.querySelector('#font-decrease').onclick = () => {
  if (mushafFontSize > 18) {
    mushafFontSize -= 2;
    document.documentElement.style.setProperty('--mushaf-font-size', `${mushafFontSize}px`);
    document.querySelector('#font-size-label').textContent = `${mushafFontSize}px`;
  }
};

// Copy CSS
document.querySelector('#copy').onclick = async () => {
  await navigator.clipboard.writeText(markerCss(currentVariant().record));
  const button = document.querySelector('#copy');
  const originalText = button.textContent;
  button.textContent = 'Copied!';
  setTimeout(() => button.textContent = originalText, 1200);
};

// Copy HTML Snippet
document.querySelector('#copy-html').onclick = async () => {
  const variant = currentVariant();
  const activeSvg = svgCache[variant.index];
  const snippet = `<!-- Ayah Marker: ${variant.record.id} -->
<!-- the number is placed at the centre collection.json records for this marker -->
<span class="mushaf-ayah-marker" style="display:inline-flex;vertical-align:middle;width:1.35em;height:1.35em;">
  ${withAyahNumber(activeSvg, variant.record, '١')}
</span>`;
  await navigator.clipboard.writeText(snippet);
  const button = document.querySelector('#copy-html');
  const originalText = button.textContent;
  button.textContent = 'Copied!';
  setTimeout(() => button.textContent = originalText, 1200);
};

// Reset colors
document.querySelector('#reset').onclick = () => {
  Object.entries(defaultTheme).forEach(([part, value]) => setColor(part, value));
  document.querySelectorAll('.palette-btn').forEach((b, i) => b.classList.toggle('active', i === 0));
  render();
};

// Search
document.querySelector('#search').oninput = filterGallery;
