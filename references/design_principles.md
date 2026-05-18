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
- Use full-width figures when details matter.
- Preserve each paper figure's intrinsic aspect ratio in the page layout. Do not force unrelated figures into equal-height or equal-aspect-ratio cards just to align a grid; that creates large empty bands around wide/tall diagrams and makes the figure look broken.
- Avoid `object-fit: contain` inside fixed-height figure cards except in zoom modals or intentionally bounded thumbnails. Prefer `img { width: 100%; height: auto; }`, group figures with similar aspect ratios, or let masonry/stacked sections keep natural heights.
- When a repeated figure set has mixed ratios, use text-only summary cards plus one selected figure, or split wide pipeline/heatmap figures from tall case-study figures instead of putting all of them in one uniform tile system.
- When placing two or more figures in the same row, compare their aspect ratios first. If the widest ratio divided by the narrowest ratio is above roughly 1.25, use a stacked layout, a main-figure-plus-notes composition, or an intentionally cropped thumbnail treatment for non-critical images. Do not rely on equal boxes to fix alignment.
- Use cards for repeated items, not for every page band.
- Keep dense operational/benchmark pages compact and scannable.
- Ensure long tables scroll horizontally on mobile and do not compress text beyond readability.
- Size tables by density: two- or three-column tables should use a `compact`/`narrow` treatment with a capped column width, while central result tables with many columns should use full-width scroll containers.
- Do not leave a narrow table isolated inside a full-width band with a large empty area to its right. Pair it with a related figure, metric cards, explanatory notes, or place it in a visibly constrained column so the unused space reads as layout, not an accident.

## Validation Checklist

- All local images, PDFs, and linked assets exist.
- Figures are web formats and have stable filenames.
- Main result and dataset statistic tables are present in full when central.
- Figure containers follow the actual figure ratio; no large empty areas are introduced by fixed dimensions, equal-height grids, or mismatched `object-fit: contain` usage.
- Figures shown side-by-side have compatible ratios, or the layout uses explanatory text/table content to balance the row rather than forcing image boxes to match.
- Low-column-count tables are not stretched across the full page unless the surrounding text or figure composition justifies it.
- Narrow tables are paired or constrained; they should not create a large blank region on the right side of the section.
- The background and palette can be traced to the target paper, not to a prior generated page.
- Mobile navigation works.
- Text does not overlap figures/cards/buttons.
- Page still works without access to the original paper source directory.

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

When a check cannot be run (e.g., manifest unavailable), record the skip
in the validation summary instead of treating a missing check as a pass.
