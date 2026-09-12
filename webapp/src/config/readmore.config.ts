// ---------------------------------------------------------------------------
// "閱讀全文" (Read Full Text) button -> details modal wiring.
//
// The PDF renders each "閱讀全文" button's outline/arrow graphic into the
// page's background PNG (see ../../generate.py) — only the button's TEXT is
// real HTML (one of the absolutely-positioned `.t` divs in
// src/generated/fragments/pageN.html, id `p{N}-t{X}`). This file maps each
// such trigger element to the markdown file (under src/details/) whose
// content should appear in the popup modal when it's clicked.
//
// To find new triggers when extending to more pages: grep the parent
// project's data/pages.json for "閱讀全文", then check pageN.html for the
// element id genereate.py assigned to that span.
//
// Adding a new one:
//   1. Write src/details/pageNreadmore.md (frontmatter: title, subtitle, page)
//   2. Add a row here with that page's trigger element id.
// No other file needs to change — index.astro renders a modal panel for
// every row here that has a matching markdown file.
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
  { page: 6, elementId: 'p6-t1', detailsFile: 'page6readmore' },
  { page: 7, elementId: 'p7-t9', detailsFile: 'page7readmore' },
];

export default readMoreLinks;
