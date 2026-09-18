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

# Dismissible hint-bubble placements (see emit_hint_bubble below) — edit
# this file to add/move/reword one, then re-run this script to see it.
# Each entry: {"page": N, "id": "...", "text": "...",
#   plus any of "left"/"right"/"top"/"bottom" (px, from that edge of the
#   695x900 page canvas) to position it}. `id` sets both this instance's
#   own DOM id (f"p{page}-{id}", so it only needs to be unique within its
#   own page) AND its dismiss-group (shared with every other entry using
#   the SAME id string, on any page) — closing one closes every entry in
#   that group, now and on any later page view. Give a tip a fresh, unused
#   id if it should NOT be linked to anything else.
try:
    HINTS_CONFIG = json.load(open('hints_config.json', encoding='utf-8'))
except FileNotFoundError:
    HINTS_CONFIG = []

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

# Reusable hover/tap tooltip hotspot — an invisible hit-area over content
# that's already part of the background image (same "overlay on real
# artwork" pattern as .readmore-trigger/.photo-zoom elsewhere in this file),
# wired to the shared #tooltip popup by pages/style.css's .event-title rules
# and webapp/src/scripts/tooltip-hotspot.client.ts (or timeline.js's
# wireTooltipHotspots for the standalone pageN.html previews — keep both in
# sync if either changes). Originally timeline-only (pages 8-9's
# TIMELINE_PAGES below); pulled out into its own function so any other
# page can add one too — just call this with that page's own bbox/title/desc,
# no need to be added to any timeline-specific set.
def emit_tooltip_hotspot(html, css_rules, el_id, bbox, sx, sy, title, desc, year=None, tag=None):
    x0, y0, x1, y1 = bbox
    left, top = x0 * sx, y0 * sy
    width, height = (x1 - x0) * sx, (y1 - y0) * sy
    esc_title = esc_attr(title)
    esc_desc = esc_attr(desc)
    if tag:
        esc_title = f'<span class="tt-tag">{esc_attr(tag)}</span>{esc_title}'
    year_attr = f' data-year="{esc_attr(str(year))}"' if year else ''
    html.append(
        f'<div class="event-title tooltip-hotspot" id="{el_id}" tabindex="0"'
        f"{year_attr} data-title='{esc_title}' data-desc=\"{esc_desc}\"></div>\n"
    )
    css_rules.append(
        f"#{el_id} {{ left:{left:.2f}px; top:{top:.2f}px; "
        f"width:{width:.2f}px; height:{height:.2f}px; }}\n"
    )

# Reusable dismissible hint callout (a small pill with a close button,
# floating near whatever it's pointing at) — same generalization as
# emit_tooltip_hotspot above, pulled out of the TIMELINE_PAGES-only block it
# used to live in. `side` is a CSS property:value pair for positioning
# (e.g. "right:24px"). Not normally called directly — every hint bubble in
# the actual book is placed via hints_config.json + emit_configured_hints
# below, which builds `side` from that file's left/right/top/bottom keys;
# this function is the one place that config maps to real markup.
def emit_hint_bubble(html, css_rules, el_id, side, text, group=None):
    group_attr = f' data-hint-group="{esc_attr(group)}"' if group else ''
    html.append(
        f'<div class="hint-bubble" id="{el_id}"{group_attr} role="status">'
        f'<span class="hint-bubble-text">{esc_attr(text)}</span>'
        '<button type="button" class="hint-bubble-close" aria-label="關閉提示">×</button>'
        '</div>\n'
    )
    css_rules.append(f"#{el_id} {{ {side}; }}\n")

