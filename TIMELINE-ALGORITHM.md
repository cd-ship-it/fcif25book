# Timeline overlay algorithm

How the FiCF 25 "恩典長河" timeline works, and how to wire up the production
background once it's supplied. This is a standalone prototype — not part of
`generate.py`'s book-page pipeline.

## The core idea

Don't redraw the artwork. The wave, bubbles, and year numbers are already a
finished graphic — trying to recreate them in HTML/CSS/SVG is guesswork
(color, exact curve shape, spacing) with no upside. Instead:

1. Use the real image as a plain CSS `background-image`, at its native
   pixel size, untouched.
2. Overlay **only the data that isn't in the image**: each event's title
   (and, for years with more than one event, all of them stacked) plus a
   hover/tap tooltip with the full description — as absolutely-positioned
   `<div>`s sitting on top, placed at the real bubble's pixel coordinates.

This is why `test1.html`/`test2.html`/`timeline-exact.html` (which redraw
the wave+bubbles from scratch) were superseded by `timeline-overlay.html`
(which doesn't) — once a real background exists, recreating it is strictly
worse: more effort, and it can only ever approximate the source.

## Files

- **`timeline.js`** — the renderer, dependency-free vanilla JS. Two entry
  points (`renderTimelineOverlay` for one image/one page,
  `renderTimelineSplitOverlay` for a two-page spread — see below), plus
  `renderTimeline`/`wireTimelineTooltip` which are the earlier from-scratch
  version's internals (kept for `test1.html`/`test2.html`/`timeline-exact.html`,
  not needed for the overlay approach).
- **`timeline.css`** — shared styles: `.titles`/`.event-title`/`.event-tag`
  (the label stacks) and `#tooltip` (the hover popup). Same classes serve
  both the overlay and from-scratch renderers.
- **`timeline-overlay.html`** — single-image reference implementation,
  currently pointed at `timeline1.jpg` (the placeholder/reference art) with
  all 25 events from `ficf-25.md`. This is the one to copy from.

## Data model

```js
{
  year: 2011,
  x: 456, y: 186,      // the bubble's pixel center IN THE BACKGROUND IMAGE
  dir: 'up',           // 'up' = bubble sits above the wave -> title(s) render ABOVE it
                        // 'down' = bubble sits below the wave -> title(s) render BELOW it
  events: [
    { tag: '【內程】', title: '靈命塑造', desc: '成立「靈命塑造」事工，提供實體與網路課程及屬靈導引等。' },
    { title: '購置「基督豐榮中心」', desc: '購入北加州海沃（Hayward）物業...' },
  ],
}
```

`tag` is optional (renders as a small purple prefix, e.g. "【啟程】"). A year
with N events just gets N stacked `.event-title` lines, each independently
hoverable.

## Measuring bubble coordinates in a new image

There's no vector source to read coordinates from — they're measured by
eye against the image. Fastest way: open the image in a browser tab, use
the browser devtools "zoom"/inspect to read pixel position of the cursor,
or open it in any image editor that shows a live cursor-position readout
(Preview.app's loupe, Figma, Photoshop, etc.) and read off each bubble's
center. Get `x`, `y`, and note `dir` (is the title going above or below).
Bubble radius is currently assumed **38px** — pass `radius` in `opts` if
the production art uses a different bubble size.

## Single-page usage (`renderTimelineOverlay`)

```js
renderTimelineOverlay(document.getElementById('canvas'), points, {
  radius: 38,      // bubble radius in the image, px (default 38)
  gap: 10,         // clearance between bubble edge and title block (default 10)
  titleWidth: 140, // width of the stacked-title box, px (default 140)
});
```
The container needs `background-image`/`background-size` set to the image
at its native size (see `timeline-overlay.html`'s `.canvas` CSS) — the
function only adds the title/tooltip overlay, it doesn't touch the
background itself.

## Two-page ("spread") usage — for the production background

**What to ask for in the production art**: a single wide image containing
*both* pages' worth of timeline, with a **deliberate clear/empty gutter
zone** down the middle — wide enough, and positioned such that no bubble,
stem, or label sits within it — where the two pages will be cut apart.
Mobile shows one page at a time (matches the flipbook's existing
`responsive.mobileBreakpointPx` single-page mode), so that gutter is what
keeps a bubble from ever being sliced in half across the two pages.

The image itself does **not** need to be pre-cut into two files — one
image, two containers, each showing its own half via `background-position`:

```js
renderTimelineSplitOverlay({
  imageUrl: 'timeline-production.jpg',
  imageWidth: 1390,     // full artwork size — e.g. exactly 2x a 695px book page
  imageHeight: 900,
  splitX: 695,           // x (in the FULL image, px) of the gutter's center —
                          // page 1 shows [0, splitX), page 2 shows [splitX, imageWidth)
  pageWidth: 695,
  pageHeight: 900,
  leftContainer: document.getElementById('page1-canvas'),
  rightContainer: document.getElementById('page2-canvas'),
  points,                // x/y in FULL-IMAGE coordinates — split/rebase is automatic
});
```

What it does:
- Sets both containers' background to the *same* full image at native
  size, `leftContainer` at `background-position: 0 0`, `rightContainer` at
  `background-position: -${splitX}px 0` — so each shows exactly its half,
  no image editor round-trip needed.
- Partitions `points` by `x < splitX` vs `x >= splitX`, and rebases the
  right-hand page's points to `x - splitX` (their own local coordinate
  space) automatically — the source data just uses one consistent
  full-image coordinate system throughout; you never hand-split it.
- Both containers get tagged `.tl-canvas` so the tooltip clamps to
  whichever page a hovered title is actually on (not the whole document,
  and not the other page) — verified via a smoketest with two side-by-side
  canvases before this was written up.

### When the production background arrives

1. Save it into the project root (or wherever), note its exact pixel
   dimensions and the gutter's x-coordinate.
2. Re-measure each bubble's `(x, y)` against the new image (old
   `timeline-overlay.html` coordinates were measured against
   `timeline1.jpg` specifically — they won't line up with a different
   piece of art).
3. Copy `timeline-overlay.html`, swap in `renderTimelineSplitOverlay` with
   the new image's dimensions/gutter x and two page containers instead of
   one.
4. `ficf-25.md`'s event text can be copied over as-is — the `events` data
   doesn't depend on the artwork, only `x`/`y`/`dir` do.
