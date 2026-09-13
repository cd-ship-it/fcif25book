import pymupdf as fitz
import json, os, sys

DEFAULT_PDF = 'FiCF 25 Book-Stage1.2.pdf'
PDF_PATH = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PDF

doc = fitz.open(PDF_PATH)
print(f'Reading {PDF_PATH} ({len(doc)} pages)')

PAGE_W_PT = 612.0
PAGE_H_PT = 792.0
CSS_W = 695
CSS_H = 900
RENDER_SCALE = 2  # retina background

# Pages whose design (rotated/curved text following hand-drawn art, e.g. a
# vine) can't be reproduced as our usual horizontal absolutely-positioned
# text divs — rendered as a single flat image with NO text overlay at all,
# instead of the normal redact-text-then-overlay-divs treatment.
FULL_IMAGE_PAGES = set()

os.makedirs('assets/backgrounds', exist_ok=True)
os.makedirs('data', exist_ok=True)

sx = CSS_W / PAGE_W_PT
sy = CSS_H / PAGE_H_PT

pages_data = []
NUM_PAGES = len(doc)

for i in range(NUM_PAGES):
    page = doc[i]
    n = i + 1

    # Link annotations (kind 2 = URI link) -> generate.py turns these into
    # real <a target="_blank"> overlays (or a YouTube <iframe> embed, for a
    # link that's a YouTube URL). Rect is in the same PDF-point space as
    # text bboxes, so the same sx/sy scaling applies.
    links_out = []
    for link in page.get_links():
        if link.get('kind') == fitz.LINK_URI and link.get('uri'):
            r = link['from']
            links_out.append({'uri': link['uri'], 'bbox': [r.x0, r.y0, r.x1, r.y1]})

    if n in FULL_IMAGE_PAGES:
        lines_out = []
        bg_ext = 'jpg'
    else:
        bg_ext = 'png'
        d = page.get_text('dict')
        lines_out = []
        for b in d['blocks']:
            if b['type'] != 0:
                continue
            for l in b['lines']:
                spans_out = []
                for s in l['spans']:
                    spans_out.append({
                        'text': s['text'],
                        'bbox': s['bbox'],
                        'size': s['size'],
                        'font': s['font'],
                        'color': s['color'],
                        'origin': s['origin'],
                    })
                if spans_out:
                    lines_out.append({'bbox': l['bbox'], 'spans': spans_out})

        # Redact text (not images/vectors) on this in-memory copy so the
        # rendered background is clean underneath the HTML text overlay.
        for b in d['blocks']:
            if b['type'] != 0:
                continue
            for l in b['lines']:
                for s in l['spans']:
                    r = fitz.Rect(s['bbox'])
                    page.add_redact_annot(r, fill=None)
        if d['blocks']:
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

    pages_data.append({'page': n, 'lines': lines_out, 'links': links_out, 'bg_ext': bg_ext})

    mat = fitz.Matrix(sx * RENDER_SCALE, sy * RENDER_SCALE)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    if pix.width != CSS_W * RENDER_SCALE or pix.height != CSS_H * RENDER_SCALE:
        print('WARN size mismatch page', n, pix.width, pix.height)
    bg_path = f'assets/backgrounds/page{n}.{bg_ext}'
    if bg_ext == 'jpg':
        pix.save(bg_path, jpg_quality=90)
    else:
        pix.save(bg_path)
    print('page', n, 'lines:', len(lines_out), 'links:', len(links_out), 'bg saved', pix.width, pix.height, bg_path)

with open('data/pages.json', 'w', encoding='utf-8') as f:
    json.dump(pages_data, f, ensure_ascii=False, indent=1)

# Raw outline/bookmarks (page-level headings), for generate.py to derive
# per-page titles from for pages with no manually-curated title.
toc = doc.get_toc()
with open('data/outline.json', 'w', encoding='utf-8') as f:
    json.dump(toc, f, ensure_ascii=False, indent=1)

print('DONE', NUM_PAGES, 'pages')
