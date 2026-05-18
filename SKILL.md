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
   - Plan figure layout from the actual converted image ratios in `figures.manifest.json`. Wide pipeline/heatmap/table figures, tall case figures, and compact charts should not be forced into one equal-height grid.
   - Avoid fixed-height or fixed-aspect figure cards with `object-fit: contain` for paper figures. Use natural image height (`width: 100%; height: auto`) by default; reserve fixed boxes for icons, logos, thumbnails, or zoom modals.
   - Put figures side-by-side only when their aspect ratios are compatible, or when one side is balanced by text/table content instead of another image. If max/min ratio is above about 1.25, stack them or use a main-figure-plus-notes composition.
   - Keep background transitions coherent across sections. Avoid abrupt dark-to-light jumps unless the entire page system intentionally supports that contrast.
   - Read `references/design_principles.md` when deciding visual style or revising design feedback. The "Measurable Criteria" section there names the thresholds the design-drift check enforces.

6. Implement the webpage.
   - Start from `assets/single-page-template.html`. It includes semantic landmarks (`header`/`nav`/`main`/`footer`), a skip-link, a `prefers-reduced-motion` fallback, a CJK-friendly font stack, and the `{{LANG}} {{TITLE}} {{DESCRIPTION}} {{CANONICAL_URL}} {{OG_IMAGE}} {{JSONLD}}` placeholders. Fill them with `scripts/render_template.py` (or `scripts/inject_metadata.py --inplace` if you only need to refresh the head block of an existing page).
   - Set `<html lang="...">` to the paper's language (BCP-47: `en`, `zh-CN`, `ja`, `ko`, etc.); the scan scripts do not auto-detect this. For CJK papers keep the bundled font stack and add `lang` attributes around any embedded English titles so browsers pick the right glyphs.
   - Generate the head metadata once via `scripts/inject_metadata.py --title ... --description ... --canonical ... --og-image ... --author ...` and pipe its `render-values` JSON into `render_template.py`. Use `--arxiv` / `--doi` when known so the ScholarlyArticle JSON-LD includes a stable identifier.
   - Produce a self-contained single-page `index.html` unless the repo already has a framework.
   - Include responsive navigation, resource buttons, figure zoom/modal behavior, and readable tables.
   - For primary paper figures, do not use equal-ratio card grids unless all figures in that grid share a close aspect ratio. If a layout needs equal rhythm, align captions/text, not the image boxes.
   - Use compact/narrow table treatments for two- or three-column tables. Do not stretch low-density tables across the full page just because wide result tables need full-width scroll containers, and do not leave narrow tables isolated with a large blank area to the right; pair them with related notes, metrics, or figures.
   - Include full central tables with horizontal scroll on mobile, sticky headers when useful, grouped rows when needed, and highlights for the proposed method or best values. Tag each rendered `<table>` (or its wrapping `<section>`) with `data-tex-label="<label>"` so step 7 can reconcile it.
   - Use charts only when they clarify a key result beyond the paper figures.
   - Avoid hidden dependency on the source paper directory; generated page should work from the webpage folder.

