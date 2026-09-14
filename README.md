# FiCF 25 週年紀念電子書

A PDF-to-HTML/CSS conversion of "FiCF 25 Book-Stage1.3.pdf" (93 pages), rendered as a
two-page-spread flipbook.

**Live site:** https://cd-ship-it.github.io/fcif25book/ (deployed automatically by
`.github/workflows/deploy.yml` on every push to `main`)

## Layout

```
FiCF 25 Book-Stage1.3.pdf   — source document (93 pages)
extract.py                 — PDF -> assets/backgrounds/*.png|jpg (text-redacted, 2x retina)
                                 + assets/backgrounds/*.webp (displayed copy, see below)
                                 + assets/photos/*.jpg (original-resolution real photos, see below)
                              + data/pages.json (text spans, PDF hyperlinks, photos, position/font/size/color)
                              + data/outline.json (PDF bookmarks, for auto page titles)
generate.py                — data/pages.json -> pages/pageN.html / pageN.generated.css / pageN.css
                              (per page: standalone preview + generated + hand-editable CSS)
                              + data/titles.json (manifest: page count + titles)
pages/                     — the 93 standalone previews + their shared style.css, one directory
                              down from the root (assets/ paths inside are '../assets/...')
index.html                 — thumbnail gallery of all pages/pageN.html previews
assets/                    — backgrounds (PNG/JPG + WebP) + fonts + original-res photos per page

details/*.md               — "閱讀全文" article source (title/author/body, see below)
details/images/            — inline images those articles reference

Timeline/                  — timeline spread (pages 8-9) source PDF + data, see below

PhotoAlbums/Page N Photo Slides/  — real photos for the pages 37/45/53 carousels, see below

webapp/                    — the actual deployed flipbook app (Astro + page-flip)
  scripts/sync-from-source.mjs   — pulls the pipeline output above into webapp/src + webapp/public
  scripts/sync-details.mjs       — pulls details/*.md into webapp/src/details/, auto-generates
                                    src/config/readmore.config.ts (see webapp/README.md)
  src/config/flipbook.config.ts  — book size, toolbar features, labels, palette
  README.md                      — full app-level documentation
```

**Regenerating from the PDF** (e.g. after editing a `pageN.css` override, or if the
source PDF changes):

```sh
python3 -m venv .venv && ./.venv/bin/pip install pymupdf pillow   # first time only
./.venv/bin/python3 extract.py                 # or: extract.py "Some Other Book.pdf"
./.venv/bin/python3 generate.py
cd webapp && node scripts/sync-from-source.mjs && npm run build
```

`extract.py` takes the PDF path as an optional first argument (defaults to the
constant at the top of the file) — no need to hand-edit the script for a new PDF.

Only `webapp/` is what actually ships — the `pages/pageN.html` files and
`index.html` gallery are a standalone preview/debugging aid, not part of the
deployed site.

**WebP backgrounds:** `extract.py` renders each page's background at 2x retina
resolution as usual (`.png`, or `.jpg` for a `FULL_IMAGE_PAGES` entry), then
also saves a lossy WebP copy (quality 85, or 82 for a JPG source) via Pillow.
`generate.py`'s CSS always points the displayed background at the `.webp`
file — the original `.png`/`.jpg` is kept on disk untouched (not referenced
in the background CSS, not deleted). Across all 93 pages this cut total
background weight from ~88MB to ~5MB (94%), with no visible quality loss at
the size these are actually displayed. The `page-flip` book only fetches a
given page's background the moment that page is actually flipped to (each
page's `<div>` toggles `display:none`/`block`), so this saves bandwidth per
page turn rather than as one large upfront batch.

**Click-to-zoom photos:** `extract.py` also pulls out every *real content
photo* embedded in the PDF, at its original never-resized/recompressed
resolution, to `assets/photos/pageN-photoI.jpg`. The book has plenty of
other embedded raster images that are NOT real photos — watercolor washes,
leaf-motif line art, a generic "Photo Slides not ready yet" stock
illustration reused on 3 pages (see below) — so two purely mechanical,
zero-exception-across-the-whole-book signals separate them:
- **Format** — every decorative graphic in this design is PNG (needs alpha
  transparency to blend with the page background); every real photo is JPEG.
- **Uniqueness** — a real photo's exact byte content appears exactly once in
  the whole PDF. A couple of JPEGs *are* reused byte-for-byte across pages
  (the stock "Photo Slides" placeholder, an abstract background texture on
  pages 14/15) — those are decorative too, just happen to be saved as JPEG.
  Excluding any content-hash seen more than once catches both, with no
  page-specific list to maintain.