# Emits every HINTS_CONFIG entry for page n (0, 1, or many — nothing wrong
# with a page having several). Builds each one's `side` CSS from whichever
# of left/right/top/bottom keys are present in its config entry.
#
# A config entry's `id` does double duty: p{n}-{id} is this instance's own
# (page-scoped, always-unique) DOM id, but the bare `id` value is ALSO
# written out as data-hint-group — the webapp/timeline.js dismiss logic
# groups by THAT, not by DOM id, so any two entries sharing the same `id`
# (like pages 8 and 9's "timeline-hint" pair) are treated as the same tip:
# closing one closes both, on both current and future page views, even
# though they're separate elements on separate pages. Give a tip its own
# never-reused id if it should dismiss independently of everything else.
def emit_configured_hints(html, css_rules, n):
    for hint in HINTS_CONFIG:
        if hint.get('page') != n:
            continue
        side = '; '.join(
            f"{prop}:{hint[prop]}px" for prop in ('left', 'right', 'top', 'bottom') if prop in hint
        )
        emit_hint_bubble(html, css_rules, f"p{n}-{hint['id']}", side, hint['text'], group=hint['id'])

# "Click a text block to zoom in" — desktop-only in the app (see
# webapp/src/scripts/flipbook.client.ts's own mobileMode check; the .zoom-
# block divs below are emitted unconditionally into the shared page markup
# either way, same as every other overlay, and simply never get wired up or
# made interactive on mobile — see .zoom-block's pointer-events rule in
# pages/style.css). One invisible hit-area per eligible paragraph, using
# extract.py's own 'lines' data — same data every other overlay in this
# file already draws on, just read differently here: grouped into
# paragraph-shaped blocks instead of matched against exact trigger text.
#
# "Eligible" deliberately excludes anything that isn't flowing body prose,
# proven against a 5-spread hand-checked sample (pages 6,7,14-18,48,49,
# 70,90,92 among them) before being turned loose on all 93 pages:
#   - the eyebrow/category heading (EYEBROW_COLOR, any size)
#   - the title (the largest non-eyebrow size on the page, when clearly
#     bigger than body text)
#   - a subtitle (a remaining size strictly between body and title)
#   - the byline/author line (matches AUTHOR_TEXT_MARKERS)
#   - a genuine PHOTO caption (caption-sized text spatially matching one of
#     the page's own `photos` entries — NOT every small-print line: pages
#     33/39/47 are a "ministry milestones" infographic (year labels +
#     13pt descriptions, zero photos on the page) where that small print
#     IS the entire readable content; a blanket "exclude anything caption-
#     sized" rule dropped every single block on those 3 pages)
EYEBROW_COLOR = 0x624393  # brand purple used for every category/eyebrow heading, any size
ZOOM_BODY_SIZE = 16.0
ZOOM_CAPTION_SIZE_LO, ZOOM_CAPTION_SIZE_HI = 11.0, 14.5
ZOOM_AUTHOR_TEXT_MARKERS = ('｜', '夫婦：', '夫婦:')
ZOOM_GAP_MULT = 0.6
ZOOM_X_JUMP_THRESH = 60
# Page 5 (table of contents) is excluded outright: every "body-sized" line
# on it is a TOC entry already wired to .toc-jump navigation — a zoom-block
# on top of the exact same area would fight that click instead of adding a
# reading aid. Pages 8/9 (timeline) have no 'lines' at all and so never
# produce a block anyway; listed here for clarity, not because they need
# special-casing.
ZOOM_EXCLUDED_PAGES = {5, 8, 9}

def zoom_line_text(line):
    return ''.join(s['text'] for s in line['spans']).strip()

def zoom_is_author_text(text):
    return any(marker in text for marker in ZOOM_AUTHOR_TEXT_MARKERS) or text.startswith('夫婦')

