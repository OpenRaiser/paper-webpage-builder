---
name: paper-webpage-builder
description: Build a polished single-page academic project webpage from a paper directory or paper source, including content extraction, figure selection/conversion, module planning, visual design, tables, assets, and validation. Use when asked to create or update webpages for papers, benchmarks, arXiv-style projects, OpenRaiser project pages, or paths containing paper.tex/PDF/images/assets.
---

# Paper Webpage Builder

Use this skill to turn a paper project folder into a web-ready project page. It is optimized for repos with `paper.tex`, `*.pdf`, `images/`, and `assets/`, but also works from a PDF plus image assets.

## Core Rule

Do not mechanically clone an existing webpage. Use prior pages only as references for interaction patterns and content completeness. The final design must follow the target paper's topic, figures, color palette, density, and audience.

## Workflow

1. Inspect inputs before editing.
   - Locate paper source, PDF, figures, logos, existing `template.html`, and target `index.html`.
   - Run `scripts/scan_paper.py <paper.tex>` when a TeX source exists.
   - Identify important tables as well as figures; main results, dataset statistics, and ablations usually belong on the page.

2. Build a content map.
   - Extract title, authors, affiliations, abstract claim, contributions, links, dataset stats, method description, main results, case studies, citation.
   - Decide modules before writing. Typical modules: Hero, Motivation, Method, Dataset/Benchmark, Results, Case Study, Citation.
   - Read `references/module_patterns.md` when choosing sections or table placement.

3. Prepare assets.
   - Prefer paper-provided figures over generic visuals.
   - Convert PDF figures to PNG/SVG-friendly web assets. Use `scripts/convert_figures.sh <source_images_dir> <target_figures_dir>` when applicable.
   - Copy logos and paper PDF into the webpage output folder when useful.
   - Rename web assets to stable ASCII filenames.

4. Design the page around the paper.
   - Derive colors from the paper's key figures and domain. For geometry/GUI papers, grids, coordinate-paper textures, and precise callouts are often appropriate.
   - Keep background transitions coherent across sections. Avoid abrupt dark-to-light jumps unless the entire page system intentionally supports that contrast.
   - Read `references/design_principles.md` when deciding visual style or revising design feedback.

5. Implement the webpage.
   - Produce a self-contained single-page `index.html` unless the repo already has a framework.
   - Include responsive navigation, resource buttons, figure zoom/modal behavior, and readable tables.
   - Use charts only when they clarify a key result beyond the paper figures.
   - Avoid hidden dependency on the source paper directory; generated page should work from the webpage folder.

6. Validate.
   - Run `scripts/check_webpage_links.py <index.html>` to verify local `src`/`href` assets.
   - Run available HTML sanity checks, such as `xmllint --html --noout`.
   - If browser tooling exists, capture desktop/mobile screenshots and check for overflow, missing assets, or poor contrast.
   - Report any validation you could not run.

## Output Expectations

In the final response, include:
- The generated/updated `index.html` path.
- The major modules included.
- The important figures/tables included.
- Validation performed and remaining risks.

## Reference Files

- `references/module_patterns.md`: section patterns, paper-content extraction targets, and table handling.
- `references/design_principles.md`: visual design rules for paper webpages.

## Scripts

- `scripts/scan_paper.py`: summarize TeX title/authors/abstract/sections/figures/tables/links.
- `scripts/convert_figures.sh`: convert one-page PDF figures to PNG with Ghostscript.
- `scripts/check_webpage_links.py`: check local `src`, `href`, and `data-figure` targets in an HTML file.
