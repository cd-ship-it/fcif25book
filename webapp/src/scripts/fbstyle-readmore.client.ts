// FB-style feed's read-more — expands the article inline within the same
// post card (like Facebook's own "See more"), not a modal. No collapse:
// once expanded, the button is removed — Facebook doesn't offer a
// "retract" either.

function init(): void {
  const buttons = document.querySelectorAll<HTMLElement>('[data-fb-readmore]');

  buttons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const slug = btn.dataset.fbReadmore;
      if (!slug) return;
      const post = btn.closest('.fb-post');
      const panel = post?.querySelector<HTMLElement>(`[data-fb-detail-panel="${slug}"]`);
      if (!panel) return;
      panel.hidden = false;
      btn.remove();
    });
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
