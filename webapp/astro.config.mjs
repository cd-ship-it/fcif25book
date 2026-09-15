// @ts-check
import { defineConfig } from 'astro/config';

// Production is served from the custom domain ficf25book.com (see the
// repo's CNAME file) at the domain ROOT — GitHub Pages does NOT nest
// custom-domain sites under /reponame/ the way it does for the bare
// *.github.io project-page URL, so the deployed `base` must be '/', not
// '/fcif25book'. (cd-ship-it.github.io/fcif25book/ still exists but is now
// just a 301 redirect to the custom domain, handled automatically by
// GitHub once a custom domain is configured.)
//
// Local dev keeps the OLD '/fcif25book' base regardless, so
// http://localhost:4321/fcif25book/ keeps working exactly as it always
// has — no need to relearn a new local URL just because production's
// path structure changed. defineConfig() in this Astro version only
// accepts a plain object, not a (command) => {...} callback, so this
// checks process.argv directly instead — `npm run dev` runs `astro dev`,
// `npm run build` runs `astro build`, and that literal word shows up in
// argv either way.
const isDev = process.argv.includes('dev');

export default defineConfig({
  site: 'https://ficf25book.com',
  base: isDev ? '/fcif25book' : '/',
});
