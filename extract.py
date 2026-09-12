import pymupdf as fitz
import json, os

doc = fitz.open('FiCF 25 Book-level 1.pdf')

PAGE_W_PT = 612.0
PAGE_H_PT = 792.0
CSS_W = 695
CSS_H = 900
RENDER_SCALE = 2  # retina background

os.makedirs('assets/backgrounds', exist_ok=True)
os.makedirs('data', exist_ok=True)

sx = CSS_W / PAGE_W_PT
sy = CSS_H / PAGE_H_PT

pages_data = []
NUM_PAGES = len(doc)

for i in range(NUM_PAGES):
    page = doc[i]
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
    pages_data.append({'page': i+1, 'lines': lines_out})

    # Now redact text on a fresh copy to render clean background
    for l in d['blocks']:
        pass
    for b in d['blocks']:
        if b['type'] != 0:
            continue
        for l in b['lines']:
            for s in l['spans']:
                r = fitz.Rect(s['bbox'])
                page.add_redact_annot(r, fill=None)
    if d['blocks']:
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

    mat = fitz.Matrix(sx * RENDER_SCALE, sy * RENDER_SCALE)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    if pix.width != CSS_W * RENDER_SCALE or pix.height != CSS_H * RENDER_SCALE:
        print('WARN size mismatch page', i+1, pix.width, pix.height)
    pix.save(f'assets/backgrounds/page{i+1}.png')
    print('page', i+1, 'lines:', len(lines_out), 'bg saved', pix.width, pix.height)

with open('data/pages.json', 'w', encoding='utf-8') as f:
    json.dump(pages_data, f, ensure_ascii=False, indent=1)

# Raw outline/bookmarks (page-level headings), for generate.py to derive
# per-page titles from for pages with no manually-curated title.
toc = doc.get_toc()
with open('data/outline.json', 'w', encoding='utf-8') as f:
    json.dump(toc, f, ensure_ascii=False, indent=1)

print('DONE', NUM_PAGES, 'pages')
