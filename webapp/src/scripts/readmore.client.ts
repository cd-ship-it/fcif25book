import { readMoreLinks } from '../config/readmore.config';

function init(): void {
  const overlay = document.getElementById('detail-overlay');
  const closeBtn = document.getElementById('detail-close');
  if (!overlay) return; // no detail panels were rendered (no matching .md files)

  const panels = overlay.querySelectorAll<HTMLElement>('[data-detail-panel]');

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

  readMoreLinks.forEach((link) => {
    const trigger = document.getElementById(link.elementId);
    if (!trigger) return; // page not present in this build (e.g. only pages 1-10 synced so far)

    trigger.classList.add('readmore-trigger');
    trigger.setAttribute('role', 'button');
    trigger.setAttribute('tabindex', '0');
    trigger.setAttribute('aria-haspopup', 'dialog');

    const activate = (e: Event): void => {
      // Critical: the book itself has a click-to-flip handler (see
      // flipbook.client.ts). Without stopping propagation here, clicking
      // this button would also flip the page underneath the modal.
      e.stopPropagation();
      openModal(link.detailsFile);
    };

    trigger.addEventListener('click', activate);
    trigger.addEventListener('keydown', (e) => {
      const ke = e as KeyboardEvent;
      if (ke.key === 'Enter' || ke.key === ' ') {
        e.preventDefault();
        activate(e);
      }
    });
  });

  closeBtn?.addEventListener('click', closeModal);
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeModal();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && overlay.classList.contains('open')) closeModal();
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
