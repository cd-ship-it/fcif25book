// Click-to-play YouTube embed. generate.py emits an invisible
// `.yt-trigger` overlay over the video's spot rather than a live iframe,
// so the PDF's own thumbnail artwork (already baked into the background
// image) shows through until the reader actually wants to watch — swap it
// for a real <iframe class="yt-embed"> only on click, autoplaying since
// that click IS the "play" action.

function activate(trigger: HTMLElement): void {
  const src = trigger.dataset.ytEmbed;
  if (!src) return;
  const iframe = document.createElement('iframe');
  iframe.id = trigger.id;
  iframe.className = 'yt-embed';
  iframe.src = `${src}?autoplay=1`;
  iframe.title = 'YouTube video player';
  iframe.setAttribute('frameborder', '0');
  iframe.setAttribute(
    'allow',
    'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share'
  );
  iframe.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
  iframe.allowFullscreen = true;
  // #{id} in the generated CSS positions by id, not class, so the iframe
  // inherits the exact same left/top/width/height the trigger div had —
  // no separate position rule needed for the "activated" state.
  trigger.replaceWith(iframe);
}

function triggerFor(target: EventTarget | null): HTMLElement | null {
  if (!(target instanceof Element)) return null;
  return target.closest<HTMLElement>('.yt-trigger');
}

function init(): void {
  const stage = document.getElementById('stage');
  if (!stage) return;

  // Event delegation on #stage (stable across rebuilds), not on the
  // .yt-trigger elements themselves — they're children of #book, which
  // flipbook.client.ts destroys and recreates on every desktop/mobile
  // breakpoint crossing. Same pattern as photo-zoom.client.ts.
  stage.addEventListener('click', (e) => {
    const trigger = triggerFor(e.target);
    if (!trigger) return;
    activate(trigger);
  });

  stage.addEventListener('keydown', (e) => {
    const ke = e as KeyboardEvent;
    if (ke.key !== 'Enter' && ke.key !== ' ') return;
    const trigger = triggerFor(e.target);
    if (!trigger) return;
    ke.preventDefault();
    activate(trigger);
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
