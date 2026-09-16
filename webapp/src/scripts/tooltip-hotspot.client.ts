// Reusable tooltip-hotspot + dismissible hint-bubble wiring. Ported from
// ../../../timeline.js's wireTooltipHotspots/wireHintBubbles (used as-is by
// the standalone pageN.html previews via a plain <script> tag). Originally
// built for the timeline spread (generate.py's TIMELINE_PAGES, pages 8-9)
// but neither piece is timeline-specific — generate.py's
// emit_tooltip_hotspot/emit_hint_bubble helpers can place one on any page.
// Same logic here, adapted two ways for the app:
//   - event delegation on the stable #stage (hotspots/hint-bubbles are
//     children of #book, which flipbook.client.ts destroys and recreates on
//     every desktop/mobile breakpoint crossing — a listener on one directly
//     wouldn't survive a rebuild; same reasoning as readmore.client.ts /
//     photo-zoom.client.ts).
//   - TypeScript types instead of vanilla JS.
// Keep this in sync with timeline.js's wireTooltipHotspots/wireHintBubbles
// if any changes.

// Dismissing a hint bubble hides every bubble sharing its data-hint-group
// (generate.py's hints_config.json — entries reusing the same `id` share a
// group), not just the one instance clicked — so pages 8 and 9's identical
// "timeline-hint" pair close together, while unrelated tips (different
// group) never cross-dismiss each other. Still only for the rest of THIS
// view: dismissedGroups is an in-memory Set, nothing persisted, so a
// refresh always shows every tip again.
//
// The tricky part is mobile: renderMobilePage (flipbook.client.ts) clones
// each page fresh from a pristine template on every navigation, so a
// group already dismissed needs to be re-applied to that brand-new,
// never-clicked markup too — a MutationObserver on #stage catches every
// such insertion (desktop's rebuilds go through the same #stage, so one
// observer covers both) and re-hides any bubble whose group is already in
// the set.
const dismissedGroups = new Set<string>();

function applyDismissedGroups(root: Element): void {
  const bubbles = root.matches('.hint-bubble[data-hint-group]')
    ? [root]
    : Array.from(root.querySelectorAll('.hint-bubble[data-hint-group]'));
  for (const el of bubbles) {
    const group = (el as HTMLElement).dataset.hintGroup;
    if (group && dismissedGroups.has(group)) el.classList.add('dismissed');
  }
}

function dismissGroup(group: string): void {
  dismissedGroups.add(group);
  document
    .querySelectorAll<HTMLElement>(`.hint-bubble[data-hint-group="${CSS.escape(group)}"]`)
    .forEach((el) => el.classList.add('dismissed'));
}

function wireHintBubbles(): void {
  const stage = document.getElementById('stage');
  if (!stage || stage.dataset.hintBubblesWired === '1') return;
  stage.dataset.hintBubblesWired = '1';

  stage.addEventListener('click', (e) => {
    const btn = (e.target as Element | null)?.closest?.('.hint-bubble-close');
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    const bubble = btn.closest<HTMLElement>('.hint-bubble');
    const group = bubble?.dataset.hintGroup;
    if (group) dismissGroup(group);
    else bubble?.classList.add('dismissed'); // no group configured — just this one
  });

  new MutationObserver((mutations) => {
    for (const m of mutations) {
      m.addedNodes.forEach((node) => {
        if (node instanceof Element) applyDismissedGroups(node);
      });
    }
  }).observe(stage, { childList: true, subtree: true });
}

function init(): void {
  const stage = document.getElementById('stage');
  if (!stage) return;

  wireHintBubbles();

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
      `<div class="tt-desc">${el.dataset.desc ?? ''}</div>`;
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
