# FiCF 25 — Flipbook

A two-page-spread flipbook viewer for the "FiCF 25" ebook, built with Astro +
[page-flip](https://github.com/Nodlik/StPageFlip) (StPageFlip). Page 1 is a
lone cover; pages 2–3, 4–5, 6–7, 8–9 are spreads; page 10 (last, odd count
out) is shown alone — the standard `showCover` book layout.

This app does **not** re-derive page layout itself. It consumes the
695×900 HTML/CSS/background pages already produced by the parent project's
`extract.py` + `generate.py` pipeline (`../extract.py`, `../generate.py`,
one directory up) and adapts them into a single-page flipbook.

## Pipeline

```
../FiCF 25 Book-Stage1.6.pdf
        │  extract.py   (PyMuPDF: renders text-free backgrounds, dumps text spans)
        ▼
../data/pages.json, ../assets/backgrounds/*.png|jpg, ../assets/fonts/*
        │  generate.py  (writes pageN.html, pageN.generated.css, pageN.css, data/titles.json)
        ▼
../pageN.html, ../pageN.generated.css, ../pageN.css, ../style.css
        │  scripts/sync-from-source.mjs   (THIS app's sync step)
        ▼
src/generated/fragments/pageN.html   — just the <div class="page"> for each page
src/generated/manifest.json          — page count + titles, for the TOC drawer
public/generated/book.css            — style.css + all pageN.(generated.)css concatenated
public/assets/backgrounds/*.png, public/assets/fonts/*   — copied straight through
```

Re-run the sync step any time the parent project's pages change:

```sh
node scripts/sync-from-source.mjs
```

It's safe to re-run — it clears and fully regenerates everything under
`src/generated/` and `public/assets/` + `public/generated/` (rather than just
overwriting on top of what's there), so a source file that's renamed or
deleted between runs — e.g. a page's background switching from `.png` to
`.jpg` — doesn't leave a stale orphan copy behind. It reads
`../data/titles.json` to know how many pages exist (currently all 93), so
nothing in this app hardcodes a page count — re-running `../extract.py` +
`../generate.py` against an updated source PDF (even one with a different
page count) and then this sync script is enough to pick it up.

## Configuration

**`src/config/flipbook.config.ts`** is the one file you edit to change how
the book looks/behaves — book dimensions, which toolbar features are on,
all UI copy (currently Traditional Chinese), and the color palette. It's a
single typed object; both the Astro page (build-time toolbar markup) and
the client script (`src/scripts/flipbook.client.ts`, runtime page-flip
behavior) import it, so it's one source of truth. Edit it, then rebuild —
no other file should need touching for config-level changes.

## Commands

| Command                          | Action                                              |
| :-------------------------------- | :--------------------------------------------------- |
| `node scripts/sync-from-source.mjs` | Pull latest pages/assets from the parent project   |
| `npm run dev`                     | Local dev server (`astro dev --background` per this repo's CLAUDE.md) |
| `npm run build`                   | Production build to `./dist/`                       |
| `npm run preview`                 | Preview the production build                        |

## Notable implementation details

- **`src/styles/page-flip-base.css`** — the `page-flip` npm package ships no
  CSS in its `dist/` build (only in `src/`, which isn't published to the
  bundle). This file is a manual copy of the required `.stf__*` structural
  rules, with the upstream `.sft__wrapper` typo corrected to `.stf__wrapper`.
- **Client script must be inline** — `<script>import '../scripts/flipbook.client.ts';</script>`,
  *not* `<script type="module" src="../scripts/flipbook.client.ts">`. Astro
  does not bundle the latter; it passes the `src` through unprocessed,
  which 404s once deployed.
- **Scale-to-fit, not native-size** — `page-flip` in `size:'fixed'` mode
  always lays the book out at a full two-page-spread width (`pageWidth * 2`)
  internally, even for a lone cover page (it just occupies the right half).
  `flipbook.client.ts` gives `#book-shell` that natural 1390×900 box and
  applies a `transform: scale()` (capped at 1, i.e. never upscaled past
  native resolution) to fit whatever room `#stage` actually has, recomputed
  on resize/fullscreen-change.
- **Jump vs. flip** — `pageFlip.flip(n)` / `flipToPage(n)` only steps one
  spread at a time *no matter how far away* `n` is (it's meant for
  animated single-step navigation, e.g. Prev/Next buttons). The page-jump
  input and TOC drawer use `pageFlip.turnToPage(n)` instead, which jumps
  directly (no animation) — using `flip()` there lands on the wrong spread
  for any jump of more than one spread.
- **Click-to-flip vs. "閱讀全文" buttons** — `book.useMouseEvents:false` (the
  default) means `flipbook.client.ts` attaches its own plain click-to-flip
  handler directly on `#book` (left half = prev, right half = next). Any
  "閱讀全文" trigger sits *inside* `#book`, so its own click handler
  (`readmore.client.ts`) must call `e.stopPropagation()` — otherwise opening
  the details modal would also flip the page underneath it.
- **Resume position (`localStorage['ficf25:lastPage']`)** — tapping a PDF
  hyperlink opens it in a new tab; closing that tab and coming back can find
  the browser has silently reloaded this tab from scratch under memory
  pressure (especially on mobile, especially for a page this heavy — 93
  full-page backgrounds + a live YouTube iframe), which with no persisted
  state always restarted at `config.book.startPage`. `flipbook.client.ts`
  saves the current page on every `'flip'` event and restores it on load.
  The same lookup also fixes a second bug for free: `buildBook()` (called
  again whenever the mobile/desktop breakpoint is crossed) used to always
  reset to `config.book.startPage` too, since it read the config value
  unconditionally instead of the live instance's current position — it now
  reads the live `pageFlip`'s position when one exists (a rebuild) and only
  falls back to the saved/config value when there isn't one yet (a real
  fresh load).

## PDF hyperlinks, YouTube embeds, full-image pages

These are entirely `../generate.py`'s doing (real `<a target="_blank">`
overlays for PDF hyperlinks, a live `<iframe>` for a YouTube link, a flat
`.jpg` background with no text overlay for a page whose design can't be
reproduced as horizontal text divs) — this app just receives them as part
of the synced fragment HTML/CSS, no webapp-side code needed. See the root
project's `README.md` for how `extract.py`/`generate.py` produce them.

## Click-to-zoom photos

`../generate.py` positions an invisible `.photo-zoom` overlay div over every
real content photo it kept (see the root `README.md` for the JPEG-format +
uniqueness heuristic that separates real photos from decorative art).
`src/scripts/photo-zoom.client.ts` delegates click/Enter/Space handling on
the stable `#stage` element (same reasoning as `readmore.client.ts` below —
the actual `.photo-zoom` triggers live inside `#book`, which gets destroyed
and recreated on every desktop/mobile rebuild) and opens the matching
`assets/photos/pageN-photoI.jpg` — the untouched original, never resized or
recompressed — in a shared lightbox (`#photo-lightbox` in `index.astro`,
styled in `src/styles/photo-lightbox.css`).

## Photo Slides carousels (pages 37/45/53)

`../generate.py` positions a `.photo-album` div over the reused "Photo
Slides" placeholder graphic on these 3 pages (see the root `README.md` for
how `../extract.py` letterboxes each page's real photos from
`../PhotoAlbums/Page N Photo Slides/*` into `assets/photos/pageN-albumI.jpg`
and produces the caption). Every slide's `<img>` is stacked inside the div
up front (all but the first `hidden`) along with prev/next `<button>`s and
a caption div. `src/scripts/photo-album.client.ts` delegates click handling
on the stable `#stage` element (same reasoning as `photo-zoom.client.ts`
above), toggles which `<img>` is `hidden`, and updates the caption text —
looping at both ends, always starting from slide 1 (no position memory,
even across a desktop/mobile rebuild). Native `<button>`s mean Enter/Space
activation works for free, no extra keydown handling needed like
`readmore.client.ts`'s triggers (plain divs) require below.

