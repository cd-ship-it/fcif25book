import pymupdf as fitz
import difflib, hashlib, json, os, re, sys
from PIL import Image, ImageOps

DEFAULT_PDF = 'FiCF 25 Book-Stage1.3.pdf'
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

# Timeline spread (pages 8-9): a separately hand-designed artwork
# (Timeline/Timeline-Years and Titles.pdf) replaces whatever the main book's
# own pages 8/9 contain (both were blank spacer pages). That PDF is a single
# 1224x792pt page — exactly two of this book's own 612x792pt pages side by
# side — rendered once here and split at its horizontal midpoint (612pt,
# confirmed by eye to clear every bubble/label) into this book's normal
# per-page background image pair. Event titles/tags are read from the
# timeline PDF's own vector text and matched against
# Timeline/Timeline-Years and Titles.md's descriptions; generate.py turns
# each into an invisible hover hotspot (the title text is already part of
# the background image — see TIMELINE-ALGORITHM.md for why this doesn't
# redraw the artwork).
TIMELINE_PDF_PATH = 'Timeline/Timeline-Years and Titles.pdf'
TIMELINE_MD_PATH = 'Timeline/Timeline-Years and Titles.md'
TIMELINE_PAGES = {8, 9}
TIMELINE_SPLIT_PT = 612.0  # x, in the timeline PDF's own point space

# "Photo Slides" pages: the PDF places the exact same reused stock
# "sky/clouds/hills" placeholder graphic (a JPEG whose hash repeats across
# these 3 pages — see the image-extraction pass below, which already
# excludes it as decorative for that reason) plus a literal "Photo Slides"
# text label, at an identical position on all three — a stand-in for a real
# slideshow supplied separately per page, outside the main PDF, at
# ../PhotoAlbums/<folder>/*. Each folder's photos (alphabetical order)
# replace that placeholder with an interactive prev/next carousel occupying
# its exact position — see generate.py for the HTML/CSS it emits.
PHOTO_ALBUM_DIR = 'PhotoAlbums'
PHOTO_ALBUM_PAGES = {37: 'Page 37 Photo Slides', 45: 'Page 45 Photo Slides', 53: 'Page 53 Photo Slides'}
PHOTO_ALBUM_LABEL_TEXT = 'Photo Slides'  # literal PDF text label over the placeholder; suppressed on these pages
# left, top, width, height, in this book's normal 612x792pt page space.
# Measured from the rendered placeholder graphic itself, NOT
# get_image_info()'s declared bbox — like page 36's photo, that bbox
# overshoots the page edges (a clip path PyMuPDF doesn't report), so it was
# cross-checked by eye against assets/backgrounds/page37/45/53.png instead.
PHOTO_ALBUM_BOX_PT = (61.2, 215.16, 488.7194, 314.16)


