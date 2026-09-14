// Ported from ../../../timeline.js's wireTimelineTooltip (used as-is by the
// standalone pageN.html previews via a plain <script> tag — see
// generate.py's TIMELINE_PAGES). Same logic, adapted two ways for the app:
//   - event delegation on the stable #stage (the .event-title hotspots are
//     children of #book, which flipbook.client.ts destroys and recreates on
//     every desktop/mobile breakpoint crossing — a listener on a hotspot
//     itself wouldn't survive a rebuild; same reasoning as
//     readmore.client.ts / photo-zoom.client.ts).
//   - TypeScript types instead of vanilla JS.
// Keep this in sync with timeline.js's wireTimelineTooltip if either changes.

// Dismissible floating hint on pages 8-9. Closing it hides it for the rest
// of THIS view only (a body class CSS uses to hide every .timeline-hint) —
// deliberately not persisted anywhere, so a refresh always shows it again.
function dismissTimelineHint(): void {
  document.body.classList.add('timeline-hint-dismissed');
}

function wireTimelineHint(): void {
  const stage = document.getElementById('stage');
  if (!stage || stage.dataset.timelineHintWired === '1') return;
  stage.dataset.timelineHintWired = '1';

  stage.addEventListener('click', (e) => {
    const btn = (e.target as Element | null)?.closest?.('.timeline-hint-close');
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    dismissTimelineHint();
  });
}

function init(): void {
  const stage = document.getElementById('stage');
  if (!stage) return;

  wireTimelineHint();

  let tooltip = document.getElementById('tooltip');
  if (!tooltip) {
    tooltip = document.createElement('div');
    tooltip.id = 'tooltip';
    document.body.appendChild(tooltip);
  }
  const tt = tooltip;

  let activeEl: HTMLElement | null = null;

  function show(el: HTMLElement): void {
    activeEl = el;
    tt.innerHTML =
      `<div class="tt-title"><span class="tt-year">${el.dataset.year ?? ''}</span>${el.dataset.title ?? ''}</div>` +
      `<div>${el.dataset.desc ?? ''}</div>`;
    tt.classList.add('open');
    position(el);
    // Re-clamp after layout settles the tooltip's real (content-dependent) height.
    requestAnimationFrame(() => position(el));
  }

  function hide(): void {
    activeEl = null;
    tt.classList.remove('open');
  }

  function position(el: HTMLElement): void {
    const pageEl = el.closest('.page, .canvas, .tl-canvas') ?? document.body;
    const pageRect = pageEl.getBoundingClientRect();
    const elRect = el.getBoundingClientRect();
    const tw = tt.offsetWidth || 260;
    const th = tt.offsetHeight || 60;

    let left = elRect.left + elRect.width / 2 - tw / 2;
    left = Math.max(pageRect.left + 8, Math.min(left, pageRect.right - tw - 8));

    let top = elRect.top - th - 10;
    if (top < pageRect.top + 8) top = elRect.bottom + 10;

    tt.style.left = `${left}px`;
    tt.style.top = `${top}px`;
  }

  function eventTitleFor(target: EventTarget | null): HTMLElement | null {
    if (!(target instanceof Element)) return null;
    return target.closest<HTMLElement>('.event-title');
  }

  stage.addEventListener('mouseover', (e) => {
    const el = eventTitleFor(e.target);
    if (!el) return;
    el.classList.add('is-active');
    show(el);
  });
  stage.addEventListener('mouseout', (e) => {
    const el = eventTitleFor(e.target);
    if (!el) return;
    el.classList.remove('is-active');
    hide();
  });
  stage.addEventListener('focusin', (e) => {
    const el = eventTitleFor(e.target);
    if (el) show(el);
  });
  stage.addEventListener('focusout', (e) => {
    const el = eventTitleFor(e.target);
    if (el) hide();
  });
  // Tap-to-toggle fallback for touch devices (no real hover state).
  stage.addEventListener('click', (e) => {
    const el = eventTitleFor(e.target);
    if (!el) return;
    if (activeEl === el) hide();
    else show(el);
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
