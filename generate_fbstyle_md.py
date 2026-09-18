#!/usr/bin/env python3
"""Extract a per-page Markdown "FB post" source file from data/pages.json.

Proof-of-concept for the "go back to the Facebook version" request — this is
a SEPARATE, read-only pipeline from generate.py (the production flipbook
pages). It never touches generate.py's own output; it only reads
data/pages.json (already produced by extract.py) and
webapp/src/config/readmore.config.ts (to note which pages have a "閱讀全文"
article), and writes one fbstyle-src/md/pageN.md per sample page.

Field heuristics (all font sizes/colors are PDF-point values straight out of
data/pages.json's line spans):
  - category (the small/large purple running-header, e.g. "感恩致謝")
      any line whose span color == EYEBROW_COLOR (#624393).
  - title: the largest-font non-purple line on the page (ties within 20pt of
      each other, vertically adjacent, are merged as a wrapped title).
  - subtitle: a non-purple line sized strictly between the title and the
      body size (16pt) — rare; most pages don't have one.
  - author: a body-sized line matching a byline pattern ('｜' name/role
      separator, or a '夫婦：' couple-byline prefix).
  - photos: extract.py's 'photos' list (bbox only, no caption) with the
      nearest small-font (~13pt) line(s) below it matched in as the caption;
      'photo_album' entries already carry their own caption.
  - body: every remaining line, reading-order sorted, grouped into
      paragraphs by vertical gap and re-joined (no space between CJK lines,
      a space only at an ASCII/ASCII wrap boundary) — same approach explored
      in the earlier fbstyle POC plan.
  - readmore: page number cross-referenced against readmore.config.ts's own
      page list (metadata only — filenames/ids, not the article text
      itself); the actual article body already lives in webapp/src/details/
      and is deliberately NOT duplicated into these files.

This is a first pass over a small sample set (see SAMPLE_PAGES) to validate
the heuristics before running it over all 93 pages — expect some pages to
need a manual look, same as every other per-page heuristic in this project.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
DATA = json.loads((ROOT / 'data/pages.json').read_text(encoding='utf-8'))
OUT_DIR = ROOT / 'fbstyle-src/md'
OUT_DIR.mkdir(parents=True, exist_ok=True)

SAMPLE_PAGES = [5, 6, 7, 8, 9, 14, 33, 37, 39, 63, 92, 20, 21, 30, 45, 53, 57, 65, 70, 84, 90]

EYEBROW_COLOR = 0x624393
BODY_SIZE = 16.0
CAPTION_SIZE_LO, CAPTION_SIZE_HI = 11.0, 14.5
READMORE_TRIGGER_TEXT = '閱讀全文'
TOC_PLACEHOLDER_RE = re.compile(r'^PAGE\s*#?\s*\d*$')
TIMELINE_TITLE = '廿五年恩典長河'

AUTHOR_RE = re.compile(r'｜|^夫婦[：:]')


def esc_yaml(s: str) -> str:
    return s.replace('\\', '\\\\').replace('"', '\\"')


def line_text(line: dict) -> str:
    return ''.join(s['text'] for s in line['spans']).strip()


def line_size(line: dict) -> float:
    return line['spans'][0]['size']


def line_color(line: dict) -> int:
    return line['spans'][0]['color']


def load_readmore_pages() -> dict:
    """page number -> detailsFile, parsed straight from the config's own
    array literal (metadata only, never the article text)."""
    src = (ROOT / 'webapp/src/config/readmore.config.ts').read_text(encoding='utf-8')
    out = {}
    for m in re.finditer(
        r"page:\s*(\d+),\s*elementId:\s*'[^']+',\s*detailsFile:\s*'([^']+)'", src
    ):
        page, details_file = m.groups()
        out.setdefault(int(page), []).append(details_file)
    return out


READMORE_PAGES = load_readmore_pages()


def join_run(texts: list) -> str:
    """Join wrapped PDF lines within one paragraph — no separator for CJK
    (correct at a normal wrap point), a single space only when both
    boundary characters are ASCII alnum (an English word wrapped mid-line)."""
    out = texts[0]
    for t in texts[1:]:
        prev_c = out[-1] if out else ''
        next_c = t[0] if t else ''
        if prev_c.isascii() and prev_c.isalnum() and next_c.isascii() and next_c.isalnum():
            out += ' ' + t
        else:
            out += t
    return out


def group_paragraphs(lines: list) -> list:
    """lines: list of (text, bbox, size, color), already reading-order
    sorted. Groups consecutive same-style lines with a small vertical gap
    into paragraphs; a larger gap (or a style change) starts a new one."""
    paragraphs = []
    current = []
    prev = None
    for entry in lines:
        text, bbox, size, color = entry
        if prev is not None:
            gap = bbox[1] - prev[1][3]
            same_style = abs(size - prev[2]) < 0.5 and color == prev[3]
            if not same_style or gap > size * 1.8:
                paragraphs.append(join_run([e[0] for e in current]))
                current = []
        current.append(entry)
        prev = entry
    if current:
        paragraphs.append(join_run([e[0] for e in current]))
    return paragraphs


def match_captions(photos: list, caption_lines: list) -> list:
    """For each extract.py 'photos' entry (bbox + file, no caption), find
    the small-font line(s) sitting just below it and use them as the
    caption. caption_lines: list of (text, bbox, size, color)."""
    used = set()
    result = []
    for photo in photos:
        px0, py0, px1, py1 = photo['bbox']
        candidates = []
        for i, (text, bbox, size, color) in enumerate(caption_lines):
            if i in used:
                continue
            cx0, cy0, cx1, cy1 = bbox
            x_overlap = min(px1, cx1) - max(px0, cx0)
            if x_overlap < (px1 - px0) * 0.3:
                continue
            if -5 <= cy0 - py1 <= 45:
                candidates.append((cy0, i, text))
        candidates.sort()
        cap_texts = []
        # Only take a run of candidates that stay close together (avoid
        # sweeping in a second photo's caption if two photos are stacked).
        last_bottom = None
        for cy0, i, text in candidates:
            if last_bottom is not None and cy0 - last_bottom > 25:
                break
            cap_texts.append(text)
            used.add(i)
            last_bottom = caption_lines[i][1][3]
        result.append({'file': photo['file'], 'caption': ''.join(cap_texts)})
    return result


def extract_page(n: int) -> dict:
    p = DATA[n - 1]
    lines_raw = p.get('lines', [])
    lines = []
    for line in lines_raw:
        text = line_text(line)
        if not text or text == READMORE_TRIGGER_TEXT:
            continue
        lines.append((text, line['bbox'], line_size(line), line_color(line)))

    # Page 5's TOC "PAGE #" placeholders (generate.py's TOC_PAGE_LABELS)
    # happen to use the same brand purple as a real category heading —
    # filter those out specifically, they're page-number labels, not topics.
    categories = [
        t for (t, b, s, c) in lines if c == EYEBROW_COLOR and not TOC_PLACEHOLDER_RE.match(t)
    ]
    non_eyebrow = [e for e in lines if e[3] != EYEBROW_COLOR]

    title_lines, subtitle_line, author_line = [], None, None
    body_pool = list(non_eyebrow)

    if non_eyebrow:
        max_size = max(e[2] for e in non_eyebrow)
        if max_size > BODY_SIZE + 1:
            title_candidates = [e for e in non_eyebrow if abs(e[2] - max_size) < 0.5]
            title_candidates.sort(key=lambda e: e[1][1])
            title_lines = title_candidates
            for e in title_lines:
                body_pool.remove(e)

            mid_sizes = sorted(
                {e[2] for e in body_pool if BODY_SIZE + 1 < e[2] < max_size - 1}, reverse=True
            )
            if mid_sizes:
                subtitle_candidates = [e for e in body_pool if abs(e[2] - mid_sizes[0]) < 0.5]
                subtitle_candidates.sort(key=lambda e: e[1][1])
                subtitle_line = join_run([e[0] for e in subtitle_candidates])
                for e in subtitle_candidates:
                    body_pool.remove(e)

        for e in list(body_pool):
            if abs(e[2] - BODY_SIZE) < 1.0 and AUTHOR_RE.search(e[0]):
                author_line = e[0]
                body_pool.remove(e)
                break

    caption_pool = [e for e in body_pool if CAPTION_SIZE_LO <= e[2] <= CAPTION_SIZE_HI]
    for e in caption_pool:
        body_pool.remove(e)

    photos = match_captions(p.get('photos', []), caption_pool)
    for album in p.get('photo_album', []):
        photos.append({'file': album['file'], 'caption': album.get('caption', '')})

    # Timeline pages (8-9) have no `lines` at all — synthesize paragraphs
    # from timeline_events instead, per the plan's accepted "reads oddly
    # out of context" tradeoff. No real title/category text exists in the
    # data for these two pages either (the "廿五年恩典長河" heading is part
    # of the background artwork, not an extracted line) — TIMELINE_TITLE is
    # a hand-supplied label, not something pulled from PDF data like every
    # other field here.
    if not lines_raw and p.get('timeline_events'):
        title_lines = [(TIMELINE_TITLE, [0, 0, 0, 0], 0, 0)]
        body_pool = []
        for ev in p['timeline_events']:
            tag = f"{ev['tag']} " if ev.get('tag') else ''
            body_pool.append((f"{ev['year']} — {tag}{ev['title']}：{ev['desc']}", [0, 0, 0, 0], BODY_SIZE, 0))

    body_pool.sort(key=lambda e: (round(e[1][1] / 4) * 4, e[1][0]))
    body_paragraphs = group_paragraphs(body_pool)

    title = join_run([e[0] for e in title_lines]) if title_lines else None
    readmore = READMORE_PAGES.get(n)

    return {
        'page': n,
        'categories': categories,
        'title': title,
        'subtitle': subtitle_line,
        'author': author_line,
        'photos': photos,
        'body': body_paragraphs,
        'readmore': readmore[0] if readmore else None,
    }


def write_md(info: dict) -> None:
    lines = ['---']
    lines.append(f"page: {info['page']}")
    if info['title']:
        lines.append(f'title: "{esc_yaml(info["title"])}"')
    if info['subtitle']:
        lines.append(f'subtitle: "{esc_yaml(info["subtitle"])}"')
    if info['author']:
        lines.append(f'author: "{esc_yaml(info["author"])}"')
    if info['categories']:
        lines.append('categories:')
        for c in info['categories']:
            lines.append(f'  - "{esc_yaml(c)}"')
    if info['photos']:
        lines.append('photos:')
        for photo in info['photos']:
            lines.append(f'  - file: "{photo["file"]}"')
            lines.append(f'    caption: "{esc_yaml(photo["caption"])}"')
    if info['readmore']:
        lines.append(f'readmore: "{info["readmore"]}"')
    lines.append('---')
    lines.append('')
    lines.append('\n\n'.join(info['body']))
    lines.append('')

    out_path = OUT_DIR / f"page{info['page']}.md"
    out_path.write_text('\n'.join(lines), encoding='utf-8')
    print(f"wrote {out_path.relative_to(ROOT)}")


if __name__ == '__main__':
    for n in SAMPLE_PAGES:
        write_md(extract_page(n))
