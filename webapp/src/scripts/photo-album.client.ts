function init(): void {
  const stage = document.getElementById('stage');
  if (!stage) return;

  function albumFor(target: EventTarget | null): HTMLElement | null {
    if (!(target instanceof Element)) return null;
    return target.closest<HTMLElement>('.photo-album');
  }

  function currentIndex(imgs: HTMLImageElement[]): number {
    const i = imgs.findIndex((img) => !img.hidden);
    return i === -1 ? 0 : i;
  }

  function step(album: HTMLElement, delta: number): void {
    const imgs = Array.from(album.querySelectorAll<HTMLImageElement>('.photo-album-img'));
    if (imgs.length === 0) return;
    const next = ((currentIndex(imgs) + delta) % imgs.length + imgs.length) % imgs.length;
    imgs.forEach((img, i) => {
      img.hidden = i !== next;
    });
    const caption = album.querySelector<HTMLElement>('.photo-album-caption');
    if (caption) caption.textContent = imgs[next].dataset.caption ?? '';
  }

  // Event delegation on #stage (stable across rebuilds), in the CAPTURE
  // phase — same reasoning as readmore.client.ts/photo-zoom.client.ts: the
  // .photo-album div is a child of #book, which flipbook.client.ts destroys
  // and recreates on every desktop/mobile breakpoint crossing, so a
  // listener attached directly to the buttons wouldn't survive a rebuild.
  // Capture + stopPropagation() also keeps a button click from bubbling
  // into #book's own click-to-flip handler — the album box sits well clear
  // of the actual page-turn zones, but this is defensive regardless of
  // exact pixel geometry, not reliant on it.
  stage.addEventListener(
    'click',
    (e) => {
      const target = e.target;
      if (!(target instanceof Element)) return;
      const isPrev = target.closest('.photo-album-prev');
      const isNext = !isPrev && target.closest('.photo-album-next');
      if (!isPrev && !isNext) return;
      const album = albumFor(target);
      if (!album) return;
      e.preventDefault();
      e.stopPropagation();
      step(album, isPrev ? -1 : 1);
    },
    { capture: true }
  );
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
