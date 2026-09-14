// Pulls "閱讀全文" (Read Full Text) article content from the parent
// project's ../details/*.md + ../details/images/ into this app, and
// auto-generates src/config/readmore.config.ts from it.
//
// ../details/ is the source of truth (like ../Timeline/ is for the
// timeline feature) — write/edit articles there, then re-run this script.
// It does three things:
//
//   1. Transforms each ../details/*.md into src/details/*.md: the source
//      files put the title as a "# Heading" and the author as an
//      "*italic*" line directly in the body (no frontmatter) — this pulls
//      those two into YAML frontmatter (title/subtitle/page) the way
//      index.astro expects. Image references (`images/foo.jpg`) need no
//      rewriting since step 2 puts the actual files right next to these.
//   2. Copies ../details/images/* to src/details/images/* — co-located
//      with the .md files (NOT public/): Astro's markdown compiler
//      resolves a relative image path as a build-time module import, not a
//      runtime URL, so it has to be a real file reachable from src/.
//   3. Auto-generates src/config/readmore.config.ts by matching every
//      "閱讀全文" trigger div in the parent project's already-generated
//      pageN.html/pageN.generated.css against a details file for that page
//      (by filename: "Page N.md", or "Page N Left/Right.md" /
//      "Page N Top/Bottom.md" when a page has two buttons — disambiguated
//      by comparing the two buttons' actual (left, top) position, not a
//      hardcoded page list, so this keeps working if a future PDF revision
//      changes which pages have one vs two). A trailing parenthetical in
//      the filename, e.g. "Page 57 (with in text photos).md", is ignored
//      when matching.
//
// Usage: node scripts/sync-details.mjs
// Run this in addition to sync-from-source.mjs (either order — this reads
// the ROOT project's pageN.html/.generated.css directly, not the synced
// copies, so it doesn't depend on that script having run first).

