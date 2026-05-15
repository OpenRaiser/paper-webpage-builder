# Module Patterns

Use the paper's own narrative, not a fixed template. These patterns are defaults to adapt.

## Content Extraction Targets

- Hero: title, short claim, authors, affiliations, Paper/Code/Dataset/Project links, 4-6 headline metrics.
- Motivation: what gap the paper identifies, why existing work fails, one strong overview/motivation figure.
- Method: 2-4 conceptual steps or modules, plus the main framework figure.
- Dataset/Benchmark: data construction pipeline, split/statistics, taxonomy/category figure, key table.
- Results: main result table in full when it is central; benchmark comparison table when it supports the paper's novelty claim; compact chart or takeaway cards; appendix figures if useful.
- Case Study: one qualitative figure, error analysis, human study or alignment plot.
- Citation: BibTeX draft with a warning if arXiv/venue data is not final.

## Table Handling

Tables should enter the webpage when they carry the core claim.

- Start with a table ledger: caption, label, source section, row/column scope, centrality, and page destination.
- Main results: include the full table, not just a summary or selected rows.
- Benchmark comparisons: include in full when the paper uses them to claim coverage, novelty, or state-of-the-art positioning.
- Dataset stats: include a compact web table or metric grid, but preserve all dimensions that support the claim.
- Ablations: include when the user asks for completeness, the paper's method depends on them, or the abstract/conclusion cites them.
- Large tables: wrap in horizontal scroll, keep sticky headers if practical, group rows by model family, highlight the proposed method and best values.
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