def zoom_cluster_columns(entries):
    """entries: list of (text, bbox, size, color). Splits into columns by
    x0 proximity — sort by x0, start a new column whenever the gap to the
    previous (x0-sorted) entry's x0 exceeds ZOOM_X_JUMP_THRESH. Real column
    x0s in this book cluster tightly (a handful of discrete values, not a
    continuum), so this single-linkage gap cut is reliable.

    Needed because a single global sort-by-Y-then-X pass interleaves two
    side-by-side columns whenever their lines land at close to the same Y —
    e.g. page 70's two parallel testimonial columns, same rows throughout —
    which fragmented each column's own paragraph into one block PER LINE
    (every column transition in sort order looked like a "column change").
    Clustering by X first, then grouping each column's lines by Y
    independently (zoom_group_lines below), fixes that while still keeping
    pages 14-17's genuinely separate (non-row-aligned) poem-stanza columns
    apart."""
    by_x = sorted(entries, key=lambda e: e[1][0])
    columns, current, prev_x0 = [], [], None
    for entry in by_x:
        x0 = entry[1][0]
        if prev_x0 is not None and abs(x0 - prev_x0) > ZOOM_X_JUMP_THRESH:
            columns.append(current)
            current = []
        current.append(entry)
        prev_x0 = x0
    if current:
        columns.append(current)
    return columns

def zoom_group_lines(entries):
    """entries: list of (text, bbox, size, color) all from ONE column (see
    zoom_cluster_columns above). Sorts by Y and groups into contiguous
    blocks by vertical gap + style continuity."""
    ordered = sorted(entries, key=lambda e: e[1][1])
    blocks, current, prev = [], [], None
    for entry in ordered:
        text, bbox, size, color = entry
        if prev is not None:
            gap = bbox[1] - prev[1][3]
            same_style = abs(size - prev[2]) < 0.5 and color == prev[3]
            if not same_style or gap > size * ZOOM_GAP_MULT:
                blocks.append(current)
                current = []
        current.append(entry)
        prev = entry
    if current:
        blocks.append(current)
    return blocks

def zoom_is_photo_caption_group(group, photos):
    """True if every line in the group is caption-sized AND spatially
    matches one of this page's real photos (same test the earlier fbstyle
    extraction's match_captions() used: sits within 30% of a photo's own
    width horizontally, starts 0-45px below its bottom edge) — a group must
    clear BOTH bars, so small-print body text on a page with no photos
    never gets excluded just for being small (see pages 33/39/47 above)."""
    if not all(ZOOM_CAPTION_SIZE_LO <= e[2] <= ZOOM_CAPTION_SIZE_HI for e in group):
        return False
    if not photos:
        return False
    cx0 = min(e[1][0] for e in group)
    cy0 = min(e[1][1] for e in group)
    cx1 = max(e[1][2] for e in group)
    for photo in photos:
        px0, py0, px1, py1 = photo['bbox']
        x_overlap = min(px1, cx1) - max(px0, cx0)
        if x_overlap < (px1 - px0) * 0.3:
            continue
        if -5 <= cy0 - py1 <= 45:
            return True
    return False

def compute_zoom_blocks(p):
    n = p['page']
    if n in ZOOM_EXCLUDED_PAGES:
        return []
    entries = []
    for line in p.get('lines', []):
        text = zoom_line_text(line)
        if not text or text == READMORE_TRIGGER_TEXT:
            continue
        first_s = line['spans'][0]
        entries.append((text, line['bbox'], first_s['size'], first_s['color']))
    if not entries:
        return []

    non_eyebrow = [e for e in entries if e[3] != EYEBROW_COLOR]
    if not non_eyebrow:
        return []

    max_size = max(e[2] for e in non_eyebrow)
    body_pool = list(non_eyebrow)
    if max_size > ZOOM_BODY_SIZE + 1:
        body_pool = [e for e in body_pool if abs(e[2] - max_size) >= 0.5]
    mid_sizes = sorted(
        {e[2] for e in body_pool if ZOOM_BODY_SIZE + 1 < e[2] < max_size - 1}, reverse=True
    )
    if mid_sizes:
        body_pool = [e for e in body_pool if abs(e[2] - mid_sizes[0]) >= 0.5]
    if not body_pool:
        return []

    groups = [g for col in zoom_cluster_columns(body_pool) for g in zoom_group_lines(col)]
    photos = p.get('photos', [])
    out = []
    for g in groups:
        joined = ''.join(e[0] for e in g)
        if zoom_is_author_text(joined) or zoom_is_photo_caption_group(g, photos):
            continue
        x0 = min(e[1][0] for e in g)
        y0 = min(e[1][1] for e in g)
        x1 = max(e[1][2] for e in g)
        y1 = max(e[1][3] for e in g)
        out.append((x0, y0, x1, y1))
    return out

