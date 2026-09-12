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
../FiCF 25 Book-level 1.pdf
        │  extract.py   (PyMuPDF: renders text-free backgrounds, dumps text spans)
        ▼
../data/pages.json, ../assets/backgrounds/*.png, ../assets/fonts/*
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

It's safe to re-run — it fully regenerates everything under `src/generated/`
and `public/assets/` + `public/generated/`. It reads `../data/titles.json`
to know how many pages exist, so extending this to all 93 pages later is
just: extend the `range(1, 10)` → `range(1, 94)` loops in `../generate.py`,
rebuild there, then re-run this sync script. Nothing in this app hardcodes
"10".

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

## "閱讀全文" (Read Full Text) details modal

Each "閱讀全文" button in the source PDF is a button-shaped graphic baked
into that page's background PNG, with only its text as real HTML (one of
the `.t` spans in `src/generated/fragments/pageN.html`). Clicking it pops
open a modal showing the full article, sourced from a markdown file.

- **`src/config/readmore.config.ts`** — maps each trigger's element id
  (`p{page}-t{n}`, found by grepping the parent project's
  `data/pages.json` for "閱讀全文" then checking that page's `.html` for the
  id `generate.py` assigned) to a markdown filename under `src/details/`.
- **`src/details/pageNreadmore.md`** — one file per button, frontmatter
  `title` / `subtitle` / `page` + the article body in Markdown. A link in
  `readmore.config.ts` with no matching file is skipped with a build-time
  `console.warn`, not a build failure.
- Currently pages 6 and 7 (the only "閱讀全文" buttons in pages 1–10) have
  **placeholder/bogus content** — the PDF only contains each article's
  opening teaser, not the full text, so `page6readmore.md` /
  `page7readmore.md` are stand-ins clearly marked as such. Replace their
  body text with the real articles before shipping.
- `src/pages/index.astro` renders one hidden `.detail-panel` per matched
  link inside a shared `#detail-overlay`; `readmore.client.ts` shows/hides
  the right panel on click and closes on the ✕ button, Escape, or backdrop
  click.
