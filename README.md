# FiCF 25 週年紀念電子書

A PDF-to-HTML/CSS conversion of "FiCF 25 Book-Stage1.2.pdf" (93 pages), rendered as a
two-page-spread flipbook.

**Live site:** https://cd-ship-it.github.io/fcif25book/ (deployed automatically by
`.github/workflows/deploy.yml` on every push to `main`)

## Layout

```
FiCF 25 Book-Stage1.2.pdf   — source document (93 pages)
extract.py                 — PDF -> assets/backgrounds/*.png|jpg (text-redacted, 2x retina)
                              + data/pages.json (text spans, PDF hyperlinks, position/font/size/color)
                              + data/outline.json (PDF bookmarks, for auto page titles)
generate.py                — data/pages.json -> pageN.html / pageN.generated.css / pageN.css
                              (per page: standalone preview + generated + hand-editable CSS)
                              + data/titles.json (manifest: page count + titles)
style.css                  — shared CSS for the standalone pageN.html previews
index.html                 — thumbnail gallery of all pageN.html previews
pageN.html/.css            — one set per PDF page (generated + hand-editable, see below)
assets/                    — backgrounds (PNG) + fonts (extracted embedded TTF) per page

webapp/                    — the actual deployed flipbook app (Astro + page-flip)
  scripts/sync-from-source.mjs   — pulls the above into webapp/src + webapp/public
  src/config/flipbook.config.ts  — book size, toolbar features, labels, palette
  src/config/readmore.config.ts  — "閱讀全文" button -> details modal wiring
  src/details/*.md               — full-article content for those modals
  README.md                      — full app-level documentation
```

**Regenerating from the PDF** (e.g. after editing a `pageN.css` override, or if the
source PDF changes):

```sh
python3 -m venv .venv && ./.venv/bin/pip install pymupdf   # first time only
./.venv/bin/python3 extract.py                 # or: extract.py "Some Other Book.pdf"
./.venv/bin/python3 generate.py
cd webapp && node scripts/sync-from-source.mjs && npm run build
```

`extract.py` takes the PDF path as an optional first argument (defaults to the
constant at the top of the file) — no need to hand-edit the script for a new PDF.

Only `webapp/` is what actually ships — the root-level `pageN.html` files and
`index.html` gallery are a standalone preview/debugging aid, not part of the
deployed site.

**Full-justify paragraphs, book-wide:** `generate.py` detects paragraph-like
groups of lines (consecutive same font/size/color/left-edge, evenly spaced)
and justifies them (last line stays natural/ragged, like real typesetting).
Two techniques depending on length:
- **4+ lines** (real body paragraphs) — merged into a single wrapping `<div>`
  (`white-space:normal`, width = the group's widest original line) and
  reflowed by the browser, with genuine CSS `text-align:justify` +
  `text-align-last:left`. In testing this reproduced line breaks nearly
  identical to the PDF's own, since the width matches the original column.
- **2-3 lines** (short quote/caption blocks) — kept at the PDF's own line
  breaks, each line except the last stretched to the group's widest line via
  `text-align-last:justify`. Also the fallback for any 4+ line group that
  has a PDF hyperlink anchored inside it (see below) — merging changes the
  line count on reflow, which would leave the link overlay's fixed
  (pre-reflow) position misaligned with the now-differently-wrapped text.
- Headings and photo captions are naturally excluded (2-3 lines, but
  `MIN_MERGE_GROUP_LINES` and the same-length-run heuristic keep them out of
  the merge path; justify-stretching a large bold heading looks
  stretched/awkward in a way it doesn't for body text).

**Special per-page handling in the pipeline:**
- **Full-image pages** (`extract.py`'s `FULL_IMAGE_PAGES` set, currently
  empty) — a page whose design truly can't be reproduced as horizontal
  absolutely-positioned text divs (e.g. rotated/curved text following
  hand-drawn art) would be rendered as one flat `.jpg` with no text overlay
  at all, instead of the usual redact-text-then-overlay-divs treatment. Pages
  like 33 and 47 have a hand-drawn vine graphic but their text labels are
  plain horizontal strings, so they go through the normal pipeline fine.
- **PDF hyperlinks** are extracted automatically (`page.get_links()`) and
  become real `<a target="_blank">` overlays positioned over the link's
  original rect — invisible until hovered, since the link text is already
  visible in the background image.
- **YouTube links** specifically (any `youtube.com/watch`, `youtu.be`, or
  `youtube.com/embed` URL) become a live `<iframe>` embed in the same spot
  instead of a plain link-out.

See **`webapp/README.md`** for how the flipbook itself works (page-flip
integration, the config file, the details-modal feature, and several
non-obvious implementation gotchas).

## Deployment

GitHub Pages, built by GitHub Actions (`.github/workflows/deploy.yml`): every push
to `main` runs `npm ci && npm run build` inside `webapp/` and publishes
`webapp/dist/`. This is a GitHub Pages *project* site, so `webapp/astro.config.mjs`
sets `base: '/fcif25book'` — if this repo is ever renamed or forked, that value
(and the `site` URL) needs to match.
