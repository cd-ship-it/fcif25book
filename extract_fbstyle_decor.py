#!/usr/bin/env python3
"""Extract each sample page's decorative PNG graphics (watercolor washes,
line-art leaf/floral motifs) as their own standalone image files — no text,
since these are just the raw embedded PNGs, not a rendered page.

Separate, read-only, additive pipeline: opens the PDF directly and never
touches extract.py/generate.py or their own output. Reuses the exact
PNG-vs-JPEG signal extract.py's own comments already established ("every
decorative graphic in this book is PNG; every real photo is JPEG").

Saves every decorative PNG found per sample page (a page can have more than
one — e.g. a full-bleed wash plus a smaller accent motif), largest-area
first, as fbstyle-src/decor/pageN-decorI.png, plus a manifest.json summary
so the largest ("likely the main background wash") is easy to pick out
without opening every file.
"""
import json
import sys
from pathlib import Path

import pymupdf as fitz

PDF_PATH = 'FiCF 25 Book-Stage1.4.pdf'
OUT_DIR = Path('fbstyle-src/decor')
OUT_DIR.mkdir(parents=True, exist_ok=True)

SAMPLE_PAGES = [5, 6, 7, 8, 9, 14, 33, 37, 39, 63, 92, 20, 21, 30, 45, 53, 57, 65, 70, 84, 90]


def extract_page(doc: fitz.Document, n: int) -> list:
    page = doc[n - 1]
    found = []
    for info in page.get_image_info(xrefs=True):
        xref = info['xref']
        if not xref:
            continue
        img = doc.extract_image(xref)
        if img['ext'] != 'png':
            continue
        x0, y0, x1, y1 = info['bbox']
        # extract_image()'s own bytes are the OPAQUE base layer only — these
        # decorative PNGs store transparency as a separate soft-mask xref
        # (confirmed via img['smask']), which extract_image() does NOT
        # merge in; without this the "transparent" area comes out as solid
        # black instead. fitz.Pixmap(base, mask) does the real compositing.
        base_pix = fitz.Pixmap(doc, xref)
        smask_xref = img.get('smask')
        if smask_xref:
            mask_pix = fitz.Pixmap(doc, smask_xref)
            pix = fitz.Pixmap(base_pix, mask_pix)
        else:
            pix = base_pix
        png_bytes = pix.tobytes('png')
        found.append({'xref': xref, 'bytes': png_bytes, 'bbox': [x0, y0, x1, y1], 'area': (x1 - x0) * (y1 - y0)})
    found.sort(key=lambda e: -e['area'])
    return found


def main(sample_pages: list) -> None:
    doc = fitz.open(PDF_PATH)
    manifest = {}
    for n in sample_pages:
        entries = extract_page(doc, n)
        files = []
        for i, e in enumerate(entries, 1):
            fname = f'page{n}-decor{i}.png'
            (OUT_DIR / fname).write_bytes(e['bytes'])
            files.append({'file': fname, 'bbox': e['bbox'], 'area': round(e['area'])})
        manifest[str(n)] = files
        print(f'page {n}: {len(files)} decorative PNG(s)')
    (OUT_DIR / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')


if __name__ == '__main__':
    pages = [int(a) for a in sys.argv[1:]] if len(sys.argv) > 1 else SAMPLE_PAGES
    main(pages)
