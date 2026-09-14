// Lightweight, dependency-free timeline renderer for the FiCF 25 "恩典長河"
// spread (test1.html / test2.html). Not part of the generate.py pipeline —
// this is a standalone design prototype.
//
// renderTimeline(container, points) where `points` is:
//   [{ year, dir: 'up'|'down', milestone?: bool,
//      events: [{ tag?: string, title: string, desc: string }] }, ...]
//
// Layout: an SVG dashed "river" path runs through a fixed upper/lower spine
// height, alternating per point's `dir`. Each point gets a stem out to a
// year bubble, with its event title(s) stacked on the far side of the
// bubble from the spine (above it if dir:'up', below if dir:'down') —
// hovering (or tapping) a title shows that event's description in a
// shared tooltip.

const TL_W = 695;
const TL_H = 900;
const TL_UPPER_SPINE_Y = 430;
const TL_LOWER_SPINE_Y = 500;
const TL_UP_BUBBLE_Y = 268;
const TL_DOWN_BUBBLE_Y = 652;
// Must be >= half the .titles box width (see timeline.css) plus a little
// breathing room, or the first/last points' stacked titles bleed off the
// page edge — that box is centered on the bubble's x, not the bubble
// itself, so it needs more clearance than the bubble alone.
const TL_MARGIN = 72;
const BUBBLE_R = 32;

function renderTimeline(container, points) {
  const n = points.length;
  const usable = TL_W - TL_MARGIN * 2;
  const xs = points.map((_, i) => (n === 1 ? TL_W / 2 : TL_MARGIN + (usable * i) / (n - 1)));
  const spineYs = points.map((p) => (p.dir === 'up' ? TL_UPPER_SPINE_Y : TL_LOWER_SPINE_Y));

  const svgNS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(svgNS, 'svg');
  svg.setAttribute('class', 'timeline-svg');
  svg.setAttribute('viewBox', `0 0 ${TL_W} ${TL_H}`);

  // Smooth S-curve "flow" path through the alternating spine heights —
  // a cubic bezier per segment with control points at the horizontal
  // midpoint gives the same look as a step chart with rounded transitions.
  let d = `M ${xs[0]},${spineYs[0]}`;
  for (let i = 1; i < n; i++) {
    const x0 = xs[i - 1], y0 = spineYs[i - 1], x1 = xs[i], y1 = spineYs[i];
    const midX = (x0 + x1) / 2;
    d += ` C ${midX},${y0} ${midX},${y1} ${x1},${y1}`;
  }
  const path = document.createElementNS(svgNS, 'path');
  path.setAttribute('class', 'wave-path');
  path.setAttribute('d', d);
  svg.appendChild(path);

  points.forEach((p, i) => {
    const x = xs[i];
    const ySpine = spineYs[i];
    const yBubbleEdge = p.dir === 'up' ? TL_UP_BUBBLE_Y + BUBBLE_R : TL_DOWN_BUBBLE_Y - BUBBLE_R;

    const stem = document.createElementNS(svgNS, 'line');
    stem.setAttribute('class', 'stem');
    stem.setAttribute('x1', x);
    stem.setAttribute('y1', ySpine);
    stem.setAttribute('x2', x);
    stem.setAttribute('y2', yBubbleEdge);
    svg.appendChild(stem);

    const dot = document.createElementNS(svgNS, 'circle');
    dot.setAttribute('class', 'spine-dot');
    dot.setAttribute('cx', x);
    dot.setAttribute('cy', ySpine);
    dot.setAttribute('r', 4);
    svg.appendChild(dot);
  });

  container.appendChild(svg);

  points.forEach((p, i) => {
    const x = xs[i];
    const yBubble = p.dir === 'up' ? TL_UP_BUBBLE_Y : TL_DOWN_BUBBLE_Y;

    const bubble = document.createElement('div');
    bubble.className = 'bubble' + (p.milestone ? ' is-milestone' : '');
    bubble.style.left = x + 'px';
    bubble.style.top = yBubble + 'px';
    bubble.textContent = p.year;
    container.appendChild(bubble);

    const titleWrap = document.createElement('div');
    titleWrap.className = 'titles dir-' + p.dir;
    titleWrap.style.left = x + 'px';
    titleWrap.style.top = (p.dir === 'up' ? yBubble - BUBBLE_R - 12 : yBubble + BUBBLE_R + 12) + 'px';

    p.events.forEach((ev) => {
      const t = document.createElement('span');
      t.className = 'event-title';
      t.tabIndex = 0;
      t.innerHTML = (ev.tag ? `<span class="event-tag">${ev.tag}</span> ` : '') + ev.title;
      t.dataset.year = p.year;
      t.dataset.title = ev.title;
      t.dataset.desc = ev.desc;
      titleWrap.appendChild(t);
    });

    container.appendChild(titleWrap);
  });

  wireTimelineTooltip(container);
}

