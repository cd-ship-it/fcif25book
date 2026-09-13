import { PageFlip } from 'page-flip';
import config from '../config/flipbook.config';
import { readMoreLinks } from '../config/readmore.config';

function init(): void {
  const bookShell = document.getElementById('book-shell');
  const stage = document.getElementById('stage');
  const app = document.getElementById('app');
  const loadingNote = document.getElementById('loading-note');
  const originalBookEl = document.getElementById('book');
  if (!bookShell || !stage || !app || !originalBookEl) return;

  // Freeze a pristine copy of the page markup before page-flip ever touches
  // it — loadFromHTML reparents/wraps the live nodes it's given, and
  // PageFlip.destroy() removes the whole block element outright (there's no
  // "reconfigure in place" API). Switching between desktop-spread and
  // mobile-single-page means fully tearing down and recreating the
  // instance, so we need our own clean copies to rebuild from each time.
  const templatePages = Array.from(
    originalBookEl.querySelectorAll<HTMLElement>(':scope > .page')
  ).map((el) => el.cloneNode(true) as HTMLElement);
  const total = templatePages.length;

  // Mark "閱讀全文" trigger elements once, on the template — every future
  // clone (i.e. every rebuild) then already carries the affordance styling
  // and a11y attributes with it, with no per-rebuild re-work needed.
  for (const link of readMoreLinks) {
    for (const page of templatePages) {
      const el = page.querySelector<HTMLElement>(`#${CSS.escape(link.elementId)}`);
      if (!el) continue;
      el.classList.add('readmore-trigger');
      el.setAttribute('role', 'button');
      el.setAttribute('tabindex', '0');
      el.setAttribute('aria-haspopup', 'dialog');
    }
  }

  const mq = window.matchMedia(`(max-width: ${config.responsive.mobileBreakpointPx}px)`);
  let pageFlip: PageFlip | null = null;
  let bookEl: HTMLElement | null = null;
  let mobileMode = false;

  // Resume-position persistence. Motivating bug: tapping a PDF hyperlink
  // opens it in a new tab (target="_blank"); closing that tab and coming
  // back can leave the browser having silently reloaded this (now
  // background-then-foreground) tab from scratch under memory pressure —
  // especially on mobile, and especially for a page this heavy (93
  // full-page background images + a live YouTube iframe). With no state
  // persisted anywhere, a reload always restarted at config.book.startPage.
  const RESUME_KEY = 'ficf25:lastPage';

  function saveCurrentPage(pageNum: number): void {
    try {
      localStorage.setItem(RESUME_KEY, String(pageNum));
    } catch {
      // Storage can throw (private browsing, disabled, quota) — resuming
      // position is a nice-to-have, never worth breaking the book over.
    }
  }

  function loadSavedPage(): number | null {
    try {
      const n = parseInt(localStorage.getItem(RESUME_KEY) ?? '', 10);
      return Number.isFinite(n) && n >= 1 && n <= total ? n : null;
    } catch {
      return null;
    }
  }

  // What page index should a (re)build open on? A rebuild triggered by a
  // mobile/desktop breakpoint crossing should stay on whatever page the
  // reader is ALREADY on (read the live instance), not jump back to the
  // configured/saved start page — that's a separate, equally real bug this
  // fixes as a side effect of sharing this logic with the reload case.
  function getResumePageIndex(): number {
    if (pageFlip) return pageFlip.getCurrentPageIndex();
    return Math.max(0, (loadSavedPage() ?? config.book.startPage) - 1);
  }

  const prevBtn = document.getElementById('btn-prev') as HTMLButtonElement | null;
  const nextBtn = document.getElementById('btn-next') as HTMLButtonElement | null;
  const indicator = document.getElementById('page-indicator');
  const prevBtnMobile = document.getElementById('btn-prev-mobile') as HTMLButtonElement | null;
  const nextBtnMobile = document.getElementById('btn-next-mobile') as HTMLButtonElement | null;
  const indicatorMobile = document.getElementById('page-indicator-mobile');

  // Derive which 1-indexed source page(s) are on screen. With showCover
  // enabled, the first and last pages are shown alone; everything else is a
  // left/right spread starting at the current page index. In single-page
  // (portrait) mode there's only ever one page shown.
  function currentPagesDisplay(): number[] {
    if (!pageFlip) return [1];
    const idx = pageFlip.getCurrentPageIndex();
    const orientation = pageFlip.getOrientation();
    const left = idx + 1;
    if (orientation !== 'landscape') return [left];
    if (left <= 1 || left >= total) return [left];
    const right = left + 1;
    return right <= total ? [left, right] : [left];
  }

  function refreshUI(): void {
    if (!pageFlip) return;
    const shown = currentPagesDisplay();
    // Don't derive "last page" from getCurrentPageIndex() alone — see the
    // README for why (it's only ever the LEFT page of the spread).
    const atStart = shown[0] <= 1;
    const atEnd = shown[shown.length - 1] >= total;
    const text = config.labels.pageIndicator(shown, total);
    if (prevBtn) prevBtn.disabled = atStart;
    if (nextBtn) nextBtn.disabled = atEnd;
    if (indicator) indicator.textContent = text;
    if (prevBtnMobile) prevBtnMobile.disabled = atStart;
    if (nextBtnMobile) nextBtnMobile.disabled = atEnd;
    if (indicatorMobile) indicatorMobile.textContent = text;
    saveCurrentPage(shown[0]);
  }

  // Desktop: scale the whole two-page spread (never upscaled) to fit
  // entirely within #stage — no scrolling, the whole spread is always
  // visible at once.
  function fitDesktop(): void {
    if (!bookEl) return;
    const NATURAL_W = config.book.pageWidth * 2;
    const NATURAL_H = config.book.pageHeight;
    const PADDING = 32;
    bookShell!.style.width = `${NATURAL_W}px`;
    bookShell!.style.height = `${NATURAL_H}px`;
    const availW = stage!.clientWidth - PADDING * 2;
    const availH = stage!.clientHeight - PADDING * 2;
    const scale = Math.min(availW / NATURAL_W, availH / NATURAL_H, 1);
    bookShell!.style.transformOrigin = 'center center';
    bookShell!.style.transform = `scale(${Math.max(scale, 0.1)})`;
  }

  // Mobile: scale a single page to fit the viewport WIDTH only (never
  // upscaled). The resulting height often exceeds the visible stage area —
  // that's expected; #stage scrolls vertically in mobile mode (see
  // #app.mobile-mode #stage in app.css) rather than shrinking text to
  // illegibility just to avoid a scrollbar.
  function fitMobile(): void {
    if (!bookEl) return;
    const NATURAL_W = config.book.pageWidth;
    const NATURAL_H = config.book.pageHeight;
    const SIDE_PADDING = 8;
    bookShell!.style.width = `${NATURAL_W}px`;
    bookShell!.style.height = `${NATURAL_H}px`;
    const availW = stage!.clientWidth - SIDE_PADDING * 2;
    const scale = Math.min(availW / NATURAL_W, 1);
    // top center (not the desktop center-center): so shrinking sits the
    // page flush at the top of the scrollable area, not visually inset.
    bookShell!.style.transformOrigin = 'top center';
    bookShell!.style.transform = `scale(${Math.max(scale, 0.1)})`;
  }

  function applyFit(): void {
    if (mobileMode) fitMobile();
    else fitDesktop();
  }

  function attachBookClickToFlip(): void {
    if (!bookEl || config.book.useMouseEvents) return;
    // With useMouseEvents:false, page-flip attaches none of its own mouse
    // handling (no hover-curl preview, no drag-follow). Restore the minimum
    // expected interaction ourselves: click the left half of the book to go
    // back, the right half to go forward — a plain flip, nothing more. This
    // is re-attached on every rebuild since #book is a fresh element each time.
    bookEl.addEventListener('click', (e) => {
      if ((window.getSelection()?.toString().length ?? 0) > 0) return; // don't hijack text selection
      const rect = bookEl!.getBoundingClientRect();
      const fraction = (e.clientX - rect.left) / rect.width;
      if (fraction < 0.5) pageFlip?.flipPrev();
      else pageFlip?.flipNext();
    });
    bookEl.style.cursor = 'pointer';
  }

  function buildBook(mobile: boolean): void {
    mobileMode = mobile;
    app!.classList.toggle('mobile-mode', mobile);

    // Must read BEFORE tearing down the old pageFlip instance below — this
    // is how a rebuild resumes the reader's current page.
    const resumeIndex = getResumePageIndex();

    if (pageFlip) {
      pageFlip.destroy(); // also removes the old #book element from the DOM
      pageFlip = null;
    } else {
      // First call: pageFlip.destroy() hasn't run yet to clear out the
      // original server-rendered #book (the one templatePages was cloned
      // from) — remove it ourselves, or we'd end up with two #book elements
      // and duplicate ids, with getElementById silently resolving to the
      // stale original instead of the live clone.
      document.getElementById('book')?.remove();
    }

    bookEl = document.createElement('div');
    bookEl.id = 'book';
    for (const p of templatePages) bookEl.appendChild(p.cloneNode(true));
    bookShell!.appendChild(bookEl);

    const shared = {
      showCover: config.book.showCover,
      startPage: resumeIndex,
      flippingTime: config.book.flippingTime,
      maxShadowOpacity: config.book.maxShadowOpacity,
      drawShadow: config.book.drawShadow,
      useMouseEvents: config.book.useMouseEvents,
      width: config.book.pageWidth,
      height: config.book.pageHeight,
      size: config.book.size,
      minWidth: config.book.pageWidth,
      maxWidth: config.book.pageWidth,
      minHeight: config.book.pageHeight,
      maxHeight: config.book.pageHeight,
    };

    pageFlip = new PageFlip(bookEl, { ...shared, usePortrait: mobile });

    const pageEls = bookEl.querySelectorAll<HTMLElement>(':scope > .page');
    pageFlip.loadFromHTML(pageEls);
    loadingNote?.remove();

    attachBookClickToFlip();
    pageFlip.on('flip', refreshUI);
    pageFlip.on('changeOrientation', refreshUI);
    refreshUI();
    applyFit();
  }

  buildBook(mq.matches);

  window.addEventListener('resize', () => {
    if (mq.matches !== mobileMode) buildBook(mq.matches);
    else applyFit();
  });
  // Some browsers fire this distinctly from (and before) `resize` on rotation.
  window.addEventListener('orientationchange', () => {
    setTimeout(() => {
      if (mq.matches !== mobileMode) buildBook(mq.matches);
      else applyFit();
    }, 100);
  });
  document.addEventListener('fullscreenchange', () => setTimeout(applyFit, 50));

  // --- Controls below are static (rendered once by index.astro) and call
  // through the `pageFlip` closure variable, which buildBook keeps pointed
  // at whichever instance is currently live. ---

  prevBtn?.addEventListener('click', () => pageFlip?.flipPrev());
  nextBtn?.addEventListener('click', () => pageFlip?.flipNext());
  prevBtnMobile?.addEventListener('click', () => pageFlip?.flipPrev());
  nextBtnMobile?.addEventListener('click', () => pageFlip?.flipNext());

  if (config.toolbar.showKeyboardNav) {
    window.addEventListener('keydown', (e) => {
      if (e.target instanceof HTMLInputElement) return;
      if (e.key === 'ArrowLeft') pageFlip?.flipPrev();
      if (e.key === 'ArrowRight') pageFlip?.flipNext();
    });
  }

  if (config.toolbar.showPageJump) {
    const form = document.getElementById('jump-form') as HTMLFormElement | null;
    const input = document.getElementById('jump-input') as HTMLInputElement | null;
    form?.addEventListener('submit', (e) => {
      e.preventDefault();
      const n = parseInt(input?.value ?? '', 10);
      if (pageFlip && !Number.isNaN(n) && n >= 1 && n <= total) {
        // turnToPage (not flip) — flip()/flipToPage() only steps one spread
        // at a time regardless of distance, so it's wrong for arbitrary jumps.
        pageFlip.turnToPage(n - 1);
      }
      if (input) input.value = '';
      input?.blur();
    });
  }

  if (config.toolbar.showFullscreen) {
    const fsBtn = document.getElementById('btn-fullscreen');
    fsBtn?.addEventListener('click', () => {
      if (!document.fullscreenElement) {
        stage!.requestFullscreen?.().catch(() => {});
      } else {
        document.exitFullscreen?.().catch(() => {});
      }
    });
    document.addEventListener('fullscreenchange', () => {
      if (fsBtn) {
        fsBtn.textContent = document.fullscreenElement
          ? config.labels.fullscreenExit
          : config.labels.fullscreenEnter;
      }
    });
  }

  if (config.toolbar.showThumbnails) {
    const tocBtn = document.getElementById('btn-toc');
    const drawer = document.getElementById('toc-drawer');
    const backdrop = document.getElementById('toc-backdrop');

    const closeToc = () => {
      drawer?.classList.remove('open');
      backdrop?.classList.remove('open');
    };

    tocBtn?.addEventListener('click', () => {
      drawer?.classList.toggle('open');
      backdrop?.classList.toggle('open');
    });
    backdrop?.addEventListener('click', closeToc);

    drawer?.querySelectorAll<HTMLElement>('[data-goto]').forEach((el) => {
      el.addEventListener('click', () => {
        const n = parseInt(el.dataset.goto ?? '1', 10);
        pageFlip?.turnToPage(n - 1);
        closeToc();
      });
    });
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