import { readFileSync, writeFileSync, mkdirSync, copyFileSync, readdirSync, rmSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..', '..'); // ficf_pdf_html/
const APP = join(__dirname, '..'); // webapp/

const SRC_DETAILS = join(ROOT, 'details');
const SRC_IMAGES = join(SRC_DETAILS, 'images');
const OUT_DETAILS = join(APP, 'src', 'details');
// Co-located under src/details/ (NOT public/), matching what Astro's
// markdown compiler actually expects: a relative image path in .md content
// is resolved as a build-time module import (Vite bundles/hashes it,
// handling the GitHub Pages /fcif25book base path automatically), not a
// plain runtime URL string — a public/ path isn't part of that module
// graph and fails the build ("Rolldown failed to resolve import ...").
// Since this sits next to the .md files, the markdown's own `images/foo.jpg`
// references need no rewriting at all.
const OUT_IMAGES = join(APP, 'src', 'details', 'images');

// ---------------------------------------------------------------------
// 1 + 2. Transform markdown, copy images.
// ---------------------------------------------------------------------

rmSync(OUT_DETAILS, { recursive: true, force: true });
mkdirSync(OUT_DETAILS, { recursive: true });
rmSync(OUT_IMAGES, { recursive: true, force: true });
mkdirSync(OUT_IMAGES, { recursive: true });

for (const file of readdirSync(SRC_IMAGES)) {
  copyFileSync(join(SRC_IMAGES, file), join(OUT_IMAGES, file));
}

function yamlEscape(s) {
  return s.replace(/"/g, '\\"');
}

// "Page 64 Left (with in text photo).md" -> { page: 64, position: 'left' }
// "Page 6.md" -> { page: 6, position: null }
function parseFilename(filename) {
  const base = filename.replace(/\.md$/, '').replace(/\s*\(.*?\)\s*$/, '');
  const m = base.match(/^Page\s+(\d+)(?:\s+(Left|Right|Top|Bottom))?$/i);
  if (!m) return null;
  return { page: parseInt(m[1], 10), position: m[2] ? m[2].toLowerCase() : null };
}

const detailsMeta = []; // { page, position, outSlug }

for (const filename of readdirSync(SRC_DETAILS)) {
  if (!filename.endsWith('.md')) continue;
  const parsed = parseFilename(filename);
  if (!parsed) {
    console.warn(`[sync-details] Skipping "${filename}" — doesn't match "Page N[.md]" / "Page N Left|Right|Top|Bottom.md"`);
    continue;
  }

  const raw = readFileSync(join(SRC_DETAILS, filename), 'utf-8');
  const lines = raw.split('\n');

  let i = 0;
  while (i < lines.length && lines[i].trim() === '') i++;
  const titleMatch = lines[i]?.match(/^#\s+(.+)$/);
  const title = titleMatch ? titleMatch[1].trim() : parsed.page.toString();
  if (titleMatch) i++;
  while (i < lines.length && lines[i].trim() === '') i++;
  const authorMatch = lines[i]?.match(/^\*(.+)\*$/);
  const subtitle = authorMatch ? authorMatch[1].trim() : null;
  if (authorMatch) i++;
  while (i < lines.length && lines[i].trim() === '') i++;

  // Image references (`![](images/foo.jpg)`) need no rewriting — images/
  // sits right next to the .md file in both the source and the synced copy.
  const body = lines.slice(i).join('\n').trim();

  const outSlug = `page${parsed.page}readmore${parsed.position ? parsed.position[0].toUpperCase() + parsed.position.slice(1) : ''}`;

  const frontmatter = [
    '---',
    `title: "${yamlEscape(title)}"`,
    subtitle ? `subtitle: "${yamlEscape(subtitle)}"` : null,
    `page: ${parsed.page}`,
    '---',
    '',
  ]
    .filter((l) => l !== null)
    .join('\n');

  writeFileSync(join(OUT_DETAILS, `${outSlug}.md`), frontmatter + body + '\n');
  detailsMeta.push({ page: parsed.page, position: parsed.position, outSlug });
}

console.log(`[sync-details] Transformed ${detailsMeta.length} articles, copied ${readdirSync(OUT_IMAGES).length} images.`);

// ---------------------------------------------------------------------
// 3. Auto-generate readmore.config.ts from the parent project's already-
//    generated pageN.html / pageN.generated.css (root, not webapp/src —
//    this doesn't depend on sync-from-source.mjs having run).
// ---------------------------------------------------------------------

const byPage = new Map(); // page -> [{ id, left, top }]

for (const meta of detailsMeta) {
  if (byPage.has(meta.page)) continue; // already scanned this page's HTML
  const htmlPath = join(ROOT, `page${meta.page}.html`);
  const cssPath = join(ROOT, `page${meta.page}.generated.css`);
  let html, css;
  try {
    html = readFileSync(htmlPath, 'utf-8');
    css = readFileSync(cssPath, 'utf-8');
  } catch {
    console.warn(`[sync-details] Missing page${meta.page}.html/.generated.css — run generate.py first. Skipping page ${meta.page}.`);
    continue;
  }

  const triggers = [];
  const divRe = /<div class="t" id="(p\d+-t\d+)">閱讀全文<\/div>/g;
  let m;
  while ((m = divRe.exec(html))) {
    const id = m[1];
    const ruleRe = new RegExp(`#${id} \\{[^}]*left:([\\d.]+)px;[^}]*top:([\\d.]+)px`);
    const ruleMatch = css.match(ruleRe);
    if (!ruleMatch) {
      console.warn(`[sync-details] Found trigger #${id} but no position rule in page${meta.page}.generated.css — skipping.`);
      continue;
    }
    triggers.push({ id, left: parseFloat(ruleMatch[1]), top: parseFloat(ruleMatch[2]) });
  }
  byPage.set(meta.page, triggers);
}

const configRows = [];

for (const meta of detailsMeta) {
  const triggers = byPage.get(meta.page) ?? [];
  let id;

  if (triggers.length === 1) {
    id = triggers[0].id;
  } else if (triggers.length >= 2) {
    // Disambiguate by whichever axis actually varies between the two
    // buttons on this page — Left/Right (compare x) or Top/Bottom
    // (compare y) — rather than a hardcoded list of which pages use which,
    // so this keeps working if a future PDF revision changes the mix.
    const sorted = [...triggers].sort((a, b) =>
      Math.abs(a.left - b.left) >= Math.abs(a.top - b.top) ? a.left - b.left : a.top - b.top
    );
    const wantFirst = meta.position === 'left' || meta.position === 'top';
    const wantLast = meta.position === 'right' || meta.position === 'bottom';
    if (wantFirst) id = sorted[0]?.id;
    else if (wantLast) id = sorted[sorted.length - 1]?.id;
  }

  if (!id) {
    console.warn(`[sync-details] Could not find a trigger element for page ${meta.page}${meta.position ? ' ' + meta.position : ''} (${meta.outSlug}) — omitting from readmore.config.ts.`);
    continue;
  }

  configRows.push({ page: meta.page, elementId: id, detailsFile: meta.outSlug });
}

configRows.sort((a, b) => a.page - b.page || a.elementId.localeCompare(b.elementId));

const configPath = join(APP, 'src', 'config', 'readmore.config.ts');
const rowsText = configRows
  .map((r) => `  { page: ${r.page}, elementId: '${r.elementId}', detailsFile: '${r.detailsFile}' },`)
  .join('\n');

const configSource = `// ---------------------------------------------------------------------------
// "閱讀全文" (Read Full Text) button -> details modal wiring.
//
// AUTO-GENERATED by scripts/sync-details.mjs from ../details/*.md — do not
// hand-edit the array below, it will be overwritten on the next sync. Add a
// new article by dropping a "Page N.md" (or "Page N Left/Right/Top/Bottom.md"
// for a page with two buttons) into ../details/, then re-running
// \`node scripts/sync-details.mjs\`.
//
// The PDF renders each "閱讀全文" button's outline/arrow graphic into the
// page's background PNG (see ../../generate.py) — only the button's TEXT is
// real HTML (one of the absolutely-positioned \`.t\` divs in
// src/generated/fragments/pageN.html, id \`p{N}-t{X}\`).
// ---------------------------------------------------------------------------

export interface ReadMoreLink {
  /** Source PDF page number, for reference/debugging only. */
  page: number;
  /** Element id of the "閱讀全文" text span in that page's generated fragment. */
  elementId: string;
  /** Filename (without .md) under src/details/. */
  detailsFile: string;
}

export const readMoreLinks: ReadMoreLink[] = [
${rowsText}
];

export default readMoreLinks;
`;

writeFileSync(configPath, configSource);
console.log(`[sync-details] Wrote ${configRows.length} rows to src/config/readmore.config.ts.`);