function wireTimelineTooltip(container) {
  let tooltip = document.getElementById('tooltip');
  if (!tooltip) {
    tooltip = document.createElement('div');
    tooltip.id = 'tooltip';
    document.body.appendChild(tooltip);
  }

  let activeEl = null;

  function show(el) {
    activeEl = el;
    tooltip.innerHTML =
      `<div class="tt-title"><span class="tt-year">${el.dataset.year}</span>${el.dataset.title}</div>` +
      `<div>${el.dataset.desc}</div>`;
    tooltip.classList.add('open');
    position(el);
    // Re-clamp after layout settles the tooltip's real (content-dependent) height.
    requestAnimationFrame(() => position(el));
  }

  function hide() {
    activeEl = null;
    tooltip.classList.remove('open');
  }

  function position(el) {
    // .page (renderTimeline's book-page canvas), .canvas (single-image
    // overlay), .tl-canvas (split-page overlay) — clamp the tooltip to
    // whichever one actually bounds this element, not document.body, or
    // a tooltip on the LEFT split page could clamp using the RIGHT page's
    // (or the whole body's) bounds instead of its own.
    const pageEl = el.closest('.page, .canvas, .tl-canvas') || document.body;
    const pageRect = pageEl.getBoundingClientRect();
    const elRect = el.getBoundingClientRect();
    const tw = tooltip.offsetWidth || 260;
    const th = tooltip.offsetHeight || 60;

    let left = elRect.left + elRect.width / 2 - tw / 2;
    left = Math.max(pageRect.left + 8, Math.min(left, pageRect.right - tw - 8));

    let top = elRect.top - th - 10;
    if (top < pageRect.top + 8) top = elRect.bottom + 10;

    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
  }

  container.addEventListener('mouseover', (e) => {
    const el = e.target.closest('.event-title');
    if (!el) return;
    el.classList.add('is-active');
    show(el);
  });
  container.addEventListener('mouseout', (e) => {
    const el = e.target.closest('.event-title');
    if (!el) return;
    el.classList.remove('is-active');
    hide();
  });
  container.addEventListener('focusin', (e) => {
    const el = e.target.closest('.event-title');
    if (el) show(el);
  });
  container.addEventListener('focusout', (e) => {
    const el = e.target.closest('.event-title');
    if (el) hide();
  });
  // Tap-to-toggle fallback for touch devices (no real hover state).
  container.addEventListener('click', (e) => {
    const el = e.target.closest('.event-title');
    if (!el) return;
    if (activeEl === el) hide();
    else show(el);
  });
}

// Dismissible floating hint on pages 8–9. Closing one dismisses both
// (and stays dismissed across reloads / flipbook rebuilds) via localStorage
// + a body class that CSS uses to hide every .timeline-hint.
const TIMELINE_HINT_KEY = 'ficf-timeline-hint-dismissed';

function dismissTimelineHint() {
  try {
    localStorage.setItem(TIMELINE_HINT_KEY, '1');
  } catch (_) { /* private mode / blocked storage */ }
  document.body.classList.add('timeline-hint-dismissed');
}

function wireTimelineHint() {
  try {
    if (localStorage.getItem(TIMELINE_HINT_KEY) === '1') {
      document.body.classList.add('timeline-hint-dismissed');
    }
  } catch (_) { /* ignore */ }

  if (wireTimelineHint._wired) return;
  wireTimelineHint._wired = true;

  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.timeline-hint-close');
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    dismissTimelineHint();
  });
}

