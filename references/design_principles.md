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
- Use cards for repeated items, not for every page band.
- Keep dense operational/benchmark pages compact and scannable.
- Ensure long tables scroll horizontally on mobile and do not compress text beyond readability.

## Validation Checklist

- All local images, PDFs, and linked assets exist.
- Figures are web formats and have stable filenames.
- Main result and dataset statistic tables are present in full when central.
- The background and palette can be traced to the target paper, not to a prior generated page.
- Mobile navigation works.
- Text does not overlap figures/cards/buttons.
- Page still works without access to the original paper source directory.
