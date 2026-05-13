# Module Patterns

Use the paper's own narrative, not a fixed template. These patterns are defaults to adapt.

## Content Extraction Targets

- Hero: title, short claim, authors, affiliations, Paper/Code/Dataset/Project links, 4-6 headline metrics.
- Motivation: what gap the paper identifies, why existing work fails, one strong overview/motivation figure.
- Method: 2-4 conceptual steps or modules, plus the main framework figure.
- Dataset/Benchmark: data construction pipeline, split/statistics, taxonomy/category figure, key table.
- Results: main result table in full when it is central; compact chart or takeaway cards; appendix figures if useful.
- Case Study: one qualitative figure, error analysis, human study or alignment plot.
- Citation: BibTeX draft with a warning if arXiv/venue data is not final.

## Table Handling

Tables should enter the webpage when they carry the core claim.

- Main results: include the full table, not just a summary.
- Dataset stats: include a compact web table or metric grid.
- Ablations: include when the user asks for completeness or the paper's method depends on them.
- Large tables: wrap in horizontal scroll, keep sticky headers if practical, group rows by model family, highlight the proposed method and best values.

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