7. Validate.
   - Run `scripts/check_webpage_links.py <index.html> --full` for the broader lint: missing `src`/`href`/`data-figure`, CSS `url(...)`, `srcset`, `<source>`/`<video poster>`/`preload`, `og:image`/`twitter:image`, broken `#fragment` targets, duplicate ids, missing `alt`/`title` on `<img>`/`<iframe>`, and path-traversal hrefs that resolve outside the page directory. Use `--json` when you need a machine-readable report.
   - Reconcile the table ledger against the page with `scripts/reconcile_tables.py --ledger <ledger.json> --html <index.html>`. The ledger is the JSON produced by `extract_tables.py` in step 1; tag any HTML `<table>` (or its wrapping `<section>`) with `data-tex-label="<label>"` to enable strict matching. The script flags missing, abbreviated, and column-stripped tables; treat any "MISSING(central)" or "abbrev" line as a blocker.
   - Run `scripts/check_html_sanity.py <index.html>` for HTML5-aware validation. It prefers `html5validator`, then `tidy`, then `html5lib`; without those installed it falls back to a stdlib structural check and says so explicitly. Do NOT use `xmllint --html` — it false-flags HTML5 elements like `<main>`, `<dialog>`, and `<picture>`.
   - Recheck the design with `scripts/check_design_drift.py --html <index.html> --manifest <figures.manifest.json> [--reports-dir reports]`. It computes palette overlap between the figure colors and the page's chosen colors, flags unsupported grid/dot/notebook backgrounds, warns about fixed figure containers that can create blank space, warns about mixed-ratio figures placed in the same row, warns about overstretched low-column tables, and warns when class-token overlap with a sibling `reports/<other>/index.html` exceeds 70% (likely template clone). Treat any warning as a design review item, not silent acceptance.
   - Capture responsive screenshots with `scripts/capture_screenshots.py <index.html> --out-dir reports/<slug>/screenshots`. The script tries Playwright, then Pyppeteer, then headless Chromium; if none are installed it skips cleanly with `meta.json.status == "skipped"` so the rest of validation can continue.
   - Report any validation you could not run, including the `meta.json` skip reason when screenshots were not captured.

## Output Expectations

In the final response, include:
- The generated/updated `index.html` path.
- The major modules included.
- The important figures/tables included.
- The page metadata you set (`lang`, canonical URL, OG image; DOI/arXiv if known) — these populate the `metadata` block of the output schema.
- Suggested project keywords or tags for discovery (required, at least one).
- The quality checks performed for links, HTML sanity, responsive layout, asset independence, visual consistency, table reconciliation, and design drift (required; use `not_run` with a reason rather than omitting an entry).
- Validation performed and remaining risks.

The output is validated against `schemas/output.schema.json`; `keywords` and `quality_checks` are required.

## Reference Files

- `references/module_patterns.md`: section patterns, paper-content extraction targets, and table handling.
- `references/design_principles.md`: visual design rules for paper webpages.

## Scripts

- `scripts/scan_paper.py`: summarize TeX title/authors/abstract/sections/figures/tables/links; follows `\input`/`\include`. Emits an explicit warning when the file is not UTF-8 (with the fallback encoding it used).
- `scripts/scan_pdf.py`: PDF-only inventory in the same shape as `scan_paper.py` (used for `kind: pdf_with_assets`).
- `scripts/extract_tables.py`: dump every LaTeX table (caption/label/header/data rows) as JSON for the table ledger.
- `scripts/extract_citation.py`: produce a best-effort BibTeX draft with explicit notes for unverified fields.
- `scripts/convert_figures.py` (and `convert_figures.sh` shim): convert paper figures to web assets and emit `figures.manifest.json`. Handles multi-page PDFs, `.eps`, `.svg`, raster passthrough, and CJK filenames.
- `scripts/render_template.py`: substitute `{{NAME}}` placeholders in `assets/single-page-template.html`; `--inplace` refreshes only the head metadata of an existing page.
- `scripts/inject_metadata.py`: build SEO + Schema.org `ScholarlyArticle` JSON-LD; outputs `render_template.py` values, a copy-paste meta block, or runs the in-place head refresh in one shot.
- `scripts/check_webpage_links.py`: link/lint check for local assets; `--full` adds CSS `url(...)`, `srcset`, `<source>`/`poster`, `preload`, `og:image`, `#fragment` targets, duplicate ids, missing `alt`/`title`, and path-traversal warnings.
- `scripts/reconcile_tables.py`: cross-check the LaTeX table ledger against `<table>`/`data-tex-label` in the rendered HTML.
- `scripts/check_html_sanity.py`: HTML5-aware sanity check (html5validator → tidy → html5lib → stdlib fallback).
- `scripts/check_design_drift.py`: palette overlap between figures and page, plus figure-container, grid/dark/clone warnings against sibling `reports/`.
- `scripts/capture_screenshots.py`: desktop+mobile screenshots and `meta.json` (Playwright → Pyppeteer → headless Chromium; skips cleanly if none installed).