// renderTimelineOverlay(container, points, opts) — for timeline-overlay.html.
// Draws ONLY the event-title labels + hover tooltip wiring on top of an
// existing background (the real timeline1.jpg), reusing the same
// .titles/.event-title/#tooltip CSS and tooltip logic as renderTimeline()
// above, but skipping the SVG wave/bubbles entirely since the background
// image already has them baked in — no need to redraw what's already there.
//
// `points` here carries its own explicit `x`/`y` (the bubble's actual pixel
// center in the background image) per point, since — unlike renderTimeline,
// which auto-spaces points along two fixed spine heights — every bubble in
// a real photo/graphic sits at its own unique, hand-measured position.
//   points: [{ year, x, y, dir: 'up'|'down',
//              events: [{ tag?, title, desc }] }, ...]
function renderTimelineOverlay(container, points, opts) {
  container.classList.add('tl-canvas');
  const radius = (opts && opts.radius) || 38; // bubble radius in the background image, px
  const gap = (opts && opts.gap) || 10; // clearance between bubble edge and title block
  const titleWidth = (opts && opts.titleWidth) || 140;

  points.forEach((p) => {
    const titleWrap = document.createElement('div');
    titleWrap.className = 'titles dir-' + p.dir;
    titleWrap.style.left = p.x + 'px';
    titleWrap.style.width = titleWidth + 'px';
    titleWrap.style.top = (p.dir === 'up' ? p.y - radius - gap : p.y + radius + gap) + 'px';

    p.events.forEach((ev) => {
      const t = document.createElement('span');
      t.className = 'event-title';
      t.tabIndex = 0;
      t.innerHTML = (ev.tag ? `<span class="event-tag">${ev.tag}</span> ` : '') + ev.title;
      t.dataset.year = p.year;
      t.dataset.title = ev.title;
      t.dataset.desc = ev.desc;
      titleWrap.appendChild(t);
    });

    container.appendChild(titleWrap);
  });

  wireTimelineTooltip(container);
}

// renderTimelineSplitOverlay(config) — the two-page ("spread") version of
// renderTimelineOverlay, for a wide production artwork that has a
// deliberate clear/gutter zone built into it so it can be cut in half for
// mobile (one page on screen at a time) without slicing through a bubble
// or label. See TIMELINE-ALGORITHM.md for the full write-up.
//
// The image itself is NOT cut — both containers get the SAME full-width
// background at native size, each shifted via background-position to show
// only its own half (so nothing needs pre-cropping in an image editor).
// Points are auto-partitioned by which side of `splitX` they fall on, with
// x rebased into that container's own local coordinate space.
//
// config = {
//   imageUrl, imageWidth, imageHeight,     // the full, uncut artwork
//   splitX,                                // x (full-image px) of the gutter — page 1 ends / page 2 begins here
//   pageWidth, pageHeight,                 // size of EACH resulting page
//   leftContainer, rightContainer,         // DOM elements to render into
//   points,                                // same shape as renderTimelineOverlay; x/y in FULL-IMAGE coordinates
//   radius, gap, titleWidth,               // optional, forwarded to renderTimelineOverlay
// }
function renderTimelineSplitOverlay(config) {
  const { imageUrl, imageWidth, imageHeight, splitX, pageWidth, pageHeight, leftContainer, rightContainer, points } = config;

  function setupCanvas(el, bgOffsetX) {
    el.style.position = 'relative';
    el.style.width = pageWidth + 'px';
    el.style.height = pageHeight + 'px';
    el.style.overflow = 'hidden';
    el.style.backgroundImage = `url('${imageUrl}')`;
    el.style.backgroundSize = `${imageWidth}px ${imageHeight}px`;
    el.style.backgroundRepeat = 'no-repeat';
    el.style.backgroundPosition = `-${bgOffsetX}px 0`;
  }

  setupCanvas(leftContainer, 0);
  setupCanvas(rightContainer, splitX);

  const leftPoints = points.filter((p) => p.x < splitX);
  const rightPoints = points
    .filter((p) => p.x >= splitX)
    .map((p) => Object.assign({}, p, { x: p.x - splitX }));

  renderTimelineOverlay(leftContainer, leftPoints, config);
  renderTimelineOverlay(rightContainer, rightPoints, config);
}