**Photo Slides carousels** (pages 37/45/53, `extract.py`'s
`PHOTO_ALBUM_PAGES` / `generate.py`'s `PHOTO_ALBUM_PAGES`): the PDF places
that same reused "Photo Slides" placeholder graphic + text label on these 3
pages as a stand-in for a real slideshow, supplied separately outside the
main PDF at `PhotoAlbums/Page N Photo Slides/*` (alphabetical filename
order; a stray non-image file like a poster `.pdf` has its first page
rendered to an image and included in its alphabetical position). Each photo
is letterboxed — resized to fit, black bars filling the rest — to exactly
the placeholder's own on-page box (`PHOTO_ALBUM_BOX_PT`, measured from the
rendered graphic itself, not `get_image_info()`'s declared bbox, which
overshoots the page edges the same way page 36's photo did — see
`generate.py`'s comment) and re-encoded as a compressed JPEG, since several
source photos are straight off a phone camera at up to ~14MB. A caption is
derived from each filename (leading `_`/whitespace and the extension
stripped). `generate.py` emits a `.photo-album` div at that position with
every slide's `<img>` stacked inside (all but the first `hidden`) plus
prev/next buttons; the webapp's `photo-album.client.ts` (event delegation
on `#stage`, same pattern as `readmore.client.ts`/`photo-zoom.client.ts`)
toggles which one shows and updates the caption — always reopening at slide
1, no position memory.

`generate.py` positions an invisible `.photo-zoom` hit-area over each kept
photo (same technique as the PDF-hyperlink overlays); the webapp's
`photo-zoom.client.ts` opens the original file in a lightbox on click.

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
- **Timeline spread** (pages 8-9, `extract.py`'s `TIMELINE_PAGES` /
  `generate.py`'s `TIMELINE_PAGES`) — a separately hand-designed artwork
  (`Timeline/Timeline-Years and Titles.pdf`) replaces the main book's own
  pages 8/9 (both were blank spacer pages) entirely. That PDF is a single
  1224x792pt page — exactly two of this book's own 612x792pt pages side by
  side — split at its horizontal midpoint (612pt) into this book's normal
  per-page background image pair. Event titles are read from the timeline
  PDF's own vector text and matched by content against
  `Timeline/Timeline-Years and Titles.md`'s descriptions; each becomes an
  invisible hover hotspot (the title/tag text is already part of the
  background image, same "don't redraw a finished graphic" reasoning as the
  standalone `Timeline/test.html` prototype this was promoted from — see
  `TIMELINE-ALGORITHM.md`) showing a popup with the year/title/description
  on hover (desktop) or tap (mobile). Re-running `extract.py`/`generate.py`
  regenerates pages 8/9 from that same timeline PDF/md every time — nothing
  about them depends on the main `FiCF 25 Book-*.pdf`.

**"閱讀全文" (Read Full Text) articles:** each button in the book pops open
the corresponding article from `details/`. One markdown file per button —
`Page N.md` for a page with a single button, `Page N Left.md` / `Right.md`
or `Page N Top.md` / `Bottom.md` for a page with two (a trailing
parenthetical in the filename, e.g. `Page 57 (with in text photos).md`, is
just a note-to-self, ignored when matching). Format: a `# Title` heading, an
`*Author*` line, then the article body in plain Markdown — an inline image
is `![](images/foo.jpg)` referencing a same-named file in `details/images/`.
`webapp/scripts/sync-details.mjs` turns this into the webapp's
`readmore.config.ts` + `src/details/*.md` automatically (see
`webapp/README.md`) — matching each file to its "閱讀全文" trigger element by
reading the already-generated `pageN.html`/`pageN.generated.css`, not a
hardcoded list, so it self-updates if the trigger's element id shifts (e.g.
after a book-wide formatting change renumbers `.t` divs) or a page's button
count changes on a future PDF revision.

See **`webapp/README.md`** for how the flipbook itself works (page-flip
integration, the config file, the details-modal feature, and several
non-obvious implementation gotchas).

## Deployment

GitHub Pages, built by GitHub Actions (`.github/workflows/deploy.yml`): every push
to `main` runs `npm ci && npm run build` inside `webapp/` and publishes
`webapp/dist/`. This is a GitHub Pages *project* site, so `webapp/astro.config.mjs`
sets `base: '/fcif25book'` — if this repo is ever renamed or forked, that value
(and the `site` URL) needs to match.
