#!/usr/bin/env python3
"""Fetch the source fonts the number-box derivation reads.

`derive_number_font.py` shapes U+06DD in each marker's OWN source font, so it
needs the real font files -- the FULL TTF/OTF, not the gstatic woff2 subsets
recorded in `collection.json`, because a subset can drop the very lookups that
implement the enclosure.

The OFL families come from `google/fonts`; the rest from `fonts.quran.ws`,
which serves complete files at the URLs already recorded in `collection.json`.

    python3 scripts/fetch_source_fonts.py [target-dir]     # default /tmp/amfonts

Nothing here is committed: the fonts are inputs, not artefacts.
"""

import os
import sys
import urllib.parse
import urllib.request

GOOGLE = "https://raw.githubusercontent.com/google/fonts/main/ofl/{slug}/{file}"
WS = "https://fonts.quran.ws/assets/fonts/{file}"

GF = [
    ("alkalami", "Alkalami-Regular.ttf"),
    ("amiri", "Amiri-Regular.ttf"),
    ("amiri", "Amiri-Bold.ttf"),
    ("amiriquran", "AmiriQuran-Regular.ttf"),
    ("estedad", "Estedad[wght].ttf"),
    ("ibmplexsansarabic", "IBMPlexSansArabic-Thin.ttf"),
    ("ibmplexsansarabic", "IBMPlexSansArabic-ExtraLight.ttf"),
    ("ibmplexsansarabic", "IBMPlexSansArabic-Light.ttf"),
    ("ibmplexsansarabic", "IBMPlexSansArabic-Regular.ttf"),
    ("ibmplexsansarabic", "IBMPlexSansArabic-Medium.ttf"),
    ("ibmplexsansarabic", "IBMPlexSansArabic-SemiBold.ttf"),
    ("ibmplexsansarabic", "IBMPlexSansArabic-Bold.ttf"),
    ("jomhuria", "Jomhuria-Regular.ttf"),
    ("katibeh", "Katibeh-Regular.ttf"),
    ("kufam", "Kufam[wght].ttf"),
    ("mada", "Mada[wght].ttf"),
    ("mirza", "Mirza-Regular.ttf"),
    ("notonaskharabic", "NotoNaskhArabic[wght].ttf"),
    ("notonastaliqurdu", "NotoNastaliqUrdu[wght].ttf"),
    ("notosansarabic", "NotoSansArabic[wdth,wght].ttf"),
    ("scheherazadenew", "ScheherazadeNew-Regular.ttf"),
    ("scheherazadenew", "ScheherazadeNew-Medium.ttf"),
    ("scheherazadenew", "ScheherazadeNew-SemiBold.ttf"),
    ("scheherazadenew", "ScheherazadeNew-Bold.ttf"),
]

WS_FILES = [
    "digital-khatt-indopak.otf",
    "digital-khatt-v1.otf",
    "hafs-nastaleeq.otf",
    "indopak-nastaleeq.ttf",
    "uthmanic-bazzi-v20.ttf",
    "uthmanic-douri-v20.ttf",
    "uthmanic-qaloun-v21.ttf",
    "uthmanic-qunbul-v20.ttf",
    "uthmanic-shuba-v20.ttf",
    "uthmanic-sousi-v20.ttf",
    "uthmanic-warsh-v21.ttf",
]


def get(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return "cached"
    with urllib.request.urlopen(url, timeout=60) as r, open(dest, "wb") as f:
        f.write(r.read())
    return f"{os.path.getsize(dest)} bytes"


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "/tmp/amfonts"
    for sub in ("gf", "ws"):
        os.makedirs(os.path.join(root, sub), exist_ok=True)
    for slug, name in GF:
        url = GOOGLE.format(slug=slug, file=urllib.parse.quote(name))
        print(name, get(url, os.path.join(root, "gf", name)))
    for name in WS_FILES:
        print(name, get(WS.format(file=name), os.path.join(root, "ws", name)))
    print(f"\nfonts in {root}; pass it as AYAH_FONT_DIR to derive_number_font.py")


if __name__ == "__main__":
    main()
