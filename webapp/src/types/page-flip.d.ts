// Minimal ambient typings for the `page-flip` package, which ships no
// .d.ts files. Covers only the surface this app actually calls.
declare module 'page-flip' {
  export interface WidgetEvent {
    data: unknown;
    object: PageFlip;
  }

  export interface PageFlipSettings {
    width: number;
    height: number;
    size?: 'fixed' | 'stretch';
    minWidth?: number;
    maxWidth?: number;
    minHeight?: number;
    maxHeight?: number;
    showCover?: boolean;
    startPage?: number;
    flippingTime?: number;
    maxShadowOpacity?: number;
    drawShadow?: boolean;
    useMouseEvents?: boolean;
    usePortrait?: boolean;
    autoSize?: boolean;
    mobileScrollSupport?: boolean;
    showPageCorners?: boolean;
    disableFlipByClick?: boolean;
    swipeDistance?: number;
    clickEventForward?: boolean;
  }

  export class PageFlip {
    constructor(element: HTMLElement, settings: Partial<PageFlipSettings>);
    loadFromHTML(items: NodeListOf<HTMLElement> | HTMLElement[]): void;
    updateFromHtml(items: NodeListOf<HTMLElement> | HTMLElement[]): void;
    destroy(): void;
    flipNext(corner?: 'top' | 'bottom'): void;
    flipPrev(corner?: 'top' | 'bottom'): void;
    flip(page: number, corner?: 'top' | 'bottom'): void;
    turnToPage(page: number): void;
    turnToNextPage(): void;
    turnToPrevPage(): void;
    getPageCount(): number;
    getCurrentPageIndex(): number;
    getOrientation(): 'portrait' | 'landscape';
    on(eventName: string, callback: (e: WidgetEvent) => void): PageFlip;
    off(eventName: string): void;
  }
}
