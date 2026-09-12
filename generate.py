import json, os

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

    html = [HEAD.format(title=title, n=n, prev=prev, next=nxt, total=TOTAL)]
    css_rules = [
        f"#page{n} {{ background-image: url('assets/backgrounds/page{n}.png'); }}\n"
    ]

    idx = 0
    for line in p['lines']:
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

            html.append(f'<div class="t" id="{el_id}">{esc}</div>\n')
            css_rules.append(
                f"#{el_id} {{ left:{left:.2f}px; top:{top:.2f}px; "
                f"font-size:{size:.2f}px; line-height:{height:.2f}px; "
                f"color:{color}; font-family:{fam}; font-weight:{weight}; }}\n"
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

titles_manifest = {
    'total': TOTAL,
    'width': CSS_W,
    'height': CSS_H,
    'pages': [
        {'page': n, 'title': page_title(n)}
        for n in range(1, TOTAL + 1)
    ],
}
with open('data/titles.json', 'w', encoding='utf-8') as f:
    json.dump(titles_manifest, f, ensure_ascii=False, indent=1)

print('Generated', len(data), 'pages')