def extract_timeline_events():
    """{book_page: [{year, tag, title, desc, bbox}, ...]} for pages 8 and 9.
    bbox is in LOCAL 612x792pt space (already rebased for page 9)."""
    tdoc = fitz.open(TIMELINE_PDF_PATH)
    tpage = tdoc[0]

    with open(TIMELINE_MD_PATH, encoding='utf-8') as f:
        content = f.read()
    md_events = []
    for m in re.finditer(r'^## (\d{4})年\s*\|\s*(.+?)\s*$\n\n(.+?)(?=\n\n##|\Z)', content, re.M | re.S):
        year = int(m.group(1))
        heading = m.group(2).strip()
        desc = m.group(3).strip().replace('\n', ' ')
        tag_m = re.match(r'(【.+?】)(.*)', heading)
        tag, title = (tag_m.group(1), tag_m.group(2)) if tag_m else (None, heading)
        md_events.append({'year': year, 'tag': tag, 'title': title, 'desc': desc})

    # Reconstruct each event's title block: a line starting with an 8-space
    # indent is a wrapped CONTINUATION of the previous line (this PDF's own
    # convention for a hanging second line under a bullet), not a new event.
    d = tpage.get_text('dict')
    seq = []
    for b in d['blocks']:
        if b['type'] != 0:
            continue
        for l in b['lines']:
            spans = l['spans']
            if not spans:
                continue
            raw = ''.join(s['text'] for s in spans)
            if raw.strip().isdigit() and len(raw.strip()) == 4:
                continue  # the big year-in-bubble numbers, not an event title
            if spans[0]['size'] >= 20:
                continue  # the "25 年恩典長河" page title
            seq.append({'x0': l['bbox'][0], 'y0': l['bbox'][1], 'x1': l['bbox'][2], 'y1': l['bbox'][3], 'raw': raw})

    blocks = []
    cur = None
    for item in seq:
        if item['raw'].startswith('        ') and cur is not None:
            cur['text'] += item['raw'].strip()
            cur['x0'] = min(cur['x0'], item['x0']); cur['y0'] = min(cur['y0'], item['y0'])
            cur['x1'] = max(cur['x1'], item['x1']); cur['y1'] = max(cur['y1'], item['y1'])
        else:
            if cur:
                blocks.append(cur)
            cur = {'x0': item['x0'], 'y0': item['y0'], 'x1': item['x1'], 'y1': item['y1'], 'text': item['raw'].strip()}
    if cur:
        blocks.append(cur)

    # Match each reconstructed PDF text block to its markdown event by
    # content (not reading order — the two aren't in the same order). Fuzzy
    # (not exact) because of a known typo in the source PDF (購罝 vs 購置).
    def norm(s):
        return re.sub(r'[【】\s]', '', s)

    used = set()
    matched = []
    for blk in blocks:
        blk_norm = norm(blk['text'])
        best, best_score = None, 0
        for i, ev in enumerate(md_events):
            if i in used:
                continue
            ev_full = norm((ev['tag'] or '') + ev['title'])
            score = difflib.SequenceMatcher(None, blk_norm, ev_full).ratio()
            if blk_norm in ev_full or ev_full in blk_norm:
                score += 1
            if score > best_score:
                best_score, best = score, i
        if best is not None:
            used.add(best)
            matched.append({**md_events[best], 'x0': blk['x0'], 'y0': blk['y0'], 'x1': blk['x1'], 'y1': blk['y1']})

    if len(matched) != len(md_events):
        print(f'WARN timeline: matched {len(matched)}/{len(md_events)} events — check for a PDF text/md content mismatch')

    events_by_page = {8: [], 9: []}
    for ev in matched:
        if ev['x0'] < TIMELINE_SPLIT_PT:
            book_page, x0, x1 = 8, ev['x0'], ev['x1']
        else:
            book_page, x0, x1 = 9, ev['x0'] - TIMELINE_SPLIT_PT, ev['x1'] - TIMELINE_SPLIT_PT
        events_by_page[book_page].append({
            'year': ev['year'], 'tag': ev['tag'], 'title': ev['title'], 'desc': ev['desc'],
            'bbox': [x0, ev['y0'], x1, ev['y1']],
        })
    return events_by_page

PHOTO_ALBUM_LIGHTBOX_MAX_DIM = 1000   # px, longer side
PHOTO_ALBUM_LIGHTBOX_MAX_BYTES = 200 * 1024

