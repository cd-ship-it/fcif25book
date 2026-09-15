// @ts-check
import { defineConfig } from 'astro/config';

// Served from the custom domain ficf25book.com (see the repo's CNAME file)
// at the domain ROOT — GitHub Pages does NOT nest custom-domain sites under
// /reponame/ the way it does for the bare *.github.io project-page URL, so
// `base` must be '/' here, not '/fcif25book'. (cd-ship-it.github.io/fcif25book/
// still exists but is now just a 301 redirect to the custom domain, handled
// automatically by GitHub once a custom domain is configured — it no longer
// needs its own working base path.)
export default defineConfig({
  site: 'https://ficf25book.com',
  base: '/',
});