def emit_zoom_blocks(html, css_rules, n, p):
    for i, bbox in enumerate(compute_zoom_blocks(p), start=1):
        x0, y0, x1, y1 = bbox
        left, top = x0 * sx, y0 * sy
        width, height = (x1 - x0) * sx, (y1 - y0) * sy
        el_id = f"p{n}-zoom{i}"
        html.append(f'<div class="zoom-block" id="{el_id}"></div>\n')
        css_rules.append(
            f"#{el_id} {{ left:{left:.2f}px; top:{top:.2f}px; "
            f"width:{width:.2f}px; height:{height:.2f}px; }}\n"
        )

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
# FiCF 25 Book-Stage1.3.pdf, re-confirmed unchanged as of Stage1.5.pdf:
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

# The three 事工一/二/三 entries are each a Chinese heading line immediately
# followed by its own English-subtitle line, both targeting the same page
# (TOC_TARGETS' (3,4)->32, (5,6)->38, (7,8)->46 pairs) — both are still
# clickable, but only the Chinese line gets the jump-icon affordance; a
# second icon on the English line right below it would just be a redundant
# repeat of the same "click to jump" cue rather than a second one.
TOC_ICON_SKIP = {4, 6, 8}

# Small purple-circle/white-arrow badge appended to every TOC entry (below)
# to signal "this is clickable" — the entries themselves are otherwise
# either fully invisible overlays (toc-jump) or plain black PDF text
# (toc-page-label), neither of which reads as interactive without it. Same
# purple-circle-white-glyph style as the mobile bottom-nav's dock buttons.
# Colors are baked directly into the SVG (fill/stroke), not currentColor, so
# it looks the same regardless of the surrounding text's own color.
# TOC_ICON_SPACE is flat CSS px (not run through sx like the rest of a
# line's geometry, since it's new UI chrome, not PDF content) added to each
# entry's own width so the icon has room to sit just past the original text
# without overlapping the next column — page 5's two TOC columns have well
# over 100px of clearance between them, far more than this needs.
TOC_ICON_SPACE = 20
TOC_ICON_SVG = (
    '<svg class="toc-jump-icon" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">'
    '<circle cx="12" cy="12" r="11" fill="#624393"/>'
    '<path d="M10 7l5 5-5 5" fill="none" stroke="#ffffff" stroke-width="2.4" '
    'stroke-linecap="round" stroke-linejoin="round"/></svg>'
)

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
    # own webapp/src/scripts/tooltip-hotspot.client.ts (event-delegated on
    # #stage instead, since #book's content is destroyed/recreated on
    # desktop/mobile rebuilds — a direct call like this wouldn't survive
    # that). DOMContentLoaded-wrapped since <head> runs before the .page
    # div below it even exists yet.
    extra_head = (
        f'<script src="../timeline.js"></script>\n'
        f'<script>document.addEventListener("DOMContentLoaded", '
        f'() => {{ wireTooltipHotspots(document.getElementById("page{n}")); wireHintBubbles(); }});</script>\n'
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
                # No icon here — every "PAGE N" label sits directly above its
                # own Chinese title line (same target page), which already
                # carries the icon; same reasoning as TOC_ICON_SKIP above,
                # just for this whole branch instead of specific line_idxs.
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
                # See TOC_ICON_SKIP above: still clickable either way, just
                # no icon (and no reserved icon space) on a skipped line.
                icon = '' if line_idx in TOC_ICON_SKIP else TOC_ICON_SVG
                icon_space = 0 if line_idx in TOC_ICON_SKIP else TOC_ICON_SPACE
                html.append(
                    f'<a class="toc-jump" id="{el_id}" href="page{target}.html" '
                    f'data-goto="{target}">{icon}</a>\n'
                )
                css_rules.append(
                    f"#{el_id} {{ left:{left:.2f}px; top:{top:.2f}px; "
                    f"width:{width + icon_space:.2f}px; height:{height:.2f}px; }}\n"
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

    # "閱讀全文" readmore triggers — see READMORE_TRIGGER_TEXT above. Emitted
    # AFTER the photo-zoom loop (not before, its earlier position) on
    # purpose: on pages like 48 and 85, the article's own photo bbox
    # vertically overlaps the small "閱讀全文" line sitting inside/under it
    # (real layouts, not a data bug), and with same-stacking-context
    # position:absolute overlays, the LATER element in DOM order paints on
    # top and wins hit-testing. Readmore used to lose that fight to
    # photo-zoom silently; being last now means it always wins its own
    # (tiny) box while photo-zoom still owns the rest of the photo, mirroring
    # the link-vs-photo precedent above.
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
        wrap_id = f"p{n}-album-wrap"
        el_id = f"p{n}-album"

        # .photo-album-wrap carries the page position (left/top/width) below
        # via generate.py's own per-page CSS; .photo-album itself is sized
        # but no longer absolutely positioned (see pages/style.css) so the
        # new below-image controls row can sit in normal flow right under
        # it, inside the same wrapper — position:absolute + overflow:hidden
        # on .photo-album (needed to clip/place the letterboxed photos)
        # would otherwise clip anything appended after them too.
        html.append(f'<div class="photo-album-wrap" id="{wrap_id}">\n')
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
        # Below-image control row — the same prev/next step, just as a
        # visible labeled button pair instead of the small icon buttons
        # overlaid on the image corners above. Same .photo-album-prev/-next
        # classes, so webapp's photo-album.client.ts click delegation (and
        # timeline.js's copy of it for the standalone previews) picks these
        # up with no extra wiring — see albumFor() there for how it
        # resolves a click in EITHER control set back to this one album.
        html.append(
            '<div class="photo-album-controls">'
            '<span class="photo-album-controls-label">相片集：</span>'
            '<button type="button" class="photo-album-prev photo-album-controls-btn">上一張</button>'
            '<button type="button" class="photo-album-next photo-album-controls-btn">下一張</button>'
            '</div>\n'
        )
        html.append('</div>\n')
        css_rules.append(
            f"#{wrap_id} {{ left:{left:.2f}px; top:{top:.2f}px; width:{width:.2f}px; }}\n"
            f"#{el_id} {{ width:{width:.2f}px; height:{height:.2f}px; }}\n"
        )

    # Timeline spread hover hotspots (extract.py's 'timeline_events') — see
    # emit_tooltip_hotspot above.
    for ev_idx, ev in enumerate(p.get('timeline_events', []), start=1):
        emit_tooltip_hotspot(
            html, css_rules, f"p{n}-tl{ev_idx}", ev['bbox'], sx, sy,
            ev['title'], ev['desc'], year=ev['year'], tag=ev.get('tag'),
        )

    # "Click a text block to zoom in" hit-areas — see emit_zoom_blocks above.
    emit_zoom_blocks(html, css_rules, n, p)

    # Folio-style page-number badge — skipped on page 1 (the cover has no
    # folio). Even page numbers sit on the LEFT side of a spread, odd on the
    # RIGHT — the fixed pagination pattern produced by showCover:true in the
    # webapp's page-flip config (page 1 alone, then 2-3, 4-5, ... as spreads).
    if n != 1:
        el_id = f"p{n}-pagenum"
        html.append(f'<div class="page-num" id="{el_id}">{n}</div>\n')
        side = 'left' if n % 2 == 0 else 'right'
        css_rules.append(f"#{el_id} {{ {side}:24px; }}\n")

    # Dismissible hint bubbles — see hints_config.json to add/move/reword
    # one for any page, no code change needed.
    emit_configured_hints(html, css_rules, n)

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
