# FiCF 25 週年紀念電子書

A PDF-to-HTML/CSS conversion of "FiCF 25 Book-level 1.pdf" (93 pages), rendered as a
two-page-spread flipbook.

**Live site:** https://cd-ship-it.github.io/fcif25book/ (deployed automatically by
`.github/workflows/deploy.yml` on every push to `main`)

## Layout

```
FiCF 25 Book-level 1.pdf   — source document (93 pages)
extract.py                 — PDF -> assets/backgrounds/*.png (text-redacted, 2x retina)
                              + data/pages.json (text spans: position/font/size/color)
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
./.venv/bin/python3 extract.py
./.venv/bin/python3 generate.py
cd webapp && node scripts/sync-from-source.mjs && npm run build
```

Only `webapp/` is what actually ships — the root-level `pageN.html` files and
`index.html` gallery are a standalone preview/debugging aid, not part of the
deployed site.

See **`webapp/README.md`** for how the flipbook itself works (page-flip
integration, the config file, the details-modal feature, and several
non-obvious implementation gotchas).

## Deployment

GitHub Pages, built by GitHub Actions (`.github/workflows/deploy.yml`): every push
to `main` runs `npm ci && npm run build` inside `webapp/` and publishes
`webapp/dist/`. This is a GitHub Pages *project* site, so `webapp/astro.config.mjs`
sets `base: '/fcif25book'` — if this repo is ever renamed or forked, that value
(and the `site` URL) needs to match.
