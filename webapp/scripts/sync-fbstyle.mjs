// Pulls generate_fbstyle_md.py's output (../fbstyle-src/md/pageN.md) into
// this Astro app as one JSON array, same intermediate-JSON pattern as the
// old posts.json-based version — just parsing per-page Markdown+frontmatter
// now instead of syncing a single pre-built JSON blob. Hand-rolled parser,
// not a general YAML lib: the frontmatter shape is entirely our own
// (written by generate_fbstyle_md.py), so it only needs to understand
// exactly that shape, not YAML in general.
//
// No photo-copying needed here, same as before: hero images reference
// webapp/public/assets/photos/ directly (already a full mirror, maintained
// by sync-from-source.mjs). Decorative background art (from
// extract_fbstyle_decor.py's fbstyle-src/decor/pageN-decor1.png — the
// largest/primary decorative PNG on that page, real transparency and all,
// no text baked in) IS copied here, into webapp/public/assets/fbstyle-decor/,
// since nothing else in the app already mirrors that folder.
//
// Run after `python3 generate_fbstyle_md.py` (and, to pick up any new/
// changed decoration, `python3 extract_fbstyle_decor.py`) in the parent
// project. Usage: node scripts/sync-fbstyle.mjs

import { readFileSync, writeFileSync, mkdirSync, readdirSync, copyFileSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..', '..'); // ficf_pdf_html/
const APP = join(__dirname, '..'); // webapp/

const mdDir = join(ROOT, 'fbstyle-src', 'md');
const decorDir = join(ROOT, 'fbstyle-src', 'decor');
const decorOutDir = join(APP, 'public', 'assets', 'fbstyle-decor');
const outDir = join(APP, 'src', 'generated-fbstyle');
const outPath = join(outDir, 'posts.json');

// Unquotes a "..." YAML-style scalar (our own generator only ever emits
// double-quoted scalars, with \" and \\ as its only escapes).
function unquote(s) {
  const m = s.match(/^"(.*)"$/s);
  const raw = m ? m[1] : s;
  return raw.replace(/\\(["\\])/g, '$1');
}

function parseFrontmatter(text) {
  const m = text.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
  if (!m) throw new Error('missing frontmatter block');
  const [, fmText, body] = m;
  const lines = fmText.split('\n');
  const fm = { categories: [], photos: [] };
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line === 'categories:') {
      i++;
      while (i < lines.length && lines[i].startsWith('  - ')) {
        fm.categories.push(unquote(lines[i].slice(4)));
        i++;
      }
      continue;
    }
    if (line === 'photos:') {
      i++;
      while (i < lines.length && lines[i].startsWith('  - file: ')) {
        const file = unquote(lines[i].slice('  - file: '.length));
        i++;
        let caption = '';
        if (i < lines.length && lines[i].startsWith('    caption: ')) {
          caption = unquote(lines[i].slice('    caption: '.length));
          i++;
        }
        fm.photos.push({ file, caption });
      }
      continue;
    }
    const kv = line.match(/^(\w+):\s*(.*)$/);
    if (kv) {
      const [, key, rawVal] = kv;
      fm[key] = key === 'page' ? parseInt(rawVal, 10) : unquote(rawVal);
    }
    i++;
  }
  return { ...fm, body: body.trim() };
}

mkdirSync(outDir, { recursive: true });
mkdirSync(decorOutDir, { recursive: true });

const files = readdirSync(mdDir).filter((f) => f.endsWith('.md')).sort(
  (a, b) => parseInt(a.match(/\d+/)[0], 10) - parseInt(b.match(/\d+/)[0], 10)
);

let decorCount = 0;
const posts = files.map((f) => {
  const post = parseFrontmatter(readFileSync(join(mdDir, f), 'utf-8'));
  const decorSrc = join(decorDir, `page${post.page}-decor1.png`);
  if (existsSync(decorSrc)) {
    const decorFile = `page${post.page}.png`;
    copyFileSync(decorSrc, join(decorOutDir, decorFile));
    post.decor = decorFile;
    decorCount++;
  }
  return post;
});

writeFileSync(outPath, JSON.stringify(posts, null, 2));

console.log(
  `Synced ${posts.length} post(s) (${decorCount} with decoration) from fbstyle-src/md/ -> ${outPath.replace(APP, 'webapp')}`
);
