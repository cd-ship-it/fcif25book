// Pulls the generated per-page HTML/CSS/background assets from the parent
// project (../extract.py + ../generate.py output) into this Astro app.
//
// The parent project is the single source of truth for turning PDF pages
// into 695x900 HTML/CSS. This script does NOT re-derive layout — it only
// extracts the already-generated `.page` fragment out of each standalone
// pageN.html, concatenates the CSS cascade, and copies image/font assets.
//
// Run after re-running `python3 generate.py` in the parent project, or
// whenever the source page count changes.
//
// Usage: node scripts/sync-from-source.mjs

import { readFileSync, writeFileSync, mkdirSync, copyFileSync, readdirSync, existsSync, rmSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..', '..'); // ficf_pdf_html/
const APP = join(__dirname, '..'); // webapp/

const titlesPath = join(ROOT, 'data', 'titles.json');
if (!existsSync(titlesPath)) {
  console.error('Missing ../data/titles.json — run `python3 generate.py` in the parent project first.');
  process.exit(1);
}
const manifest = JSON.parse(readFileSync(titlesPath, 'utf-8'));
const TOTAL = manifest.total;

const outGenerated = join(APP, 'src', 'generated');
const outFragments = join(outGenerated, 'fragments');
const outAssetsBg = join(APP, 'public', 'assets', 'backgrounds');
const outAssetsFonts = join(APP, 'public', 'assets', 'fonts');

// Clear the output dirs first, not just overwrite — otherwise a source file
// that's renamed or deleted (e.g. a page's background switching from .png
// to .jpg) leaves a stale orphan copy behind instead of actually syncing.
for (const dir of [outFragments, outAssetsBg, outAssetsFonts]) {
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(dir, { recursive: true });
}

// 1. Copy background PNGs + fonts
for (const file of readdirSync(join(ROOT, 'assets', 'backgrounds'))) {
  copyFileSync(join(ROOT, 'assets', 'backgrounds', file), join(outAssetsBg, file));
}
for (const file of readdirSync(join(ROOT, 'assets', 'fonts'))) {
  copyFileSync(join(ROOT, 'assets', 'fonts', file), join(outAssetsFonts, file));
}

// 2. Concatenate the CSS cascade: style.css, then pageN.generated.css + pageN.css for each page.
// Selectors are scoped by unique #pageN / #pN-tX ids, so one global stylesheet is safe.
let css = readFileSync(join(ROOT, 'style.css'), 'utf-8') + '\n';
for (let n = 1; n <= TOTAL; n++) {
  css += `\n/* ---- page ${n} ---- */\n`;
  css += readFileSync(join(ROOT, `page${n}.generated.css`), 'utf-8') + '\n';
  const customPath = join(ROOT, `page${n}.css`);
  if (existsSync(customPath)) {
    css += readFileSync(customPath, 'utf-8') + '\n';
  }
}
// The source CSS uses paths like url('assets/backgrounds/page1.png') that are
// relative to the standalone pageN.html files sitting at the parent project
// root. Once served from this app it lives at <base>generated/book.css
// instead — one directory level below the site's asset root — so rewrite
// to a RELATIVE '../assets/...' rather than an absolute '/assets/...'.
// Relative resolves correctly under any `base` (GitHub Pages serves this
// under a /fcif25book/ subpath, not the domain root), with no base-path
// bookkeeping needed here at all.
css = css.replace(/url\((['"]?)assets\//g, "url($1../assets/");

const outPublicGenerated = join(APP, 'public', 'generated');
mkdirSync(outPublicGenerated, { recursive: true });
writeFileSync(join(outPublicGenerated, 'book.css'), css);

// 3. Extract the `<div class="page" id="pageN">...</div>` fragment out of each standalone pageN.html
const FRAG_RE = (n) => new RegExp(`<div class="page" id="page${n}">[\\s\\S]*?\\n<\\/div>\\n<\\/div>\\n<\\/body>`);

const fragmentPaths = [];
for (let n = 1; n <= TOTAL; n++) {
  const html = readFileSync(join(ROOT, `page${n}.html`), 'utf-8');
  const match = html.match(FRAG_RE(n));
  if (!match) {
    console.error(`Could not find .page fragment in page${n}.html — has the FOOT template in generate.py changed?`);
    process.exit(1);
  }
  // Strip the trailing "</div>\n</div>\n</body>" back down to just the page's own closing </div>
  const fragment = match[0].replace(/\n<\/div>\n<\/body>$/, '');
  const outPath = join(outFragments, `page${n}.html`);
  writeFileSync(outPath, fragment);
  fragmentPaths.push(`page${n}.html`);
}

// 4. Write a manifest the Astro app can import at build time
writeFileSync(
  join(outGenerated, 'manifest.json'),
  JSON.stringify({ ...manifest, fragments: fragmentPaths }, null, 1)
);

console.log(`Synced ${TOTAL} pages from parent project into src/generated/ and public/assets/.`);