def extract_photo_albums():
    """{page: [{'file', 'full', 'caption'}, ...]} for PHOTO_ALBUM_PAGES,
    sourced from ../PhotoAlbums/<folder>/* in alphabetical filename order.
    Two JPEGs per photo:
      - 'file' (pageN-albumI.jpg): letterboxed (resized to fit, black bars
        filling the rest) to exactly PHOTO_ALBUM_BOX_PT's aspect/size at
        RENDER_SCALE — the small carousel thumbnail.
      - 'full' (pageN-albumI-full.jpg): the real photo, natural aspect
        ratio (no letterbox bars), capped at PHOTO_ALBUM_LIGHTBOX_MAX_DIM on
        its longer side and re-encoded at a stepped-down JPEG quality until
        under PHOTO_ALBUM_LIGHTBOX_MAX_BYTES — opened in the lightbox
        (reuses photo-zoom.client.ts via the same data-photo-src attribute)
        when a slide is clicked.
    Several source photos are straight off a phone camera, up to ~14MB, too
    large to ship as-is across a 93-page book either way. A stray non-image
    file (e.g. a poster PDF) has its first page rendered to an image and
    included in its alphabetical position, same as any photo."""
    box_w = round(PHOTO_ALBUM_BOX_PT[2] * sx * RENDER_SCALE)
    box_h = round(PHOTO_ALBUM_BOX_PT[3] * sy * RENDER_SCALE)

    def orient(img):
        return ImageOps.exif_transpose(img).convert('RGB')

    def letterbox(img):
        scale = min(box_w / img.width, box_h / img.height)
        new_w, new_h = max(1, round(img.width * scale)), max(1, round(img.height * scale))
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        canvas = Image.new('RGB', (box_w, box_h), (0, 0, 0))
        canvas.paste(resized, ((box_w - new_w) // 2, (box_h - new_h) // 2))
        return canvas

    def save_capped(img, path, max_dim=PHOTO_ALBUM_LIGHTBOX_MAX_DIM, max_bytes=PHOTO_ALBUM_LIGHTBOX_MAX_BYTES):
        scale = min(1.0, max_dim / max(img.width, img.height))
        if scale < 1.0:
            img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
        for quality in (85, 78, 72, 65, 58, 50, 42, 35):
            img.save(path, 'JPEG', quality=quality, optimize=True)
            if os.path.getsize(path) <= max_bytes:
                return
        print(f'WARN photo album: {path} still {os.path.getsize(path)} bytes at lowest quality tried')

    def caption_for(filename):
        # "_ 2010 retreat (Margie, 梁潔瓊院長).JPG" -> "2010 retreat (Margie, 梁潔瓊院長)"
        return os.path.splitext(filename)[0].lstrip('_').strip()

    albums_by_page = {}
    for n, folder_name in PHOTO_ALBUM_PAGES.items():
        folder = os.path.join(PHOTO_ALBUM_DIR, folder_name)
        entries = []
        for idx, fname in enumerate(sorted(f for f in os.listdir(folder) if not f.startswith('.')), start=1):
            path = os.path.join(folder, fname)
            ext = os.path.splitext(fname)[1].lower()
            if ext == '.pdf':
                pdoc = fitz.open(path)
                ppix = pdoc[0].get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False)
                img = Image.frombuffer('RGB', (ppix.width, ppix.height), ppix.samples, 'raw', 'RGB', 0, 1)
                pdoc.close()
            elif ext in ('.jpg', '.jpeg', '.png', '.heic'):
                img = Image.open(path)
            else:
                print(f'WARN photo album page {n}: skipping unrecognized file {fname!r}')
                continue
            img = orient(img)
            out_name = f'page{n}-album{idx}.jpg'
            letterbox(img).save(f'assets/photos/{out_name}', 'JPEG', quality=85)
            full_name = f'page{n}-album{idx}-full.jpg'
            save_capped(img, f'assets/photos/{full_name}')
            entries.append({'file': out_name, 'full': full_name, 'caption': caption_for(fname)})
        albums_by_page[n] = entries
        print(f'Photo album page {n}: {len(entries)} slides from {folder}/')
    return albums_by_page

os.makedirs('assets/backgrounds', exist_ok=True)
os.makedirs('assets/photos', exist_ok=True)
os.makedirs('data', exist_ok=True)

sx = CSS_W / PAGE_W_PT
sy = CSS_H / PAGE_H_PT

pages_data = []
NUM_PAGES = len(doc)

# Render the timeline artwork once, split into this book's two normal
# per-page background images (same RENDER_SCALE, same CSS_W/CSS_H per half
# as every other page) — done up front so the main per-page loop below can
# just drop these in for pages 8/9 instead of rendering from `doc`.
timeline_events_by_page = extract_timeline_events()
print(f"Timeline: {sum(len(v) for v in timeline_events_by_page.values())} events across pages {sorted(TIMELINE_PAGES)}")

photo_albums_by_page = extract_photo_albums()

_tdoc = fitz.open(TIMELINE_PDF_PATH)
_tpage = _tdoc[0]
_tmat = fitz.Matrix(sx * RENDER_SCALE, sy * RENDER_SCALE)
_tpix = _tpage.get_pixmap(matrix=_tmat, alpha=False)
_full_img = Image.frombuffer('RGB', (_tpix.width, _tpix.height), _tpix.samples, 'raw', 'RGB', 0, 1)
_split_px = round(TIMELINE_SPLIT_PT * sx * RENDER_SCALE)
timeline_bg_halves = {
    8: _full_img.crop((0, 0, _split_px, _tpix.height)),
    9: _full_img.crop((_split_px, 0, _tpix.width, _tpix.height)),
}
_tdoc.close()

# Real content photos vs. decorative art (watercolor washes, leaf-motif
# illustrations, stock "photo not available yet" placeholders): every page
# embeds several raster images, but only some are genuine unique photos.
# Two purely mechanical signals separate them cleanly (verified against the
# whole document, zero exceptions found):
#   - format: every decorative graphic in this book is PNG (needs alpha
#     transparency to blend with the page); every real photo is JPEG.
#   - uniqueness: a real photo's exact byte content appears exactly once in
#     the whole PDF. A few JPEGs ARE reused byte-for-byte across pages
#     though (a full-bleed abstract background texture on pages 14/15, and
#     a generic "Photo Slides" stock illustration on pages 37/45/53) — those
#     are decorative too, just happen to be saved as JPEG. Excluding any
#     hash seen more than once catches both without a page-specific list.
# Pass 1: scan every page's embedded images before touching anything else
# (in particular before this page's own text redaction below, though that
# wouldn't affect image xrefs either way since redaction is told to leave
# images alone).
image_hash_count = {}
page_image_entries = {}
for i in range(NUM_PAGES):
    page = doc[i]
    n = i + 1
    entries = []
    for info in page.get_image_info(xrefs=True):
        img = doc.extract_image(info['xref'])
        if img['ext'] != 'jpeg':
            continue
        h = hashlib.md5(img['image']).hexdigest()
        image_hash_count[h] = image_hash_count.get(h, 0) + 1
        entries.append({'bbox': info['bbox'], 'hash': h, 'bytes': img['image']})
    page_image_entries[n] = entries

# Pass 2: keep only hashes unique to one page, save each as its own file.
photos_by_page = {}
total_photos = 0
for n, entries in page_image_entries.items():
    kept = []
    idx = 0
    for entry in entries:
        if image_hash_count[entry['hash']] != 1:
            continue
        idx += 1
        fname = f'page{n}-photo{idx}.jpg'
        with open(f'assets/photos/{fname}', 'wb') as f:
            f.write(entry['bytes'])
        kept.append({'bbox': list(entry['bbox']), 'file': fname})
    photos_by_page[n] = kept
    total_photos += len(kept)
print(f'Extracted {total_photos} unique photos across {sum(1 for v in photos_by_page.values() if v)} pages')

for i in range(NUM_PAGES):
    page = doc[i]
    n = i + 1

    if n in TIMELINE_PAGES:
        bg_ext = 'png'
        bg_path = f'assets/backgrounds/page{n}.{bg_ext}'
        timeline_bg_halves[n].save(bg_path)
        webp_path = f'assets/backgrounds/page{n}.webp'
        timeline_bg_halves[n].save(webp_path, 'WEBP', quality=85, method=6)
        pages_data.append({
            'page': n, 'lines': [], 'links': [], 'bg_ext': bg_ext,
            'photos': [], 'timeline_events': timeline_events_by_page[n],
        })
        print('page', n, '[TIMELINE] events:', len(timeline_events_by_page[n]),
              'bg saved', timeline_bg_halves[n].size, bg_path, '+ webp')
        continue

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
                    line_text = ''.join(s['text'] for s in spans_out)
                    if n in PHOTO_ALBUM_PAGES and line_text.strip() == PHOTO_ALBUM_LABEL_TEXT:
                        continue  # replaced by the real photo-album carousel below
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

    pages_data.append({
        'page': n, 'lines': lines_out, 'links': links_out, 'bg_ext': bg_ext,
        'photos': photos_by_page[n], 'photo_album': photo_albums_by_page.get(n, []),
    })

    mat = fitz.Matrix(sx * RENDER_SCALE, sy * RENDER_SCALE)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    if pix.width != CSS_W * RENDER_SCALE or pix.height != CSS_H * RENDER_SCALE:
        print('WARN size mismatch page', n, pix.width, pix.height)
    bg_path = f'assets/backgrounds/page{n}.{bg_ext}'
    if bg_ext == 'jpg':
        pix.save(bg_path, jpg_quality=90)
    else:
        pix.save(bg_path)

    # Also save a WebP copy for the webapp to actually display — the
    # original .png/.jpg is kept on disk untouched (not deleted, not
    # referenced by generate.py) so a future full-resolution click-to-zoom
    # feature has a source to use.
    webp_path = f'assets/backgrounds/page{n}.webp'
    webp_quality = 82 if bg_ext == 'jpg' else 85
    Image.frombuffer('RGB', (pix.width, pix.height), pix.samples, 'raw', 'RGB', 0, 1).save(
        webp_path, 'WEBP', quality=webp_quality, method=6
    )

    print('page', n, 'lines:', len(lines_out), 'links:', len(links_out), 'photos:', len(photos_by_page[n]), 'bg saved', pix.width, pix.height, bg_path, '+ webp')

with open('data/pages.json', 'w', encoding='utf-8') as f:
    json.dump(pages_data, f, ensure_ascii=False, indent=1)

# Raw outline/bookmarks (page-level headings), for generate.py to derive
# per-page titles from for pages with no manually-curated title.
toc = doc.get_toc()
with open('data/outline.json', 'w', encoding='utf-8') as f:
    json.dump(toc, f, ensure_ascii=False, indent=1)

print('DONE', NUM_PAGES, 'pages')
