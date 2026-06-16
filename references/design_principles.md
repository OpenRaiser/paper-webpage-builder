# Design Principles

## Fit the Paper

Derive the visual system from the paper's topic and figures:

- Geometry/GUI/control: coordinate grids, canvas surfaces, blue/orange callouts, precise strokes when those cues are present in the paper.
- Benchmark/data papers: dense tables, taxonomies, clear statistics, restrained color.
- Agent/tool papers: workflow diagrams, tool icons, process timelines.
- Scientific visualization: larger figures, neutral backgrounds, minimal decoration.

Before writing CSS, make a short visual-cue inventory from the target paper:

- dominant figure colors and contrast level;
- recurring geometry, interface, or scientific motifs;
- figure density and whether users need to inspect fine details;
- tone: benchmark report, systems demo, scientific visualization, productized dataset, or method paper.

Use that inventory to justify the page substrate. If the inventory does not support a grid, do not use one.

## Avoid Template Cloning

Use reference pages for interaction mechanics, not surface style. Change at least:

- Background system.
- Section composition.
- Figure hierarchy.
- Color palette.
- Table treatment.
- Hero layout.

Treat the following as clone indicators that require revision:

- the same grid/background texture used for unrelated papers;
- the same card-heavy rhythm when the target paper is table- or figure-led;
- color accents not found in, or naturally derived from, the paper figures;
- a hero that copies another page's composition instead of foregrounding this paper's strongest figure or result.
- a generic split hero with oversized title text on the left and a right-side paper figure/card, unless the target paper's own evidence hierarchy specifically calls for that composition.

## Background Coherence

Keep section transitions natural:

- Prefer one shared page substrate with subtle section tinting.
- Avoid abrupt full dark sections beside bright sections unless repeated consistently.
- Use thin separators, soft gradients, figure-derived washes, plain neutral surfaces, or grid density changes only when they match the paper.
- Hero and footer should feel related to the rest of the page.

Background options are choices, not defaults:

- Plain neutral surface for dense benchmark/result pages.
- Figure-derived color wash for visual generation or multimodal papers with strong image palettes.
- Coordinate/grid substrate only for papers where construction, coordinates, GUI canvases, or figure motifs make it semantically useful.
- Dark canvas only when the paper's media or application benefits from inspection against a dark surface.

## Layout

- Put the actual project content above the fold: title, claim, links, headline metrics, and a key figure.
- The items above are a content checklist, not a required hero composition. Do not default to a large text column plus a right-side image card. Before implementing the hero, choose a paper-specific strategy: thesis-first, figure-led, benchmark-dashboard, system-workflow, or brand-led.
- If the strongest visual is a pipeline, benchmark table, case-study sequence, or diagnostic plot, it often works better as the first full-width evidence module below a concise hero rather than as a small right-side card.
- Use full-width figures when details matter.
- Preserve each paper figure's intrinsic aspect ratio in the page layout. Do not force unrelated figures into equal-height or equal-aspect-ratio cards just to align a grid; that creates large empty bands around wide/tall diagrams and makes the figure look broken.
- Avoid `object-fit: contain` inside fixed-height figure cards except in zoom modals or intentionally bounded thumbnails. Prefer `img { width: 100%; height: auto; }`, group figures with similar aspect ratios, or let masonry/stacked sections keep natural heights.
- When a repeated figure set has mixed ratios, use text-only summary cards plus one selected figure, or split wide pipeline/heatmap figures from tall case-study figures instead of putting all of them in one uniform tile system.
- When placing two or more figures in the same row, compare their aspect ratios first. If the widest ratio divided by the narrowest ratio is above roughly 1.25, use a stacked layout, a main-figure-plus-notes composition, or an intentionally cropped thumbnail treatment for non-critical images. Do not rely on equal boxes to fix alignment.
- Use cards for repeated items, not for every page band.
- Keep dense operational/benchmark pages compact and scannable.
- Ensure long tables remain statically readable on mobile and desktop; do not rely on horizontal scrolling or clipping. Split/group columns or use multiple full sub-tables when a single table is too wide.
- Size tables by density: two- or three-column tables should use a `compact`/`narrow` treatment with a capped column width, while central result tables with many columns should use full-width static modules, grouped columns, or multiple complete sub-tables.
- Size 4-6 column explanatory tables by header length and text density rather than a global compact max-width. If short headers such as `Active stages` or `Family` wrap awkwardly, allocate full module width and add explicit `colgroup` widths.
- Center short categorical/ordinal columns (`Family`, `Active stages`, `Tier`, `Rank`, `Best config.`, compact stage/objective codes) while keeping long mechanism, explanation, and caption-like columns left-aligned.
- Do not leave a narrow table isolated inside a full-width band with a large empty area to its right. Pair it with a related figure, metric cards, explanatory notes, or place it in a visibly constrained column so the unused space reads as layout, not an accident.

## Validation Checklist

- All local images, PDFs, and linked assets exist.
- Figures are web formats and have stable filenames.
- Main result and dataset statistic tables are present in full when central.
- Figure containers follow the actual figure ratio; no large empty areas are introduced by fixed dimensions, equal-height grids, or mismatched `object-fit: contain` usage.
- Figures shown side-by-side have compatible ratios, or the layout uses explanatory text/table content to balance the row rather than forcing image boxes to match.
- Low-column-count tables are not stretched across the full page unless the surrounding text or figure composition justifies it.
- Table headers do not wrap awkwardly when the header is short and semantically atomic.
- Narrow tables are paired or constrained; they should not create a large blank region on the right side of the section.
- Citation contains only citation content. Project-resource buttons are not duplicated there when the hero/header already includes them.
- Institution/lab logos appear in a compact footer/partners strip, not inside Citation cards.
- The background and palette can be traced to the target paper, not to a prior generated page.
- Mobile navigation works.
- Text does not overlap figures/cards/buttons.
- Page still works without access to the original paper source directory.

