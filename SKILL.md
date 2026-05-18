---
name: paper-webpage-builder
description: Build a polished single-page academic project webpage from a paper directory or paper source, including content extraction, figure selection/conversion, module planning, visual design, tables, assets, and validation. Use when asked to create or update webpages for papers, benchmarks, arXiv-style projects, OpenRaiser project pages, or paths containing paper.tex/PDF/images/assets.
---

# Paper Webpage Builder

Use this skill to turn a paper project folder into a web-ready project page. It is optimized for repos with `paper.tex`, `*.pdf`, `images/`, and `assets/`, but also works from a PDF plus image assets.

## Core Rule

Do not mechanically clone an existing webpage. Use prior pages only as references for interaction patterns and content completeness. The final design must follow the target paper's topic, figures, color palette, density, and audience.

Two failure modes to actively avoid:

- Do not reuse a background system from another paper page by default. Grids, coordinate paper, dark sections, gradients, or canvas textures are allowed only when they are supported by the target paper's own figures, domain, or visual language.
- Do not summarize away central evidence. If the paper's main claim depends on a main experiment table, benchmark comparison table, dataset statistics table, or ablation table, the webpage must include that table in full or provide a clearly equivalent full presentation.

## Workflow

1. Inspect inputs before editing.
   - Locate paper source, PDF, figures, logos, existing `template.html`, and target `index.html`.
   - Run `scripts/scan_paper.py <paper.tex>` when a TeX source exists. Multi-file projects are followed via `\input`/`\include` automatically.
   - Run `scripts/scan_pdf.py <paper.pdf>` when only a PDF is available; it produces the same shape of inventory (title, authors, abstract, sections, figure/table captions, links).
   - Run `scripts/extract_tables.py <paper.tex>` to dump every table (caption, label, header rows, data rows) as JSON. Use this to seed the table ledger instead of eyeballing the .tex.
   - Build a table ledger before designing: caption, label, section, whether it is main evidence, and whether it must appear fully on the page.
   - Identify important tables as well as figures; main results, benchmark comparisons, dataset statistics, and ablations usually belong on the page.

2. Build a content map.
   - Extract title, authors, affiliations, abstract claim, contributions, links, dataset stats, method description, main results, case studies, citation.
   - Map every central table to a page module. If a central table is too large, plan a scrollable/grouped table rather than dropping rows.
   - Decide modules before writing. Typical modules: Hero, Motivation, Method, Dataset/Benchmark, Results, Case Study, Citation.
   - Read `references/module_patterns.md` when choosing sections or table placement.

3. Prepare assets.
   - Prefer paper-provided figures over generic visuals.
   - Convert figures to web assets with `scripts/convert_figures.py <source_images_dir> <target_figures_dir>` (the legacy `convert_figures.sh` is now a shim around it). The script handles multi-page PDFs, `.eps`, `.svg` passthrough, raster passthrough, and writes a `figures.manifest.json` that records source→output mapping plus an empty `alt` field per asset for the LLM to fill.
   - Copy logos and paper PDF into the webpage output folder when useful.
   - Filenames coming out of the manifest are already slug+hash safe; do not rename them again.

4. Generate the citation block.
   - Run `scripts/extract_citation.py <paper.tex> [--pdf paper.pdf]` and embed the produced BibTeX as the page's citation default.
   - Preserve the leading `% NOTE:` comments verbatim; they document fields that were inferred or guessed (year, venue, authors). When any note is present, surface a "verify before publishing" hint near the citation block on the page rather than silently displaying the draft.

5. Design the page around the paper.
   - Derive colors, background, spacing, figure framing, and motifs from the paper's key figures and domain.
   - First list the paper-specific visual cues, then choose the background. A plain surface, soft paper tone, lab-notebook grid, dark canvas, figure-derived gradient, or no visible texture are all valid; none is the default.
   - Keep background transitions coherent across sections. Avoid abrupt dark-to-light jumps unless the entire page system intentionally supports that contrast.
   - Read `references/design_principles.md` when deciding visual style or revising design feedback.

6. Implement the webpage.
   - Produce a self-contained single-page `index.html` unless the repo already has a framework.
   - Include responsive navigation, resource buttons, figure zoom/modal behavior, and readable tables.
   - Include full central tables with horizontal scroll on mobile, sticky headers when useful, grouped rows when needed, and highlights for the proposed method or best values.
   - Use charts only when they clarify a key result beyond the paper figures.
   - Avoid hidden dependency on the source paper directory; generated page should work from the webpage folder.

7. Validate.
   - Run `scripts/check_webpage_links.py <index.html>` to verify local `src`/`href` assets.
   - Reconcile the table ledger against the page: every central table is included fully or has an explicit reason and equivalent representation.
   - Recheck the design for inherited style artifacts: background, palette, hero layout, and cards should match this paper rather than a prior generated page.
   - Run available HTML sanity checks, such as `xmllint --html --noout`.
   - If browser tooling exists, capture desktop/mobile screenshots and check for overflow, missing assets, or poor contrast.
   - Report any validation you could not run.

## Output Expectations

In the final response, include:
- The generated/updated `index.html` path.
- The major modules included.
- The important figures/tables included.
- Suggested project keywords or tags for discovery.
- The quality checks performed for links, HTML sanity, responsive layout, asset independence, and visual consistency.
- Validation performed and remaining risks.

## Reference Files

- `references/module_patterns.md`: section patterns, paper-content extraction targets, and table handling.
- `references/design_principles.md`: visual design rules for paper webpages.

## Scripts

- `scripts/scan_paper.py`: summarize TeX title/authors/abstract/sections/figures/tables/links; follows `\input`/`\include`.
- `scripts/scan_pdf.py`: PDF-only inventory in the same shape as `scan_paper.py` (used for `kind: pdf_with_assets`).
- `scripts/extract_tables.py`: dump every LaTeX table (caption/label/header/data rows) as JSON for the table ledger.
- `scripts/extract_citation.py`: produce a best-effort BibTeX draft with explicit notes for unverified fields.
- `scripts/convert_figures.py` (and `convert_figures.sh` shim): convert paper figures to web assets and emit `figures.manifest.json`. Handles multi-page PDFs, `.eps`, `.svg`, raster passthrough, and CJK filenames.
- `scripts/check_webpage_links.py`: check local `src`, `href`, and `data-figure` targets in an HTML file.
