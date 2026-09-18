"""One-off extraction: every page's body text + every read-more article's
full content, into a single Markdown file for an external proofreading
tool. Read-only against data/pages.json and details/*.md — writes only
proofread-full-text.md, touches nothing else in the pipeline.

Reuses generate_fbstyle.py's paragraph-grouping/joining logic (same
reflow heuristics, just discarding the per-run styling since this output
is plain text) rather than re-deriving it.
"""
import json
import os
import re

from generate_fbstyle import paragraphs_from_lines, paragraphs_from_timeline_events

OUT_PATH = 'proofread-full-text.md'
DETAILS_DIR = 'details'


def plain_text(paragraphs):
    return [''.join(run['text'] for run in p['runs']) for p in paragraphs]


def load_articles_by_page():
    """Group details/*.md files by their leading page number (`Page N...`),
    preserving filename order within a page (e.g. "Left" before "Right")."""
    by_page = {}
    for fname in sorted(os.listdir(DETAILS_DIR)):
        if not fname.endswith('.md'):
            continue
        m = re.match(r'Page (\d+)', fname)
        if not m:
            continue
        page = int(m.group(1))
        by_page.setdefault(page, []).append(fname)
    return by_page


def main():
    with open(os.path.join('data', 'pages.json'), encoding='utf-8') as f:
        data = json.load(f)
    by_page = {p['page']: p for p in data}
    total = len(data)

    articles_by_page = load_articles_by_page()

    out = [
        '# 基督豐榮：同行25載 — Full Text Extract (for proofreading)\n',
        '',
        f'Every page\'s body text (all {total} pages) plus every "閱讀全文" '
        'article\'s full content, in page order. Generated read-only from '
        'data/pages.json + details/*.md for an external proofreading pass — '
        'not used by any part of the site itself.',
        '',
    ]

    for n in range(1, total + 1):
        page = by_page[n]
        out.append(f'\n---\n\n## Page {n}\n')

        if page.get('timeline_events'):
            paragraphs = paragraphs_from_timeline_events(page['timeline_events'])
        else:
            paragraphs = paragraphs_from_lines(page.get('lines', []))

        for text in plain_text(paragraphs):
            out.append(text + '\n')

        for fname in articles_by_page.get(n, []):
            article_path = os.path.join(DETAILS_DIR, fname)
            with open(article_path, encoding='utf-8') as f:
                article_content = f.read().rstrip('\n')
            out.append(f'\n### 閱讀全文 — {fname}\n')
            out.append(article_content + '\n')

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))

    total_articles = sum(len(v) for v in articles_by_page.values())
    print(f'Wrote {OUT_PATH}: {total} pages, {total_articles} articles.')


if __name__ == '__main__':
    main()
