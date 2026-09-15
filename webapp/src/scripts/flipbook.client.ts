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

  // Checks height as well as width — a phone in landscape is wide but
  // short, and without the height half of this it would cross into
  // desktop's two-page page-flip layout just from rotating, then lose
  // mobile's plain-scroll page entirely. The height clause is gated on
  // (pointer: coarse) so it only fires for an actual touch device — a
  // short-but-wide DESKTOP browser window (very common on laptops once
  // browser chrome eats into the viewport) has a real mouse and must NOT
  // match, or desktop users see the mobile layout on a plenty-wide window
  // (a real regression this shipped and had to be walked back). Must stay
  // in sync with app.css's own matching media queries (search
  // mobileBreakpointPx there).
  const bp = config.responsive.mobileBreakpointPx;
  const mq = window.matchMedia(`(max-width: ${bp}px), ((max-height: ${bp}px) and (pointer: coarse))`);
  let pageFlip: PageFlip | null = null;
  let bookEl: HTMLElement | null = null;
  let mobileMode = false;

  // Mobile has no page-flip instance at all (see buildMobileBook) — just one
  // plain page in normal document flow at a time, tracked here.
  let mobilePageEl: HTMLElement | null = null;
  let mobileCurrentPage = 1; // 1-indexed

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

  // What page index (0-indexed, matching PageFlip's own convention) should a
  // (re)build open on? A rebuild triggered by a mobile/desktop breakpoint
  // crossing should stay on whatever page the reader is ALREADY on (read the
  // live instance), not jump back to the configured/saved start page — that's
  // a separate, equally real bug this fixes as a side effect of sharing this
  // logic with the reload case.
  function getResumePageIndex(): number {
    if (pageFlip) return pageFlip.getCurrentPageIndex();
    // mobilePageEl (not mobileMode!) — buildBook() sets mobileMode = mobile
    // BEFORE calling this, so on the very first load in mobile mode,
    // mobileMode is already true while mobilePageEl is still null (nothing
    // built yet). Checking mobileMode there made this always return
    // mobileCurrentPage - 1 = 0, ignoring the saved page on first load
    // entirely. mobilePageEl being non-null means an actual mobile session
    // is already running (a same-mode resize, not the initial build), which
    // is the only time its live current page should win over localStorage.
    if (mobilePageEl) return mobileCurrentPage - 1;
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
  // left/right spread starting at the current page index. Mobile always
  // shows exactly one page (mobileCurrentPage) — there's no spread concept
  // at all now that it's not page-flip managed.
  function currentPagesDisplay(): number[] {
    if (mobileMode) return [mobileCurrentPage];
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
    const PADDING_X = 32;
    // The book's spread aspect ratio (~1.54:1) is narrower than most desktop
    // window shapes, so height is almost always the binding constraint —
    // cut the top/bottom padding by 70% (32px -> ~10px) to let the book
    // render as large as possible; horizontal padding is untouched since
    // there's usually slack there already.
    const PADDING_Y = 32 * 0.3;
    bookShell!.style.width = `${NATURAL_W}px`;
    bookShell!.style.height = `${NATURAL_H}px`;
    const availW = stage!.clientWidth - PADDING_X * 2;
    const availH = stage!.clientHeight - PADDING_Y * 2;
    const scale = Math.min(availW / NATURAL_W, availH / NATURAL_H, 1);
    bookShell!.style.transformOrigin = 'center center';
    bookShell!.style.transform = `scale(${Math.max(scale, 0.1)})`;
  }

  // Mobile: scale a single page to fit the viewport WIDTH only (never
  // upscaled). The resulting height often exceeds the visible stage area —
  // that's expected; #stage scrolls vertically in mobile mode (see
  // #app.mobile-mode #stage in app.css) rather than shrinking text to
  // illegibility just to avoid a scrollbar. This is plain CSS scaling of a
  // page sitting in normal document flow — no page-flip instance, no touch
  // handlers of its own, so it never competes with the browser's native
  // pinch-to-zoom/pan the way a JS-driven page-turn library's own gesture
  // handling would.
  function fitMobile(): void {
    if (!mobilePageEl) return;
    const NATURAL_W = config.book.pageWidth;
    const NATURAL_H = config.book.pageHeight;
    bookShell!.style.width = `${NATURAL_W}px`;
    bookShell!.style.height = `${NATURAL_H}px`;
    const scale = Math.min(stage!.clientWidth / NATURAL_W, 1);
    // top center (not the desktop center-center): so shrinking sits the
    // page flush at the top of the scrollable area, not visually inset.
    bookShell!.style.transformOrigin = 'top center';
    bookShell!.style.transform = `scale(${Math.max(scale, 0.1)})`;
  }

  function applyFit(): void {
    if (mobileMode) fitMobile();
    else fitDesktop();
  }

  // Unified prev/next/jump — desktop drives page-flip, mobile just swaps
  // which single cloned page is shown. Every static control (dock buttons,
  // toolbar buttons, keyboard, TOC drawer, page-jump form) goes through
  // these three instead of reaching for `pageFlip` directly, so none of them
  // need their own mobile/desktop branch.
  function goToPage(n: number): void {
    if (mobileMode) {
      mobileCurrentPage = Math.max(1, Math.min(total, n));
      renderMobilePage();
    } else {
      // turnToPage (not flip) — flip()/flipToPage() only steps one spread at
      // a time regardless of distance, so it's wrong for arbitrary jumps.
      pageFlip?.turnToPage(n - 1);
    }
  }

  function flipPrev(): void {
    if (mobileMode) goToPage(mobileCurrentPage - 1);
    else pageFlip?.flipPrev();
  }

  function flipNext(): void {
    if (mobileMode) goToPage(mobileCurrentPage + 1);
    else pageFlip?.flipNext();
  }

  // Page 5's table-of-contents entries (generate.py's TOC_TARGETS) are real
  // anchors carrying BOTH an href and data-goto: the href is what makes the
  // standalone pageN.html previews navigate, but following it here would
  // leave the app entirely, so it's pre-empted and routed through goToPage.
  //
  // Delegated on #stage in the CAPTURE phase, same two reasons as
  // readmore.client.ts: #stage survives the #book teardown/rebuild that a
  // desktop/mobile breakpoint crossing triggers, and capture runs before
  // #book's own bubble-phase click-to-flip handler, so stopPropagation here
  // actually prevents a stray page turn.
  stage!.addEventListener(
    'click',
    (e) => {
      const el = (e.target as Element | null)?.closest?.<HTMLElement>('[data-goto]');
      if (!el) return;
      const n = parseInt(el.dataset.goto ?? '', 10);
      if (Number.isNaN(n)) return;
      e.preventDefault();
      e.stopPropagation();
      goToPage(n);
    },
    { capture: true }
  );

  // With useMouseEvents:false, page-flip attaches none of its own mouse
  // handling (no hover-curl preview, no drag-follow) — restore click-to-flip
  // ourselves. This used to be one click handler on the whole #book element
  // (left half = prev, right half = next), but that meant ANY click
  // anywhere in the page — including a PDF hyperlink overlay, which (unlike
  // the "閱讀全文" trigger) has no stopPropagation of its own — also bubbled
  // up and flipped the page underneath it. Reported on page 45: opening an
  // external link, then closing that tab, came back to the WRONG page,
  // because the flip had already silently happened at click time.
  //
  // Fix: two narrow (5% width) hit zones fixed to the left/right edges of
  // #book-shell, rather than a click listener on #book itself. They're
  // created once (not per-rebuild) as the first children of #book-shell, so
  // #book — appended after them on every buildBook() call — always paints
  // on top and wins hit-testing wherever real content overlaps the edges.
  // The remaining 90% in the middle has no click-to-flip listener on it at
  // all, so links/buttons there are never at risk of a flip firing under
  // them, regardless of whether they call stopPropagation.
  //
  // Desktop only (hidden in mobile mode via CSS) — mobile navigates only
  // through the bottom dock's arrow buttons, deliberately, so there's no tap
  // target anywhere on the page itself to conflict with double-tap-to-zoom.
  function createTurnZone(side: 'prev' | 'next'): void {
    const zone = document.createElement('div');
    zone.className = `turn-zone turn-zone-${side}`;
    zone.setAttribute('aria-hidden', 'true');
    zone.addEventListener('click', () => {
      if ((window.getSelection()?.toString().length ?? 0) > 0) return; // don't hijack text selection
      if (side === 'prev') flipPrev();
      else flipNext();
    });
    bookShell!.appendChild(zone);
  }
  if (!config.book.useMouseEvents) {
    createTurnZone('prev');
    createTurnZone('next');
  }

  // Removes whatever the OTHER mode left behind in #book-shell, so buildBook
  // always starts from a clean slate regardless of which mode ran last.
  function teardownDesktop(): void {
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
  }

  function teardownMobile(): void {
    mobilePageEl?.remove();
    mobilePageEl = null;
  }

  function renderMobilePage(): void {
    mobilePageEl?.remove();
    mobilePageEl = templatePages[mobileCurrentPage - 1].cloneNode(true) as HTMLElement;
    bookShell!.appendChild(mobilePageEl);
    fitMobile();
    refreshUI();
  }

  function buildDesktopBook(resumeIndex: number): void {
    teardownDesktop();
    teardownMobile();

    bookEl = document.createElement('div');
    bookEl.id = 'book';
    for (const p of templatePages) bookEl.appendChild(p.cloneNode(true));
    bookShell!.appendChild(bookEl);

    pageFlip = new PageFlip(bookEl, {
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
      usePortrait: false,
    });

    const pageEls = bookEl.querySelectorAll<HTMLElement>(':scope > .page');
    pageFlip.loadFromHTML(pageEls);
    loadingNote?.remove();

    pageFlip.on('flip', () => {
      refreshUI();
      stopStrayYoutubeEmbeds();
    });
    pageFlip.on('changeOrientation', refreshUI);
    refreshUI();
    applyFit();
  }

  // Page 63's YouTube trigger (see yt-embed.client.ts) swaps to a live,
  // autoplaying <iframe> on click. Desktop's page-flip instance keeps every
  // page's DOM node alive across flips (it's not destroyed/recreated per
  // flip the way mobile's single page is — see renderMobilePage, where
  // navigating away removes the old page, and removing an iframe from the
  // DOM is what actually stops it), so without this, flipping away from
  // page 63 would leave the video silently playing off-screen. Called after
  // every 'flip' event: find any live .yt-embed iframe still in the book,
  // and if the page it's on isn't part of the current view, revert it back
  // to its pristine (never-clicked) trigger div — cloned fresh from
  // templatePages, so a later return to that page starts clean, not with a
  // stale/blank iframe. Mobile needs no equivalent: its page (and any live
  // iframe on it) is fully removed from the DOM on every navigation already.
  function stopStrayYoutubeEmbeds(): void {
    if (!bookEl) return;
    const iframe = bookEl.querySelector<HTMLIFrameElement>('iframe.yt-embed');
    if (!iframe) return;
    const pageEl = iframe.closest<HTMLElement>('.page');
    const pageNum = pageEl ? parseInt(pageEl.id.replace('page', ''), 10) : NaN;
    if (Number.isFinite(pageNum) && currentPagesDisplay().includes(pageNum)) return;
    const pristineTrigger =
      pageNum >= 1 && pageNum <= total
        ? templatePages[pageNum - 1].querySelector<HTMLElement>(`#${CSS.escape(iframe.id)}`)
        : null;
    if (pristineTrigger) iframe.replaceWith(pristineTrigger.cloneNode(true) as HTMLElement);
    else iframe.remove(); // no matching template found — still stop playback
  }

  function buildMobileBook(resumeIndex: number): void {
    teardownDesktop();
    teardownMobile();
    mobileCurrentPage = Math.max(1, Math.min(total, resumeIndex + 1));
    renderMobilePage();
    loadingNote?.remove();
  }

  function buildBook(mobile: boolean): void {
    mobileMode = mobile;
    app!.classList.toggle('mobile-mode', mobile);

    // Must read BEFORE tearing down the old instance below — this is how a
    // rebuild resumes the reader's current page.
    const resumeIndex = getResumePageIndex();

    if (mobile) buildMobileBook(resumeIndex);
    else buildDesktopBook(resumeIndex);
  }

  buildBook(mq.matches);

  // iOS Safari's native pinch-to-zoom (the viewport meta tag deliberately
  // doesn't disable it — see index.astro) can trigger a `resize` here
  // mid-gesture on some iOS versions, even though nothing about the actual
  // page/window size really changed — window.innerWidth/stage.clientWidth
  // stay the LAYOUT size, but re-running fitMobile()'s scale-to-fit math
  // while the visual viewport is transiently zoomed would produce a wrong
  // transform. window.visualViewport.scale reliably reports "actively
  // pinch-zoomed" (!= 1) vs. a real resize/rotation (== 1), so this skips
  // re-fitting for the former and lets it settle once the pinch ends. A
  // staged real-device test confirmed this whole combination (native
  // pinch-zoom + this guard + a position:fixed #bottom-nav) is stable —
  // an earlier theory blamed a *different*, unconfirmed mechanism for a
  // reported touch-shift bug; see app.css's html/body comment for what
  // that testing actually ruled in and out.
  function isPinchZoomed(): boolean {
    return !!window.visualViewport && window.visualViewport.scale !== 1;
  }

  window.addEventListener('resize', () => {
    if (isPinchZoomed()) return;
    if (mq.matches !== mobileMode) buildBook(mq.matches);
    else applyFit();
  });
  // Some browsers fire this distinctly from (and before) `resize` on rotation.
  window.addEventListener('orientationchange', () => {
    setTimeout(() => {
      if (isPinchZoomed()) return;
      if (mq.matches !== mobileMode) buildBook(mq.matches);
      else applyFit();
    }, 100);
  });
  // Once the user finishes pinch-zooming (scale returns to 1), re-apply the
  // fit in case a resize was skipped above while they were mid-gesture.
  window.visualViewport?.addEventListener('resize', () => {
    if (!isPinchZoomed()) applyFit();
  });
  document.addEventListener('fullscreenchange', () => setTimeout(applyFit, 50));

  // --- Controls below are static (rendered once by index.astro) and call
  // through goToPage/flipPrev/flipNext, which stay correct across rebuilds
  // and across the desktop/mobile split. ---

  prevBtn?.addEventListener('click', flipPrev);
  nextBtn?.addEventListener('click', flipNext);
  prevBtnMobile?.addEventListener('click', flipPrev);
  nextBtnMobile?.addEventListener('click', flipNext);

  if (config.toolbar.showKeyboardNav) {
    window.addEventListener('keydown', (e) => {
      if (e.target instanceof HTMLInputElement) return;
      // The photo lightbox (photo-zoom.client.ts) closes on ANY keystroke —
      // don't also let arrow keys flip the page underneath it while it's open.
      if (document.getElementById('photo-lightbox')?.classList.contains('open')) return;
      if (e.key === 'ArrowLeft') flipPrev();
      if (e.key === 'ArrowRight') flipNext();
    });
  }

  if (config.toolbar.showPageJump) {
    const form = document.getElementById('jump-form') as HTMLFormElement | null;
    const input = document.getElementById('jump-input') as HTMLInputElement | null;
    form?.addEventListener('submit', (e) => {
      e.preventDefault();
      const n = parseInt(input?.value ?? '', 10);
      if (!Number.isNaN(n) && n >= 1 && n <= total) goToPage(n);
      if (input) input.value = '';
      input?.blur();
    });
  }

  if (config.toolbar.hideOnDesktopUntilToggled) {
    const toggleBtn = document.getElementById('btn-toolbar-toggle');
    toggleBtn?.addEventListener('click', () => {
      const open = app!.classList.toggle('toolbar-open');
      toggleBtn.setAttribute('aria-expanded', String(open));
      // "⋮" invites opening the toolbar; once it's open, the same button
      // closes it again, so it becomes a big "✕" instead — same icon
      // language as the read-more/photo-lightbox close buttons elsewhere.
      toggleBtn.textContent = open ? '✕' : '⋮';
      // Toolbar showing/hiding changes #stage's available height (it's the
      // flex sibling that grows to fill whatever the toolbar doesn't take),
      // so the book needs to be rescaled to the new space — same as any
      // other resize, just not one the browser fires a `resize` event for.
      applyFit();
    });
  }

  if (config.toolbar.showFullscreen) {
    const fsBtn = document.getElementById('btn-fullscreen');
    fsBtn?.addEventListener('click', () => {
      if (!document.fullscreenElement) {
        // The whole document, not just #stage: the Fullscreen API only
        // keeps the fullscreened element's OWN descendants rendered/
        // interactive — every overlay this app opens on top of the book
        // (#detail-overlay, #photo-lightbox, and the
        // dynamically-created #tooltip) is a sibling of #stage, not a
        // descendant of it, so fullscreening #stage alone silently broke
        // all of them (in every browser — this is spec behavior, not a
        // browser bug) the instant fullscreen was entered.
        document.documentElement.requestFullscreen?.().catch(() => {});
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

  if (config.toolbar.showTocButton) {
    const tocBtn = document.getElementById('btn-toc');
    const tocBtnMobile = document.getElementById('btn-toc-mobile');
    tocBtn?.addEventListener('click', () => {
      goToPage(config.toolbar.tocJumpPage);
    });
    tocBtnMobile?.addEventListener('click', () => {
      goToPage(config.toolbar.tocJumpPage);
    });
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
