import config from '../config/flipbook.config';

function init(): void {
  const stage = document.getElementById('stage');
  const lightbox = document.getElementById('photo-lightbox');
  const lightboxImg = document.getElementById('photo-lightbox-img') as HTMLImageElement | null;
  const closeBtn = document.getElementById('photo-lightbox-close');
  if (!stage || !lightbox || !lightboxImg) return;

  // Disabled on mobile: a lightbox competes with the exact same pinch-to-
  // zoom gesture mobile now relies on entirely to see a photo up close (see
  // app.css's mobile section) — the phone's own zoom already does this job.
  // Checked live (not just at init) since rotating/resizing can cross the
  // breakpoint without a page reload.
  const isMobile = () => window.matchMedia(`(max-width: ${config.responsive.mobileBreakpointPx}px)`).matches;

  // import.meta.env.BASE_URL reflects astro.config.mjs's `base` (this app
  // deploys under a /fcif25book subpath on GitHub Pages, not the domain
  // root) — same reasoning as index.astro's withBase(), just needed here
  // too since data-photo-src is a plain relative path baked into the
  // generated fragment HTML, not something Astro's own asset pipeline sees.
  const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');

  function closeLightbox(): void {
    lightbox!.classList.remove('open');
    lightbox!.setAttribute('aria-hidden', 'true');
    lightboxImg!.src = '';
  }

  function openLightbox(relSrc: string): void {
    lightboxImg!.src = `${BASE}/${relSrc.replace(/^\//, '')}`;
    lightbox!.classList.add('open');
    lightbox!.setAttribute('aria-hidden', 'false');
  }

  function photoSrcFor(target: EventTarget | null): string | null {
    if (!(target instanceof Element)) return null;
    const el = target.closest<HTMLElement>('[data-photo-src]');
    return el?.dataset.photoSrc ?? null;
  }

  // Event delegation on #stage (stable across rebuilds), not on the
  // .photo-zoom triggers themselves — they're children of #book, which
  // flipbook.client.ts destroys and recreates on every desktop/mobile
  // breakpoint crossing (page-flip's destroy() removes the whole block
  // element; there's no "reconfigure in place"), so a listener attached
  // directly to a trigger wouldn't survive a rebuild. Same reasoning as
  // readmore.client.ts.
  stage.addEventListener('click', (e) => {
    if (isMobile()) return;
    const src = photoSrcFor(e.target);
    if (!src) return;
    openLightbox(src);
  });

  stage.addEventListener('keydown', (e) => {
    if (isMobile()) return;
    const ke = e as KeyboardEvent;
    if (ke.key !== 'Enter' && ke.key !== ' ') return;
    const src = photoSrcFor(e.target);
    if (!src) return;
    e.preventDefault();
    openLightbox(src);
  });

  // Any click anywhere in the lightbox (backdrop, the photo itself, or the
  // close button) closes it — a zoomed photo has nothing else to click.
  closeBtn?.addEventListener('click', closeLightbox);
  lightbox.addEventListener('click', closeLightbox);

  // Any keystroke closes it too, not just Escape — and, critically, this
  // must run BEFORE flipbook.client.ts's own window-level keydown listener
  // (Arrow keys flip the page). Both are added in the same DOMContentLoaded
  // tick from separate <script> imports in index.astro; since flipbook's
  // listener runs first (that import comes first), CAPTURE phase on
  // document (which fires root-down, ahead of any bubble-phase listener on
  // window) is what actually guarantees this one closes the lightbox before
  // that one gets a chance to flip the page underneath.
  document.addEventListener(
    'keydown',
    (e) => {
      if (!lightbox!.classList.contains('open')) return;
      e.stopPropagation();
      closeLightbox();
    },
    { capture: true }
  );
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
