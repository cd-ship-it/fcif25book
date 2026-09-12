// @ts-check
import { defineConfig } from 'astro/config';

// Deployed as a GitHub Pages PROJECT site (not a *.github.io user/org root
// site), so it's served under a /fcif25book/ subpath, not at the domain
// root. `base` must be set for that — see README's "Deployment" section
// for the absolute-URL implications this has throughout the app.
export default defineConfig({
  site: 'https://cd-ship-it.github.io',
  base: '/fcif25book',
});
