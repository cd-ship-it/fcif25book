import { readMoreLinks } from '../config/readmore.config';

function init(): void {
  const overlay = document.getElementById('detail-overlay');
  const closeBtn = document.getElementById('detail-close');
  const stage = document.getElementById('stage');
  if (!overlay || !stage) return; // no detail panels were rendered (no matching .md files)

  const panels = overlay.querySelectorAll<HTMLElement>('[data-detail-panel]');
  const idToSlug = new Map(readMoreLinks.map((l) => [l.elementId, l.detailsFile] as const));

  function closeModal(): void {
    overlay!.classList.remove('open');
    overlay!.setAttribute('aria-hidden', 'true');
  }

  function openModal(slug: string): void {
    let found = false;
    panels.forEach((p) => {
      const match = p.dataset.detailPanel === slug;
      p.hidden = !match;
      if (match) found = true;
    });
    if (!found) return;
    overlay!.classList.add('open');
    overlay!.setAttribute('aria-hidden', 'false');
  }

  function triggerSlugFor(target: EventTarget | null): string | null {
    if (!(target instanceof Element)) return null;
    const el = target.closest<HTMLElement>('[id]');
    return el ? idToSlug.get(el.id) ?? null : null;
  }

  // Event delegation on #stage, in the CAPTURE phase, rather than attaching
  // to each trigger element directly:
  //
  // - #stage is stable; the trigger elements are children of #book, which
  //   flipbook.client.ts destroys and recreates every time it switches
  //   between desktop-spread and mobile-single-page mode (page-flip's own
  //   destroy() removes the whole block element — there's no "reconfigure
  //   in place" — so any listener attached directly to a trigger wouldn't
  //   survive a rebuild).
  // - CAPTURE phase specifically (not the default bubble phase) matters:
  //   #book's own click-to-flip handler is a BUBBLE listener attached to
  //   an element BETWEEN the trigger and #stage, so on a normal bubble
  //   listener here, #book's handler would already have fired (and flipped
  //   the page) before this one ever saw the event. Capture runs root-down
  //   before any bubble listener does, so calling stopPropagation() here
  //   reliably pre-empts the flip.
  stage.addEventListener(
    'click',
    (e) => {
      const slug = triggerSlugFor(e.target);
      if (!slug) return;
      e.stopPropagation();
      openModal(slug);
    },
    { capture: true }
  );

  stage.addEventListener(
    'keydown',
    (e) => {
      const ke = e as KeyboardEvent;
      if (ke.key !== 'Enter' && ke.key !== ' ') return;
      const slug = triggerSlugFor(e.target);
      if (!slug) return;
      e.preventDefault();
      e.stopPropagation();
      openModal(slug);
    },
    { capture: true }
  );

  closeBtn?.addEventListener('click', closeModal);
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeModal();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && overlay!.classList.contains('open')) closeModal();
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