## Timeline spread (pages 8-9)

`../generate.py` positions an invisible `.event-hotspot` overlay div over
every event title on the timeline spread (see the root `README.md` for how
`../extract.py` produces those two pages from a separate artwork PDF). The
title/tag text is already part of the background image, so nothing here
draws a visible label — `src/scripts/timeline-tooltip.client.ts` delegates
hover/focus/click handling on the stable `#stage` element (same reasoning
as `photo-zoom.client.ts` above) and shows a popup (`#tooltip`, created
lazily on first use) with that event's year/title/description, styled in
`../style.css` (`.event-hotspot`, `#tooltip`, `.tt-*`). This is a direct
TypeScript port of `../timeline.js`'s `wireTimelineTooltip` — the same
function the standalone `../pageN.html` previews for pages 8/9 call
directly (they don't need delegation; their DOM never gets rebuilt) — keep
the two in sync if either changes.

## "閱讀全文" (Read Full Text) details modal

Each "閱讀全文" button in the source PDF is a button-shaped graphic baked
into that page's background PNG, with only its text as real HTML (one of
the `.t` spans in `src/generated/fragments/pageN.html`). Clicking it pops
open a modal showing the full article, sourced from a markdown file.

- **`../details/*.md` + `../details/images/`** — the source of truth (same
  idea as `../Timeline/` for the timeline feature). One file per button:
  `Page N.md` for a page with one "閱讀全文" button, `Page N Left.md` /
  `Page N Right.md` or `Page N Top.md` / `Page N Bottom.md` for a page with
  two (a trailing parenthetical like `Page 57 (with in text photos).md` is
  ignored when matching — it's just a note-to-self in the filename). Each
  file is plain Markdown: `# Title` heading, an `*Author*` line, then the
  article body — no frontmatter, and an inline image is a normal
  `![](images/foo.jpg)` reference to a same-named file in `../details/images/`.
- **`scripts/sync-details.mjs`** — reads all of the above and:
  1. Writes `src/details/pageNreadmore[Left|Right|Top|Bottom].md`, pulling
     the `#` heading and `*italic*` author line into YAML frontmatter
     (`title`/`subtitle`/`page`) the way `index.astro` expects, and
     rewriting image references to `assets/details-images/...`.
  2. Copies `../details/images/*` to `public/assets/details-images/`.
  3. Auto-generates **`src/config/readmore.config.ts`** — do not hand-edit
     it, it's overwritten on every run. It matches each markdown file to
     its trigger element id (`p{page}-t{n}`) by reading the parent
     project's already-generated `pageN.html`/`pageN.generated.css`
     directly; a page with two buttons is disambiguated by comparing their
     actual rendered position (whichever axis — x or y — actually differs
     between the two decides Left/Right vs Top/Bottom), not a hardcoded
     page list, so a future PDF revision that changes which pages have one
     vs two buttons doesn't need this script updated.
  Run it any time `../details/` changes: `node scripts/sync-details.mjs`
  (order relative to `sync-from-source.mjs` doesn't matter — it reads the
  root project's `pageN.html`/`.generated.css` directly, not the synced
  copies).
- `src/pages/index.astro` renders one hidden `.detail-panel` per matched
  link inside a shared `#detail-overlay`; `readmore.client.ts` shows/hides
  the right panel on click and closes on the ✕ button, Escape, or backdrop
  click.
- Article paragraphs are full-justified with the last line left-aligned
  (`.detail-content p` in `src/styles/details.css`) — a single-line
  paragraph is always treated as a block's "last line" by browsers (never
  justified regardless of `text-align`), so this one rule already covers
  both cases with no separate handling needed.
