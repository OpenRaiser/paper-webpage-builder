# Module Patterns

Use the paper's own narrative, not a fixed template. These patterns are defaults to adapt.

## Content Extraction Targets

- Hero: title, short claim, authors, affiliations, Paper/Code/Dataset/Project links, 4-6 headline metrics.
- Motivation: what gap the paper identifies, why existing work fails, one strong overview/motivation figure.
- Method: 2-4 conceptual steps or modules, plus the main framework figure.
- Dataset/Benchmark: data construction pipeline, split/statistics, taxonomy/category figure, key table.
- Results: main result table in full when it is central; benchmark comparison table when it supports the paper's novelty claim; compact chart or takeaway cards; appendix figures if useful.
- Case Study: one qualitative figure, error analysis, human study or alignment plot.
- Citation: BibTeX/code block, optional copy button, and a small citation-status note if arXiv/venue data is not final. Do not duplicate hero resource buttons here.

Hero is a content inventory, not a mandated layout. Do not interpret the Hero list as a requirement to place title, authors, links, metrics, and a key figure into one two-column block. Select only the above-fold elements that communicate the paper's central claim; move secondary evidence to Motivation, Method, Dataset/Benchmark, Results, or Case Study.

Avoid generic split heroes where oversized title text occupies the left column and a paper figure/card occupies the right column. Use that composition only when the paper's own lead visual is meant to be inspected in the first viewport and the layout remains balanced. Prefer a paper-specific hero mode: thesis-first, figure-led, benchmark-dashboard, system-workflow, or brand-led.

## Table Handling

Tables should enter the webpage when they carry the core claim.

- Start with a table ledger: caption, label, source section, row/column scope, centrality, and page destination.
- Main results: include the full table, not just a summary or selected rows.
- Benchmark comparisons: include in full when the paper uses them to claim coverage, novelty, or state-of-the-art positioning.
- Dataset stats: include a compact web table or metric grid, but preserve all dimensions that support the claim.
- Ablations: include when the user asks for completeness, the paper's method depends on them, or the abstract/conclusion cites them.
- Large tables: keep them statically readable; use wider modules, grouped columns, or multiple complete sub-tables instead of horizontal scroll. Keep sticky headers if practical, group rows by model family, highlight the proposed method and best values.
- Medium explanatory tables with 4-6 columns should usually use full module width when headers or values are long. Do not apply a narrow/compact max-width blindly.
- Short code/category columns such as `Family`, `Active stages`, `Tier`, `Rank`, stage IDs, objective IDs, and compact labels should be centered and often `white-space: nowrap`; long explanation columns should remain left-aligned.
- If a table is too wide, split it by metric group or model family while preserving all rows and values.
- If a figure duplicates a table, the table can be represented visually only when all values remain inspectable or a linked full table is present.

Before finishing, reconcile the ledger:

- each central table is present fully;
- each non-central omitted table has a reason;
- displayed values match the source table;
- captions make clear when a table is selected, abbreviated, or full.

## Figure Selection

Prefer 5-9 high-signal visuals:

- Teaser or motivation figure.
- Framework/method figure.
- Data pipeline.
- Dataset distribution/taxonomy figure.
- Main result figure or chart.
- Fine-grained/appendix result figure if it adds diagnostic value.
- Qualitative case study.
- Human evaluation or consistency plot.

Avoid showing every figure. Exclude prompt screenshots and appendix-only details unless specifically requested.

## Grid Density Rule

- Grids with more than 4 columns MUST include a `@media (max-width: 960px)` rule that reduces to at most 3 columns, and a `@media (max-width: 720px)` that reduces to 1 or 2 columns.
- Any card or grid item narrower than 180px at any common viewport (360-1440px) is a layout defect — test by calculating `container_width / column_count` at each breakpoint.
- When items have short labels (2-3 words), 3-4 columns is the practical maximum for readability on medium screens.
- Responsive tests: mentally evaluate grid density at 360px, 768px, 960px, and 1440px before finishing the layout.

## Footer

- Institution, lab, project, and partner logos belong here, not in Citation.
- Logo strip: all logos use a fixed `height` (recommend 48px) with `object-fit: contain` for uniform visual weight. Never let logos inherit their natural (often wildly different) heights.
- Footer links use the same muted color system as navigation secondary links.
- Keep footer compact — one row of logos, one row of links/copyright, not elaborate multi-section footers for a single-page academic site.

## Paired Figures

When placing two figures side-by-side:

- Compare their aspect ratios first. If max/min > 1.25, prefer stacking or a main-figure-plus-notes composition over equal-width columns.
- When aspect ratios are compatible, use equal-width columns with natural image height (`width: 100%; height: auto`) and align captions/text, not image boxes.
- Do not use `object-fit: contain` on primary paper figures to force equal-height cards. That creates blank space and weakens inspectability.
- If caption alignment matters, use a caption/text rhythm or stack the figures; reserve fixed-height `object-fit: contain` treatments for thumbnails, icons, logos, and bounded non-primary media.

## Citation

- Keep the Citation module narrow and predictable: heading, BibTeX/code block, optional copy button, and at most one short muted note.
- Strip internal extraction comments from the displayed BibTeX.
- Use a small pending-verification hint for draft metadata instead of a warning banner.
- Do not include `Project resources`, Code/Dataset buttons, or institution logos in Citation.
- Do not invent license claims. Show license only when verified from source files or user-provided links.
