import { PageFlip } from 'page-flip';
import config from '../config/flipbook.config';

function init(): void {
  const bookEl = document.getElementById('book');
  const stage = document.getElementById('stage');
  const loadingNote = document.getElementById('loading-note');
  if (!bookEl || !stage) return;

  const pageFlip = new PageFlip(bookEl, {
    width: config.book.pageWidth,
    height: config.book.pageHeight,
    size: config.book.size,
    minWidth: config.book.pageWidth,
    maxWidth: config.book.pageWidth,
    minHeight: config.book.pageHeight,
    maxHeight: config.book.pageHeight,
    showCover: config.book.showCover,
    startPage: Math.max(0, config.book.startPage - 1),
    flippingTime: config.book.flippingTime,
    maxShadowOpacity: config.book.maxShadowOpacity,
    drawShadow: config.book.drawShadow,
    useMouseEvents: config.book.useMouseEvents,
    usePortrait: config.book.usePortrait,
  });

  const pageEls = bookEl.querySelectorAll<HTMLElement>(':scope > .page');
  pageFlip.loadFromHTML(pageEls);
  loadingNote?.remove();

  // page-flip's "fixed" size mode always lays the book out at a full
  // spread width (2 * pageWidth) internally — even a lone cover page just
  // occupies the right half of that box. Rather than fight that, give
  // #book-shell that exact natural size and scale it down (never up, to
  // keep text/background crisp) to fit whatever room #stage actually has.
  const bookShell = document.getElementById('book-shell');
  const NATURAL_W = config.book.pageWidth * 2;
  const NATURAL_H = config.book.pageHeight;
  const STAGE_PADDING = 32;

  function fitBookToStage(): void {
    if (!bookShell || !stage) return;
    bookShell.style.width = `${NATURAL_W}px`;
    bookShell.style.height = `${NATURAL_H}px`;
    const availW = stage.clientWidth - STAGE_PADDING * 2;
    const availH = stage.clientHeight - STAGE_PADDING * 2;
    const scale = Math.min(availW / NATURAL_W, availH / NATURAL_H, 1);
    bookShell.style.transform = `scale(${Math.max(scale, 0.1)})`;
  }

  fitBookToStage();
  window.addEventListener('resize', fitBookToStage);
  document.addEventListener('fullscreenchange', () => setTimeout(fitBookToStage, 50));

  const total = pageFlip.getPageCount();

  // With useMouseEvents:false, page-flip attaches none of its own mouse
  // handling (no hover-curl preview, no drag-follow). Restore the minimum
  // expected interaction ourselves: click the left half of the book to go
  // back, the right half to go forward — a plain flip, nothing more.
  if (!config.book.useMouseEvents) {
    bookEl.addEventListener('click', (e) => {
      if ((window.getSelection()?.toString().length ?? 0) > 0) return; // don't hijack text selection
      const rect = bookEl.getBoundingClientRect();
      const fraction = (e.clientX - rect.left) / rect.width;
      if (fraction < 0.5) {
        pageFlip.flipPrev();
      } else {
        pageFlip.flipNext();
      }
    });
    bookEl.style.cursor = 'pointer';
  }

  const prevBtn = document.getElementById('btn-prev') as HTMLButtonElement | null;
  const nextBtn = document.getElementById('btn-next') as HTMLButtonElement | null;
  const indicator = document.getElementById('page-indicator');

  // Derive which 1-indexed source page(s) are on screen. With showCover
  // enabled, the first and last pages are shown alone; everything else is a
  // left/right spread starting at the current page index.
  function currentPagesDisplay(): number[] {
    const idx = pageFlip.getCurrentPageIndex(); // 0-based
    const orientation = pageFlip.getOrientation();
    const left = idx + 1;
    if (orientation !== 'landscape') return [left];
    if (left <= 1 || left >= total) return [left];
    const right = left + 1;
    return right <= total ? [left, right] : [left];
  }

  function refreshUI(): void {
    const shown = currentPagesDisplay();
    // Bug note: don't derive "last page" from getCurrentPageIndex() alone —
    // it's the LEFT page of the current spread, which only equals total-1
    // when the final spread happens to be a lone page (true for 10 pages,
    // false for e.g. 93: 92 pages after the cover is even, so the last
    // spread pairs up with no trailing single page). Deriving from the
    // same left/right range used for the indicator is correct either way.
    if (prevBtn) prevBtn.disabled = shown[0] <= 1;
    if (nextBtn) nextBtn.disabled = shown[shown.length - 1] >= total;
    if (indicator) indicator.textContent = config.labels.pageIndicator(shown, total);
  }

  pageFlip.on('flip', refreshUI);
  pageFlip.on('changeOrientation', refreshUI);
  refreshUI();

  prevBtn?.addEventListener('click', () => pageFlip.flipPrev());
  nextBtn?.addEventListener('click', () => pageFlip.flipNext());

  if (config.toolbar.showKeyboardNav) {
    window.addEventListener('keydown', (e) => {
      if (e.target instanceof HTMLInputElement) return;
      if (e.key === 'ArrowLeft') pageFlip.flipPrev();
      if (e.key === 'ArrowRight') pageFlip.flipNext();
    });
  }

  if (config.toolbar.showPageJump) {
    const form = document.getElementById('jump-form') as HTMLFormElement | null;
    const input = document.getElementById('jump-input') as HTMLInputElement | null;
    form?.addEventListener('submit', (e) => {
      e.preventDefault();
      const n = parseInt(input?.value ?? '', 10);
      if (!Number.isNaN(n) && n >= 1 && n <= total) {
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
        stage.requestFullscreen?.().catch(() => {});
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
        pageFlip.turnToPage(n - 1);
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
