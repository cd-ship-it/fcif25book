import json, os, re

# Standalone preview pages (pageN.html/.css/.generated.css + style.css) live
# here, one level below the project root — keeps 280+ generated files out of
# the root listing. index.html/timeline.js/assets/ stay at the root, so
# every reference to them from inside this folder needs a '../' prefix;
# same-folder references (style.css, pageN.css, other pageN.html) don't.
PAGES_DIR = 'pages'

PAGE_W_PT = 612.0
PAGE_H_PT = 792.0
CSS_W = 695
CSS_H = 900
sx = CSS_W / PAGE_W_PT
sy = CSS_H / PAGE_H_PT

data = json.load(open('data/pages.json', encoding='utf-8'))
TOTAL = len(data)

try:
    outline = json.load(open('data/outline.json', encoding='utf-8'))
except FileNotFoundError:
    outline = []

def font_family(font):
    if 'TANAngleton' in font:
        return "'TANAngleton', 'Noto Sans TC', sans-serif"
    return "'Noto Sans TC', 'PingFang TC', 'Microsoft JhengHei', sans-serif"

def font_weight(font):
    if 'Bold' in font:
        return 700
    return 400

def color_hex(c):
    return '#%06x' % c

def esc_html(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def esc_attr(s):
    return esc_html(s).replace('"', '&quot;')

YOUTUBE_RE = re.compile(r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([\w-]{6,})')

def youtube_embed_url(uri):
    """None for a normal link; the embeddable URL if `uri` is a YouTube video link."""
    m = YOUTUBE_RE.search(uri)
    return f'https://www.youtube-nocookie.com/embed/{m.group(1)}' if m else None

def bbox_overlap_area(a, b):
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ox0, oy0 = max(ax0, bx0), max(ay0, by0)
    ox1, oy1 = min(ax1, bx1), min(ay1, by1)
    return max(0.0, ox1 - ox0) * max(0.0, oy1 - oy0)

# Hand-curated titles for pages we've actually looked at. Takes priority
# over the outline-derived guess below for any page listed here.
PAGE_TITLES = {
    1: '封面',
    2: '電子書製作初心',
    3: '鳴謝',
    4: '經文頁',
    5: '目錄',
    6: '感恩致謝（一）',
    7: '感恩致謝（二）',
    8: '（空白頁）',
    9: '（空白頁）',
    10: '孕育',
}

# For every other page, derive a title from the PDF's own outline/bookmarks
# (data/outline.json, dumped by extract.py via doc.get_toc()). That outline
# is noisy — every text line seems to have been bookmarked, not just real
# headings — so pick the SHORTEST entry landing on that exact page as a
# heuristic for "this one's an actual heading, not a paragraph sentence".
MAX_TITLE_LEN = 20
# Strings that legitimately show up as short outline entries but are UI
# chrome / button labels, not page headings — never use these as a title.
TITLE_BLACKLIST = {'閱讀全文', 'PAGE #'}

def build_outline_titles(outline_entries):
    by_page = {}
    for _level, title, page_num in outline_entries:
        title = title.strip()
        if not title or len(title) > MAX_TITLE_LEN or title in TITLE_BLACKLIST:
            continue
        # Keep the FIRST qualifying entry per page (outline entries follow
        # reading order), not the shortest — the actual heading is usually
        # the first thing on the page, and this book's headings are often
        # visually split across two text runs (e.g. "孕育" + "萌芽" as two
        # separate spans/colors), so "shortest wins" tends to grab a
        # trailing half-title instead of the real one.
        if page_num not in by_page:
            by_page[page_num] = title
    return by_page

OUTLINE_TITLES = build_outline_titles(outline)

def page_title(n):
    if n in PAGE_TITLES:
        return PAGE_TITLES[n]
    if n in OUTLINE_TITLES:
        return OUTLINE_TITLES[n]
    return f'第 {n} 頁'

# Every page is rendered as a single flat, pixel-perfect image of the PDF's
# own layout (see extract.py) — there is no live body-text reconstruction
# anymore, so none of that machinery (paragraph-justify heuristics, font
# matching, per-browser text-layout variance) exists to go wrong. What's
# below is only the INTERACTIVE overlay layer: invisible, absolutely-
# positioned hit-areas/embeds over content that's already visible in the
# background image, driven by bbox coordinates extract.py already extracted.
# extract.py's 'lines' data is kept purely as metadata now, to locate a
# couple of specific pieces of trigger text (below) — never redacted out of
# the background or reconstructed as visible HTML.

# Timeline spread — see extract.py's TIMELINE_PAGES/extract_timeline_events
# for how these pages' background + 'timeline_events' data are produced.
# The title/tag text is already part of that background image (a real
# designed PDF, not a placeholder), so nothing here draws visible text; each
# event just gets an invisible hover hotspot over its existing text, wired
# to a tooltip by the shared timeline tooltip script (timeline.js for the
# standalone previews, webapp/src/scripts/timeline-tooltip.client.ts for the
# app).
TIMELINE_PAGES = {8, 9}

# "Photo Slides" pages — see extract.py's PHOTO_ALBUM_PAGES/
# extract_photo_albums() for how each page's 'photo_album' list of already
# letterboxed, pre-compressed slides (assets/photos/pageN-albumI.jpg) is
# produced, and PHOTO_ALBUM_BOX_PT (same value here) for where that
# placeholder graphic actually renders on the page. Emits a prev/next
# carousel div at that position; webapp's photo-album.client.ts (event
# delegation on #stage, same pattern as readmore.client.ts/
# photo-zoom.client.ts) wires up the buttons.
PHOTO_ALBUM_PAGES = {37, 45, 53}
PHOTO_ALBUM_BOX_PT = (61.2, 215.16, 488.7194, 314.16)

# "閱讀全文" (Read Full Text) buttons: the button graphic AND its text are
# both already part of the background image now — this just places an
# invisible clickable overlay over every line whose text is exactly this,
# at that line's extracted bbox. webapp/scripts/sync-details.mjs finds
# these by id to build readmore.config.ts; webapp's readmore.client.ts
# (event delegation on #stage) opens the matching article modal.
READMORE_TRIGGER_TEXT = '閱讀全文'

# Page 5 is the table of contents. Unlike every other link in this book it
# can't come from the PDF: page.get_links() is empty for page 5, and each
# entry's page number is a literal "PAGE #" the designer left unfilled (see
# TITLE_BLACKLIST above, which already has to defend against it leaking into
# a page title). So both the targets and the numbers are resolved here, by
# matching each entry's text/position against the pages' own titles.
#
# Keyed by LINE INDEX (0-based, into that page's data/pages.json 'lines' —
# stable and independent of any rendering loop, unlike the old scheme of
# keying this by a generate.py-assigned element id, which no longer exists
# now that there's no per-line text-emission loop to assign one). Re-derive
# this table with a quick dump of page 5's 'lines' (text + bbox) if a future
# PDF revision changes page 5's content — verified once against
# FiCF 25 Book-Stage1.3.pdf:
#   0  目錄 (page title, not a TOC entry)
#   1  鳴謝                                          -> 3
#   2  成長茁壯                                       -> 30
#   3  事工一：姊妹事奉 / 4  (Women In Ministries)     -> 32
#   5  事工二：社會關懷 / 6  (Pleroma Missions...)     -> 38
#   7  事工三：靈命塑造 / 8  (Spiritual Formation...)  -> 46
#   9  初熟果子                                       -> 54
#   10 生命果子呈獻一：跨代師友同行                     -> 56
#   11 生命果子呈獻二：生命結連轉化                     -> 62
#   12 生命果子呈獻三：豐榮新知舊雨                     -> 72
#   13 文化果子呈獻四：男女同盟 同尊同榮                -> 80
#   14 文化果子呈獻五：福音宣教 抗衝文化                -> 86
#   18 電子書製作初心 -> 2      19 孕育萌芽 -> 10
#   22 感恩致謝 -> 6            24 廿五年恩典長河 -> 8
#   25 參與支持 -> 92
#   15/16/17/20/21/23/26/27 are literal "PAGE #" placeholders, each paired
#   by position (same x-column, sitting just above its heading) with one of
#   the entries above that has no page number displayed in the design
#   (鳴謝->3, 成長茁壯->30, 初熟果子->54, 電子書製作初心->2, 孕育萌芽->10,
#   感恩致謝->6, 廿五年恩典長河->8, 參與支持->92).
TOC_TARGETS = {
    1: 3, 2: 30, 3: 32, 4: 32, 5: 38, 6: 38, 7: 46, 8: 46, 9: 54,
    10: 56, 11: 62, 12: 72, 13: 80, 14: 86,
    18: 2, 19: 10, 22: 6, 24: 8, 25: 92,
    15: 3, 16: 30, 17: 54, 20: 2, 21: 10, 23: 6, 26: 8, 27: 92,
}
# The subset of TOC_TARGETS whose text is the literal "PAGE #" placeholder.
# These need more than a click overlay: the background image still shows
# the PDF's unfilled "PAGE #" verbatim (nothing is redacted anymore), so
# this small, deliberate exception covers just that bbox with an opaque
# background-colored box and draws real "PAGE <n>" text on top of it — the
# ONLY body text this pipeline still renders as live HTML, contained to
# these 8 elements on this one page.
TOC_PAGE_LABELS = {15, 16, 17, 20, 21, 23, 26, 27}

HEAD = """<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="style.css">
<link rel="stylesheet" href="page{n}.generated.css">
<link rel="stylesheet" href="page{n}.css">
{extra_head}</head>
<body>
<div class="pagewrap">
<div class="nav">
  <a href="../index.html">目錄 Index</a>
  {prev}
  <span>Page {n} / {total}</span>
  {next}
</div>
<div class="page" id="page{n}">
"""

FOOT = """</div>
</div>
</body>
</html>
"""

CUSTOM_CSS_STUB = """/* page{n}.css — local overrides for page {n}.
   This file is created once and is NEVER overwritten by generate.py,
   so it's safe to hand-edit. It loads AFTER style.css and
   page{n}.generated.css, so any rule here wins.

   Examples:

   #page{n} {{
     background-image: url('../assets/backgrounds/page{n}.webp');
   }}

   #p{n}-photo1 {{
     left: 120px;
     top: 340px;
     width: 200px;
     height: 150px;
   }}
*/
"""

os.makedirs(PAGES_DIR, exist_ok=True)

for p in data:
    n = p['page']
    title = f"FiCF 25 — Page {n}"
    prev = f'<a href="page{n-1}.html">← Prev</a>' if n > 1 else '<span class="disabled">← Prev</span>'
    nxt = f'<a href="page{n+1}.html">Next →</a>' if n < TOTAL else '<span class="disabled">Next →</span>'

    bg_ext = p.get('bg_ext', 'png')
    # Standalone-preview-only wiring for the timeline spread (pages 8-9) —
    # deliberately in <head>, not inside the .page div below: sync-from-
    # source.mjs extracts exactly the `.page` div's own contents for the
    # webapp, so anything placed inside it would leak into the app too,
    # where timeline.js doesn't exist and this would duplicate the app's
    # own webapp/src/scripts/timeline-tooltip.client.ts (event-delegated on
    # #stage instead, since #book's content is destroyed/recreated on
    # desktop/mobile rebuilds — a direct call like this wouldn't survive
    # that). DOMContentLoaded-wrapped since <head> runs before the .page
    # div below it even exists yet.
    extra_head = (
        f'<script src="../timeline.js"></script>\n'
        f'<script>document.addEventListener("DOMContentLoaded", '
        f'() => {{ wireTimelineTooltip(document.getElementById("page{n}")); wireTimelineHint(); }});</script>\n'
        if n in TIMELINE_PAGES else ''
    )
    # The displayed background is always the WebP copy extract.py generates
    # alongside the original .png (kept on disk, unreferenced here).
    html = [HEAD.format(title=title, n=n, prev=prev, next=nxt, total=TOTAL, extra_head=extra_head)]
    css_rules = [
        f"#page{n} {{ background-image: url('../assets/backgrounds/page{n}.webp'); }}\n"
    ]

    lines = p.get('lines', [])

    # Page 5's table of contents — see TOC_TARGETS above for how this table
    # was derived and what each key means.
    if n == 5:
        for line_idx, target in TOC_TARGETS.items():
            line = lines[line_idx]
            x0, y0, x1, y1 = line['bbox']
            left, top = x0 * sx, y0 * sy
            width, height = (x1 - x0) * sx, (y1 - y0) * sy
            el_id = f"p5-toc{line_idx}"
            if line_idx in TOC_PAGE_LABELS:
                first_s = line['spans'][0]
                size = first_s['size'] * sx
                line_height_px = (first_s['bbox'][3] - first_s['bbox'][1]) * sy
                fam = font_family(first_s['font'])
                color = color_hex(first_s['color'])
                html.append(
                    f'<a class="t toc-page-label" id="{el_id}" href="page{target}.html" '
                    f'data-goto="{target}">PAGE {target}</a>\n'
                )
                css_rules.append(
                    f"#{el_id} {{ left:{left:.2f}px; top:{top:.2f}px; "
                    f"width:{width:.2f}px; height:{height:.2f}px; "
                    f"font-size:{size:.2f}px; line-height:{line_height_px:.2f}px; "
                    f"color:{color}; font-family:{fam}; font-weight:700; }}\n"
                )
            else:
                # Anchor, not a div — the href is what makes the standalone
                # pageN.html previews work; the app can't follow it (it'd
                # navigate out of the SPA) and uses data-goto instead, same
                # as the page-label case above — see flipbook.client.ts.
                html.append(
                    f'<a class="toc-jump" id="{el_id}" href="page{target}.html" '
                    f'data-goto="{target}"></a>\n'
                )
                css_rules.append(
                    f"#{el_id} {{ left:{left:.2f}px; top:{top:.2f}px; "
                    f"width:{width:.2f}px; height:{height:.2f}px; }}\n"
                )

    # "閱讀全文" readmore triggers — see READMORE_TRIGGER_TEXT above.
    readmore_idx = 0
    for line in lines:
        line_text = ''.join(s['text'] for s in line['spans']).strip()
        if line_text != READMORE_TRIGGER_TEXT:
            continue
        readmore_idx += 1
        x0, y0, x1, y1 = line['bbox']
        left, top = x0 * sx, y0 * sy
        width, height = (x1 - x0) * sx, (y1 - y0) * sy
        el_id = f"p{n}-readmore{readmore_idx}"
        html.append(
            f'<div class="readmore-trigger" id="{el_id}" role="button" tabindex="0" '
            f'aria-label="閱讀全文"></div>\n'
        )
        css_rules.append(
            f"#{el_id} {{ left:{left:.2f}px; top:{top:.2f}px; "
            f"width:{width:.2f}px; height:{height:.2f}px; }}\n"
        )

    # PDF hyperlinks -> real <a target="_blank"> overlays positioned over
    # the (already-visible-in-the-background-image) link text/button; a
    # YouTube link becomes a live <iframe> embed in the same spot instead.
    for link_idx, link in enumerate(p.get('links', []), start=1):
        x0, y0, x1, y1 = link['bbox']
        left = x0 * sx
        top = y0 * sy
        width = (x1 - x0) * sx
        height = (y1 - y0) * sy
        el_id = f"p{n}-link{link_idx}"
        embed_url = youtube_embed_url(link['uri'])

        if embed_url:
            # Invisible click target, not a live iframe: the PDF's own
            # thumbnail artwork for this spot is already part of the
            # (unredacted) background image, so leaving it as a plain
            # overlay shows that real thumbnail instead of YouTube's own
            # default one. webapp's yt-embed.client.ts swaps this div for
            # an actual <iframe> (with autoplay) only once it's clicked.
            html.append(
                f'<div class="yt-trigger" id="{el_id}" data-yt-embed="{embed_url}" '
                f'role="button" tabindex="0" aria-label="播放影片"></div>\n'
            )
        else:
            uri_esc = esc_attr(link['uri'])
            html.append(
                f'<a class="pdf-link" id="{el_id}" href="{uri_esc}" target="_blank" '
                f'rel="noopener noreferrer" aria-label="開啟連結"></a>\n'
            )

        css_rules.append(
            f"#{el_id} {{ left:{left:.2f}px; top:{top:.2f}px; "
            f"width:{width:.2f}px; height:{height:.2f}px; }}\n"
        )

    # Click-to-zoom overlays for real content photos (extract.py's
    # data/pages.json 'photos' list — already filtered down to unique JPEGs,
    # excluding decorative art and reused placeholder graphics). Invisible
    # hit-area over the photo already visible in the background image;
    # webapp/src/scripts/photo-zoom.client.ts opens the full-resolution
    # original (assets/photos/pageN-photoI.jpg, never resized/recompressed)
    # in a lightbox on click.
    #
    # Skip a photo whose bbox mostly coincides with a PDF link's (e.g. page
    # 63: the YouTube video's own thumbnail image is BOTH a unique JPEG
    # extract.py correctly keeps as a "real photo" AND the link-annotated
    # area a YouTube <iframe> gets emitted over, in the exact same spot).
    # Both overlays would otherwise stack at that position and, since this
    # photo-zoom loop runs after the links loop above, the photo-zoom div —
    # later in DOM order — visually wins hit-testing and silently steals
    # every click meant for the video, opening a static lightbox instead of
    # playing it. The underlying link/iframe already provides interactivity
    # for that region, so it should win, not a redundant zoom affordance.
    link_bboxes = [tuple(link['bbox']) for link in p.get('links', [])]
    for photo_idx, photo in enumerate(p.get('photos', []), start=1):
        x0, y0, x1, y1 = photo['bbox']
        photo_area = (x1 - x0) * (y1 - y0)
        if photo_area > 0 and any(
            bbox_overlap_area((x0, y0, x1, y1), lb) / photo_area > 0.5 for lb in link_bboxes
        ):
            continue
        left = x0 * sx
        top = y0 * sy
        width = (x1 - x0) * sx
        height = (y1 - y0) * sy
        el_id = f"p{n}-photo{photo_idx}"
        html.append(
            f'<div class="photo-zoom" id="{el_id}" data-photo-src="../assets/photos/{photo["file"]}" '
            f'role="button" tabindex="0" aria-label="放大照片"></div>\n'
        )
        css_rules.append(
            f"#{el_id} {{ left:{left:.2f}px; top:{top:.2f}px; "
            f"width:{width:.2f}px; height:{height:.2f}px; }}\n"
        )

    # "Photo Slides" pages (see PHOTO_ALBUM_PAGES above) — a prev/next
    # carousel of real photos (extract.py's 'photo_album' list) replacing
    # the reused placeholder graphic at PHOTO_ALBUM_BOX_PT. Every image is
    # already letterboxed to that exact box by extract.py, so no
    # object-fit/cropping logic is needed here — just position the
    # container and stack the <img> tags, all but the first `hidden`. Each
    # also carries data-photo-src pointing at its un-letterboxed, larger
    # 'full' version — clicking the currently-visible slide opens that in
    # the lightbox for free, via the SAME [data-photo-src] delegation
    # photo-zoom.client.ts already runs on #stage for regular content
    # photos elsewhere in the book (no photo-album-specific script needed).
    album_photos = p.get('photo_album', [])
    if n in PHOTO_ALBUM_PAGES and album_photos:
        box_left, box_top, box_w, box_h = PHOTO_ALBUM_BOX_PT
        left = box_left * sx
        top = box_top * sy
        width = box_w * sx
        height = box_h * sy
        el_id = f"p{n}-album"

        html.append(f'<div class="photo-album" id="{el_id}" role="group" aria-label="相片幻燈片" tabindex="0">\n')
        for i, photo in enumerate(album_photos):
            hidden_attr = '' if i == 0 else ' hidden'
            loading_attr = '' if i == 0 else ' loading="lazy"'
            html.append(
                f'<img class="photo-album-img" src="../assets/photos/{photo["file"]}" '
                f'data-photo-src="../assets/photos/{photo["full"]}" '
                f'alt="" data-caption="{esc_attr(photo["caption"])}"{hidden_attr}{loading_attr}>\n'
            )
        html.append(
            '<button type="button" class="photo-album-nav photo-album-prev" aria-label="上一張">‹</button>\n'
            '<button type="button" class="photo-album-nav photo-album-next" aria-label="下一張">›</button>\n'
            f'<div class="photo-album-caption">{esc_attr(album_photos[0]["caption"])}</div>\n'
            '</div>\n'
        )
        css_rules.append(
            f"#{el_id} {{ left:{left:.2f}px; top:{top:.2f}px; "
            f"width:{width:.2f}px; height:{height:.2f}px; }}\n"
        )

    # Timeline spread hover hotspots (extract.py's 'timeline_events') — the
    # title/tag text is already part of the background image (see
    # TIMELINE_PAGES above), so this is just an invisible hit-area over it,
    # wired to a popup by the shared timeline tooltip script.
    for ev_idx, ev in enumerate(p.get('timeline_events', []), start=1):
        x0, y0, x1, y1 = ev['bbox']
        left = x0 * sx
        top = y0 * sy
        width = (x1 - x0) * sx
        height = (y1 - y0) * sy
        el_id = f"p{n}-tl{ev_idx}"
        esc_title = esc_attr(ev['title'])
        esc_desc = esc_attr(ev['desc'])
        if ev.get('tag'):
            esc_tag = esc_attr(ev['tag'])
            esc_title = f'<span class="tt-tag">{esc_tag}</span>{esc_title}'
        html.append(
            f'<div class="event-title event-hotspot" id="{el_id}" tabindex="0" '
            f"data-year=\"{ev['year']}\" data-title='{esc_title}' data-desc=\"{esc_desc}\"></div>\n"
        )
        css_rules.append(
            f"#{el_id} {{ left:{left:.2f}px; top:{top:.2f}px; "
            f"width:{width:.2f}px; height:{height:.2f}px; }}\n"
        )

    # Folio-style page-number badge — skipped on page 1 (the cover has no
    # folio). Even page numbers sit on the LEFT side of a spread, odd on the
    # RIGHT — the fixed pagination pattern produced by showCover:true in the
    # webapp's page-flip config (page 1 alone, then 2-3, 4-5, ... as spreads).
    if n != 1:
        el_id = f"p{n}-pagenum"
        html.append(f'<div class="page-num" id="{el_id}">{n}</div>\n')
        side = 'left' if n % 2 == 0 else 'right'
        css_rules.append(f"#{el_id} {{ {side}:24px; }}\n")

    if n in TIMELINE_PAGES:
        # Sits at the INNER edge of each page — near the spine, page 8 (the
        # left/even page of the spread) on its right, page 9 (right/odd) on
        # its left — the mirror image of the page-num badge above, which
        # sits at each page's OUTER edge instead.
        hint_id = f"p{n}-timeline-hint"
        hint_side = 'right' if n % 2 == 0 else 'left'
        html.append(
            f'<div class="timeline-hint" id="{hint_id}" role="status">'
            '<span class="timeline-hint-text">移動滑鼠到大事紀查看詳情</span>'
            '<button type="button" class="timeline-hint-close" aria-label="關閉提示">×</button>'
            '</div>\n'
        )
        css_rules.append(f"#{hint_id} {{ {hint_side}:24px; }}\n")

    html.append(FOOT)

    with open(f'{PAGES_DIR}/page{n}.html', 'w', encoding='utf-8') as f:
        f.write(''.join(html))

    # Generated CSS is always rewritten (positions derived from the PDF).
    with open(f'{PAGES_DIR}/page{n}.generated.css', 'w', encoding='utf-8') as f:
        f.write(''.join(css_rules))

    # Custom override CSS is created only once and left alone afterwards.
    custom_path = f'{PAGES_DIR}/page{n}.css'
    if not os.path.exists(custom_path):
        with open(custom_path, 'w', encoding='utf-8') as f:
            f.write(CUSTOM_CSS_STUB.format(n=n))

bg_ext_by_page = {p['page']: p.get('bg_ext', 'png') for p in data}

titles_manifest = {
    'total': TOTAL,
    'width': CSS_W,
    'height': CSS_H,
    'pages': [
        {'page': n, 'title': page_title(n), 'bgExt': bg_ext_by_page.get(n, 'png')}
        for n in range(1, TOTAL + 1)
    ],
}
with open('data/titles.json', 'w', encoding='utf-8') as f:
    json.dump(titles_manifest, f, ensure_ascii=False, indent=1)

print('Generated', len(data), 'pages')
