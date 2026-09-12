// ---------------------------------------------------------------------------
// Flipbook configuration.
//
// Edit this file, then rebuild (`npm run build`) or restart the dev server
// (`npm run dev`) to see changes — values here drive both the build-time
// toolbar markup (src/pages/index.astro) and the client-side page-flip
// behaviour (src/scripts/flipbook.client.ts), so there is a single source
// of truth for "what the reader sees and can do".
// ---------------------------------------------------------------------------

export interface FlipbookConfig {
  book: {
    /** Width of a single leaf (page) in px. Matches the generated 695x900 assets. */
    pageWidth: number;
    /** Height of a single leaf (page) in px. */
    pageHeight: number;
    /** Render page 1 (and the last page, if the total is even) as a lone cover, not part of a spread. */
    showCover: boolean;
    /** 'fixed' = never rescale pages; 'stretch' = fill the container. Keep 'fixed' for pixel-accurate backgrounds. */
    size: 'fixed' | 'stretch';
    /** 1-indexed page to open on. */
    startPage: number;
    /** Flip animation duration in ms. */
    flippingTime: number;
    /** Corner-drag shadow intensity, 0-1. */
    maxShadowOpacity: number;
    drawShadow: boolean;
    /**
     * true = page-flip's native mouse/touch interaction: hover-to-curl the
     * corner, drag-to-fold, click-to-flip.
     * false (default) = none of that — clicking anywhere on the book just
     * triggers a plain animated flip (left half = prev, right half = next),
     * with no hover-curl preview and no drag-follow. Wired up in
     * flipbook.client.ts's own click handler, independent of this library flag.
     */
    useMouseEvents: boolean;
    /** If true, page-flip may collapse to a single-page portrait layout on narrow viewports. Set false to always force the two-page spread. */
    usePortrait: boolean;
  };

  toolbar: {
    /** Slide-out drawer with page thumbnails for jumping to any spread. */
    showThumbnails: boolean;
    /** Fullscreen toggle button (uses the Fullscreen API on the book container). */
    showFullscreen: boolean;
    /** "Jump to page number" input + button. */
    showPageJump: boolean;
    /** Left/Right arrow key navigation. */
    showKeyboardNav: boolean;
    /** Reserved: play a page-turn sound effect. Requires `sound.flipSoundUrl`. */
    showSound: boolean;
  };

  labels: {
    tocTitle: string;
    tocButton: string;
    prev: string;
    next: string;
    fullscreenEnter: string;
    fullscreenExit: string;
    soundOn: string;
    soundOff: string;
    jumpPlaceholder: string;
    jumpButton: string;
    loading: string;
    /** current = [leftPage, rightPage] for a spread, or a single number for a cover page. */
    pageIndicator: (current: number[] | number, total: number) => string;
  };

  palette: {
    /** Brand purple, sampled from the book's cover typography. */
    primary: string;
    primaryDark: string;
    accentGold: string;
    accentGreen: string;
    /** Room/backdrop behind the book. */
    background: string;
    backgroundGradient: string;
    toolbarBg: string;
    toolbarText: string;
    toolbarBorder: string;
    pageShadow: string;
  };

  sound: {
    enabled: boolean;
    flipSoundUrl?: string;
  };
}

const config: FlipbookConfig = {
  book: {
    pageWidth: 695,
    pageHeight: 900,
    showCover: true,
    size: 'fixed',
    startPage: 1,
    flippingTime: 700,
    maxShadowOpacity: 0.5,
    drawShadow: true,
    useMouseEvents: false,
    usePortrait: false,
  },

  toolbar: {
    showThumbnails: true,
    showFullscreen: true,
    showPageJump: true,
    showKeyboardNav: true,
    showSound: false,
  },

  labels: {
    tocTitle: '目錄',
    tocButton: '目錄',
    prev: '上一頁',
    next: '下一頁',
    fullscreenEnter: '全螢幕',
    fullscreenExit: '離開全螢幕',
    soundOn: '開啟音效',
    soundOff: '關閉音效',
    jumpPlaceholder: '頁碼',
    jumpButton: '跳至',
    loading: '書本載入中…',
    pageIndicator: (current, total) => {
      if (Array.isArray(current)) {
        const [a, b] = current;
        if (b) return `第 ${a}–${b} 頁 ／ 共 ${total} 頁`;
        return `第 ${a} 頁 ／ 共 ${total} 頁`;
      }
      return `第 ${current} 頁 ／ 共 ${total} 頁`;
    },
  },

  palette: {
    primary: '#624393',
    primaryDark: '#453168',
    accentGold: '#c9a227',
    accentGreen: '#8fbfa0',
    background: '#26232b',
    backgroundGradient: 'radial-gradient(ellipse at 50% 30%, #37323d 0%, #201d24 70%)',
    toolbarBg: 'rgba(24, 21, 28, 0.92)',
    toolbarText: '#f3ede0',
    toolbarBorder: 'rgba(201, 162, 39, 0.35)',
    pageShadow: '0 20px 60px rgba(0,0,0,0.55)',
  },

  sound: {
    enabled: false,
    flipSoundUrl: undefined,
  },
};

export default config;
