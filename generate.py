import json, os, re

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

YOUTUBE_RE = re.compile(r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([\w-]{6,})')

def youtube_embed_url(uri):
    """None for a normal link; the embeddable URL if `uri` is a YouTube video link."""
    m = YOUTUBE_RE.search(uri)
    return f'https://www.youtube-nocookie.com/embed/{m.group(1)}' if m else None

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

# --- Shared: detect "paragraph" groups (consecutive same-style, ---------
# same-left-margin, evenly-spaced single-span lines) that the two
# experiments below both build on top of.
MIN_PARAGRAPH_GROUP = 2  # a "paragraph" of 1 line has nothing to justify/merge against

def _same_style(a, b):
    return a['font'] == b['font'] and abs(a['size'] - b['size']) < 0.01 and a['color'] == b['color']

def group_paragraph_lines(lines):
    """Return a list of paragraph groups, each a list of line-indices into
    `lines`, for consecutive lines that look like one wrapped paragraph:
    same font/size/color, same left edge, and a consistent line-to-line gap."""
    groups = []
    current = []

    def flush():
        if len(current) >= MIN_PARAGRAPH_GROUP:
            groups.append(list(current))
        current.clear()

    for i, line in enumerate(lines):
        spans = line['spans']
        if len(spans) != 1 or not spans[0]['text'].strip():
            flush()
            continue
        s = spans[0]
        if current:
            prev_line = lines[current[-1]]
            prev_s = prev_line['spans'][0]
            same_left = abs(line['bbox'][0] - prev_line['bbox'][0]) < 1.0
            gap = line['bbox'][1] - prev_line['bbox'][1]
            reasonable_gap = 0 < gap < s['size'] * 2.0
            if _same_style(s, prev_s) and same_left and reasonable_gap:
                current.append(i)
            else:
                flush()
                current.append(i)
        else:
            current.append(i)
    flush()
    return groups

# --- Full-justify paragraphs, book-wide ----------------------------------
# Every paragraph-like group (see group_paragraph_lines above) gets full
# justification, via one of two techniques depending on how long it is:
#
# A) MERGE-AND-REFLOW (>= MIN_MERGE_GROUP_LINES lines — real body-text
#    paragraphs): merge the group's lines into a single wrapping <div>
#    (white-space:normal, width = the group's widest original line) and
#    let the browser re-flow the text from scratch — true CSS justify
#    (text-align:justify + text-align-last:left, so only the last line
#    stays unstretched), rather than faking it line-by-line. In testing
#    (pages 68/69) this reproduced line breaks nearly identical to the
#    PDF's own, since the width matches the original column.
#
# B) PER-LINE STRETCH (2-3 lines — short quote/caption blocks too short to
#    safely reflow): keep the PDF's own line breaks and just stretch each
#    line except the last to the group's widest line via text-align-last:
#    justify. This is the fallback for anything under the merge threshold.
#
# Groups shorter than MIN_MERGE_GROUP_LINES are deliberately NOT merged —
# testing on page 68 showed merging also caught 2-line headings (same
# font/size/color/left-edge run, just short), and justify-stretching a
# large bold heading looks stretched/awkward in a way it doesn't for body
# text. Those still get technique B if they're >= MIN_PARAGRAPH_GROUP.
MIN_MERGE_GROUP_LINES = 4

def group_overlaps_a_link(lines, group, links):
    """True if any line in this group's original position coincides with a
    PDF hyperlink's rect (page.get_links(), extracted by extract.py).
    A merged/reflowed paragraph doesn't wrap the same way the original did
    (e.g. an unbreakable URL like "ficfellowship.org" may push to a new
    line), but the link overlay stays at its ORIGINAL coordinates — found
    on page 92, where a paragraph ending in a URL grew a line on reflow and
    swallowed the link's now-misaligned hitbox. Simplest safe fix: never
    merge a group a link is anchored inside; it keeps the PDF's exact line
    positions via the per-line stretch technique instead, so the link
    overlay (positioned against those same original coordinates) stays
    correctly aligned with the visible text under it."""
    for i in group:
        lb = lines[i]['spans'][0]['bbox']
        for link in links:
            rb = link['bbox']
            intersects = not (rb[2] < lb[0] or rb[0] > lb[2] or rb[3] < lb[1] or rb[1] > lb[3])
            if intersects:
                return True
    return False

def build_justify_widths_from_groups(lines, groups):
    """Return {line_index: target_width_pt} for lines that should be
    stretched to their paragraph's widest line via text-align:justify."""
    widths = {}
    for group in groups:
        line_widths = {i: lines[i]['spans'][0]['bbox'][2] - lines[i]['spans'][0]['bbox'][0] for i in group}
        target = max(line_widths.values())
        for i in group[:-1]:  # last line of a justified paragraph stays natural width
            widths[i] = target
    return widths

HEAD = """<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="style.css">
<link rel="stylesheet" href="page{n}.generated.css">
<link rel="stylesheet" href="page{n}.css">
</head>
<body>
<div class="pagewrap">
<div class="nav">
  <a href="index.html">目錄 Index</a>
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
     background-image: url('assets/backgrounds/page{n}.png');
   }}

   #p{n}-t3 {{
     left: 120px;
     top: 340px;
     font-size: 18px;
     color: #333333;
   }}
*/
"""

for p in data:
    n = p['page']
    title = f"FiCF 25 — Page {n}"
    prev = f'<a href="page{n-1}.html">← Prev</a>' if n > 1 else '<span class="disabled">← Prev</span>'
    nxt = f'<a href="page{n+1}.html">Next →</a>' if n < TOTAL else '<span class="disabled">Next →</span>'

    bg_ext = p.get('bg_ext', 'png')
    html = [HEAD.format(title=title, n=n, prev=prev, next=nxt, total=TOTAL)]
    css_rules = [
        f"#page{n} {{ background-image: url('assets/backgrounds/page{n}.{bg_ext}'); }}\n"
    ]

    page_links = p.get('links', [])
    all_groups = group_paragraph_lines(p['lines'])
    merge_groups = [
        g for g in all_groups
        if len(g) >= MIN_MERGE_GROUP_LINES and not group_overlaps_a_link(p['lines'], g, page_links)
    ]
    stretch_groups = [g for g in all_groups if g not in merge_groups]
    justify_widths = build_justify_widths_from_groups(p['lines'], stretch_groups)

    merge_skip = set()
    merge_start = {}
    for group in merge_groups:
        merge_start[group[0]] = group
        merge_skip.update(group)

    idx = 0
    for line_idx, line in enumerate(p['lines']):
        if line_idx in merge_start:
            group = merge_start[line_idx]
            group_lines = [p['lines'][i] for i in group]
            group_spans = [gl['spans'][0] for gl in group_lines]
            idx += 1
            el_id = f"p{n}-t{idx}"
            first_s = group_spans[0]
            merged_text = ''.join(s['text'] for s in group_spans)
            target_width_pt = max(s['bbox'][2] - s['bbox'][0] for s in group_spans)
            left = first_s['bbox'][0] * sx
            top = first_s['bbox'][1] * sy
            width_px = target_width_pt * sx
            size = first_s['size'] * sx
            line_height_px = (first_s['bbox'][3] - first_s['bbox'][1]) * sy
            fam = font_family(first_s['font'])
            weight = font_weight(first_s['font'])
            color = color_hex(first_s['color'])
            esc = merged_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

            html.append(f'<div class="t" id="{el_id}">{esc}</div>\n')
            css_rules.append(
                f"#{el_id} {{ left:{left:.2f}px; top:{top:.2f}px; "
                f"font-size:{size:.2f}px; line-height:{line_height_px:.2f}px; "
                f"color:{color}; font-family:{fam}; font-weight:{weight}; "
                f"width:{width_px:.2f}px; white-space:normal; text-align:justify; "
                f"text-align-last:left; text-justify:inter-character; }}\n"
            )
            continue
        if line_idx in merge_skip:
            continue

        for s in line['spans']:
            text = s['text']
            if text.strip() == '':
                continue
            idx += 1
            el_id = f"p{n}-t{idx}"
            x0, y0, x1, y1 = s['bbox']
            left = x0 * sx
            top = y0 * sy
            height = (y1 - y0) * sy
            size = s['size'] * sx
            fam = font_family(s['font'])
            weight = font_weight(s['font'])
            color = color_hex(s['color'])
            esc = (text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))

            extra = ''
            if line_idx in justify_widths and len(line['spans']) == 1:
                width_px = justify_widths[line_idx] * sx
                # text-align-last matters here: each .t div's content never
                # wraps (white-space:pre, and the width is sized to already
                # fit), so it's always exactly one line — which browsers
                # treat as a block's "last line", and never justify by
                # default no matter what text-align says.
                extra = (
                    f" width:{width_px:.2f}px; text-align:justify; "
                    f"text-align-last:justify; text-justify:inter-character;"
                )

            html.append(f'<div class="t" id="{el_id}">{esc}</div>\n')
            css_rules.append(
                f"#{el_id} {{ left:{left:.2f}px; top:{top:.2f}px; "
                f"font-size:{size:.2f}px; line-height:{height:.2f}px; "
                f"color:{color}; font-family:{fam}; font-weight:{weight};{extra} }}\n"
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
            html.append(
                f'<iframe class="yt-embed" id="{el_id}" src="{embed_url}" '
                f'title="YouTube video player" frameborder="0" '
                f'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" '
                f'referrerpolicy="strict-origin-when-cross-origin" allowfullscreen loading="lazy"></iframe>\n'
            )
        else:
            uri_esc = link['uri'].replace('&', '&amp;').replace('"', '&quot;')
            html.append(
                f'<a class="pdf-link" id="{el_id}" href="{uri_esc}" target="_blank" '
                f'rel="noopener noreferrer" aria-label="開啟連結"></a>\n'
            )

        css_rules.append(
            f"#{el_id} {{ left:{left:.2f}px; top:{top:.2f}px; "
            f"width:{width:.2f}px; height:{height:.2f}px; }}\n"
        )

    html.append(FOOT)
    with open(f'page{n}.html', 'w', encoding='utf-8') as f:
        f.write(''.join(html))

    # Generated CSS is always rewritten (positions/fonts derived from the PDF).
    with open(f'page{n}.generated.css', 'w', encoding='utf-8') as f:
        f.write(''.join(css_rules))

    # Custom override CSS is created only once and left alone afterwards.
    custom_path = f'page{n}.css'
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
