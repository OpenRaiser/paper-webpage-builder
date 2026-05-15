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
   - Run `scripts/scan_paper.py <paper.tex>` when a TeX source exists.
   - Build a table ledger before designing: caption, label, section, whether it is main evidence, and whether it must appear fully on the page.
   - Identify important tables as well as figures; main results, benchmark comparisons, dataset statistics, and ablations usually belong on the page.

2. Build a content map.
   - Extract title, authors, affiliations, abstract claim, contributions, links, dataset stats, method description, main results, case studies, citation.
   - Map every central table to a page module. If a central table is too large, plan a scrollable/grouped table rather than dropping rows.
   - Decide modules before writing. Typical modules: Hero, Motivation, Method, Dataset/Benchmark, Results, Case Study, Citation.
   - Read `references/module_patterns.md` when choosing sections or table placement.

3. Prepare assets.
   - Prefer paper-provided figures over generic visuals.
   - Convert PDF figures to PNG/SVG-friendly web assets. Use `scripts/convert_figures.sh <source_images_dir> <target_figures_dir>` when applicable.
   - Copy logos and paper PDF into the webpage output folder when useful.
   - Rename web assets to stable ASCII filenames.

4. Design the page around the paper.
   - Derive colors, background, spacing, figure framing, and motifs from the paper's key figures and domain.
   - First list the paper-specific visual cues, then choose the background. A plain surface, soft paper tone, lab-notebook grid, dark canvas, figure-derived gradient, or no visible texture are all valid; none is the default.
   - Keep background transitions coherent across sections. Avoid abrupt dark-to-light jumps unless the entire page system intentionally supports that contrast.
   - Read `references/design_principles.md` when deciding visual style or revising design feedback.

5. Implement the webpage.
   - Produce a self-contained single-page `index.html` unless the repo already has a framework.
   - Include responsive navigation, resource buttons, figure zoom/modal behavior, and readable tables.
   - Include full central tables with horizontal scroll on mobile, sticky headers when useful, grouped rows when needed, and highlights for the proposed method or best values.
   - Use charts only when they clarify a key result beyond the paper figures.
   - Avoid hidden dependency on the source paper directory; generated page should work from the webpage folder.

6. Validate.
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

- `scripts/scan_paper.py`: summarize TeX title/authors/abstract/sections/figures/tables/links.
- `scripts/convert_figures.sh`: convert one-page PDF figures to PNG with Ghostscript.
- `scripts/check_webpage_links.py`: check local `src`, `href`, and `data-figure` targets in an HTML file.