## CSS Variable Naming

CSS custom properties for colors must use semantic names (`--primary`,
`--accent`, `--surface`, `--muted`) rather than hue-literal names (`--green`,
`--blue`, `--red`). Hue-literal names rot the moment the palette shifts — as
seen when a page uses `--green: #4060a0` where the actual color is blue.

Rules:
- Derive variable names from function (primary, accent, surface, border,
  muted, text-secondary) rather than from apparent color family.
- When using Tailwind utilities, keep the custom-property layer semantic
  even if Tailwind class names use color families (`bg-blue-600` is fine;
  `--green: #4060a0` is not).
- The drift check (`check_design_drift.py --html ...`) flags variable names
  that contradict their computed hue (e.g., `--green` whose H is in the
  blue range 180–260°). Treat any such flag as a blocker.

## Theme Color Propagation

After defining CSS custom properties, all theme-significant colors must
reference those variables rather than hardcoded hex values:

- Table headers, group rows, card backgrounds, tag backgrounds, borders,
  and footer accents must use `var(--primary)`, `var(--surface)`, etc.
- Inline hex colors that don't fall within ΔE ≈ 20 of any declared CSS
  variable are flagged by the drift check as `hardcoded_color_drift`.
- The generation step must do a final grep for orphan hex colors outside
  `:root` and replace them with the appropriate variable reference.

## Footer and Logo Strip

- Logo strips in the footer must use uniform `height` (recommend 48px) with
  `object-fit: contain` so logos of wildly different native sizes render at
  the same visual weight.
- Footer links use the same muted color system as navigation secondary items.
- Do not let logos inherit their natural (often wildly different) heights.
- Do not place institution or partner logos inside Citation. Citation and
  footer/partners are separate modules.

## Citation

- Citation modules should be small and predictable: heading, BibTeX/code block,
  optional copy button, and at most one short muted note about pending citation
  fields or verified license.
- Do not display internal `% NOTE:` extraction comments in the user-facing
  BibTeX block.
- Do not use warning banners for missing venue/year; they make the page look
  broken. Use a small inline hint when needed.
- Do not invent license text. Only show license text when verified from a
  LICENSE file, paper source, or user-provided link.
- Do not repeat Code/Dataset/Project buttons already shown in the hero/header.

## Measurable Criteria

The subjective rules above are easier to keep honest when paired with hard
checks. Where applicable, run:

- Figure budget: 5–9 high-signal figures on the page (count `<img>` plus
  `<figure>` minus icons under 64×64). More than 12 likely means appendix
  bleed; fewer than 4 likely means key evidence is missing.
- Figure layout fit: paper figures should normally render with natural height
  (`width: 100%; height: auto`). Fixed `height`, fixed `aspect-ratio`, or
  `object-fit: contain` on non-modal figure/card images is a warning unless
  the container's ratio matches that specific image. The drift script flags
  these patterns because they commonly cause large blank space in generated
  pages.
- Mixed-ratio figure rows: side-by-side figure groups should keep max/min
  aspect-ratio <= 1.25 unless the layout explicitly treats one item as a
  thumbnail or pairs the figure with non-image explanation.
- Narrow table fit: tables with <= 3 columns should usually carry a compact or
  narrow wrapper/class so they are not stretched to full page width.
- Palette overlap: at least 50% of the page's top-8 non-neutral colors
  should be within ΔE ≈ 64 of the figures' top-5 non-neutral colors. Run
  `scripts/check_design_drift.py --html <index.html> --manifest <figures>`
  to compute the overlap and list missing accents.
- Background coherence: no more than one "dark canvas" section unless the
  page deliberately commits to a dark system; consecutive section
  background luminance should not jump by more than 0.5 unless the
  contrast itself carries meaning.
- Texture support: grids, dot fields, "paper" textures, or notebook lines
  must be traceable to a figure motif. The drift script flags any of
  `linear-gradient(...)+url(grid|dots|paper|notebook|noise)` as a
  candidate clone indicator.
- Contrast: body text should clear WCAG AA (4.5:1) against its actual
  background; headings clear AA Large (3:1). Eyeballing is not enough on
  tinted hero backgrounds.
- Class overlap with prior generated pages: when a sibling
  `reports/<other>/index.html` exists, the page's class-token bag should
  overlap less than 70% with any one of them. Above that threshold the
  new page is most likely cloning the prior one.

- Grid density: grids with more than 4 columns must include a media query
  at max-width ≤ 960px that reduces to at most 3 columns. Any grid item
  narrower than 180px at viewports in the 360-1440px range is a layout
  defect. The drift check flags grid rules missing responsive breakpoints.
- Paired-figure alignment: primary paper figures should preserve natural image
  height. Pair figures only when their aspect ratios are compatible; otherwise
  stack them or use a main-figure-plus-notes composition. `object-fit: contain`
  is appropriate for logos, icons, thumbnails, and bounded non-primary media,
  not for core paper figures used as evidence.
- CSS variable naming: variable names containing a color-word (green, blue,
  red, orange, purple, yellow, teal, cyan, pink) where the actual hue
  contradicts the name are flagged as `variable_name_hue_mismatch`.
- Hardcoded color orphans: hex colors in CSS rules outside `:root` that
  don't match any declared custom property within ΔE ≈ 20 are flagged as
  `hardcoded_color_drift`.

When a check cannot be run (e.g., manifest unavailable), record the skip
in the validation summary instead of treating a missing check as a pass.
