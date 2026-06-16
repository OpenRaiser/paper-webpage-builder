# Paper Reading Protocol

The most common failure of a generated page is **shallow content**: a hero
subtitle paraphrased from the abstract, invented section headings, and tables
shown as raw numbers with no explanation of what they prove. This happens when
the builder designs the page from the *skeleton* (`scan_paper.py`) without ever
reading the paper's *argument*.

This protocol is mandatory before any visual design. Read the paper, then
produce a **Paper Brief**, then derive all page copy from the Brief — never
straight from the abstract.

## Inputs to read first

Run and read **both**, not just the first:

- `scripts/scan_paper.py <paper.tex>` — skeleton: title, authors, captions,
  table/figure metadata, links.
- `scripts/extract_sections.py <paper.tex>` — the body prose of every section.
  This is where the actual argument lives. Read all of it. Use `--full` if a
  section is truncated and you need the rest.

If only a PDF exists, use `scripts/scan_pdf.py` and read the PDF text directly;
the same Brief is still required.

## Step 1 — Build the Paper Brief

Write the Brief explicitly (in working notes, not on the page) before designing.
It has eight parts:

1. **One-sentence thesis.** What does this paper claim is true that was not
   established before? State it as a claim, not a topic. (Topic: "a benchmark
   for layout repair." Claim: "compilation success is not publication
   readiness, and closing a visual feedback loop with acceptance gates fixes
   that.")
2. **Problem.** What concrete pain exists today, and why do existing approaches
   fail at it? Pull the specific failure modes the paper names, not a generic
   "this is hard."
3. **Core idea / name.** The named contribution (method, task formalization,
   benchmark) and the 1-line definition the paper gives it. Reuse the paper's
   own term of art (e.g. "Visual Typesetting Optimization (VTO)").
4. **How it works.** The method as 2–4 concrete stages, in the paper's own
   vocabulary. Capture what each stage actually does, not a label.
5. **Evidence map.** For every central table and figure: in one line, *what
   claim it supports*. A table is not "the main results" — it is "PaperFit
   reaches the highest page-budget hit rate, which is the gain over naive
   visual iteration." This line becomes the table's on-page framing.
6. **Headline numbers.** The 3–5 numbers that matter, each with the comparison
   that makes it meaningful. "80.5%" alone is noise; "80.5% page-budget hit vs.
   VisualMR's 54.9%" is a result.
7. **Honest limits.** What the paper says still fails. Pages that hide this read
   as marketing; pages that state it read as credible research.
8. **Audience & tone.** Who reads this (benchmark users, method researchers,
   tool adopters) and therefore what register the copy should take.

If you cannot fill a part from the extracted text, go back and read more — do
not fill it with a guess. A missing part is a signal to re-read, not to invent.

## Step 2 — Derive page copy from the Brief

Every piece of user-facing text must trace to a Brief entry:

| Page element        | Comes from                                   |
|---------------------|----------------------------------------------|
| Hero title          | Paper title (verbatim)                       |
| Hero subtitle       | Brief #1 thesis, rewritten for a reader      |
| TL;DR / abstract     | Brief #1–#3 condensed to 3–5 sentences       |
| Section headings    | Brief #2/#4/#5 as **claims**, not labels     |
| Method step cards   | Brief #4 stages                              |
| Result highlights   | Brief #6 headline numbers (with comparison)  |
| Table framing line  | Brief #5 evidence map entry for that table   |
| Limitations         | Brief #7                                     |

## Narrative rules (what made the bad page bad)

- **Headings are claims, not academic labels.** "The missing stage after
  structural formatting" is a label. "Compilation success is not publication
  readiness" is a claim. Prefer the claim.
- **Never write "The paper argues…", "The authors propose…", "This work
  presents…".** A project page speaks *for* the work in the present tense:
  "PaperFit closes the visual feedback loop." Third-person hedging reads like a
  review, not a project page.
- **No number without a comparison or unit of meaning.** Every headline metric
  needs the baseline or budget it is measured against.
- **No table without a one-line "why this matters" framing** above or beside it,
  taken from the evidence map. Raw tables with no framing are the single biggest
  symptom of a page built without reading.
- **Don't paraphrase the abstract into the hero and call it done.** The abstract
  is dense and hedged; the hero subtitle should be one sharp reader-facing
  sentence derived from the thesis.
- **Use the paper's own terms of art** consistently (the task name, method name,
  benchmark name, category labels). Do not rename them.
- **Match length to the medium.** Web readers skim. Compress multi-clause
  abstract sentences into short declarative ones. Cut hedging qualifiers that
  are appropriate in a paper but heavy on a landing page.

## Self-check before designing

- [ ] I read `extract_sections.py` output, not only `scan_paper.py`.
- [ ] The Brief's eight parts are all filled from the text, none invented.
- [ ] Every section heading is a claim traceable to the Brief.
- [ ] Every headline number carries its comparison.
- [ ] Every central table has a "why this matters" line from the evidence map.
- [ ] No "the paper argues / proposes / presents" phrasing remains.
- [ ] Limitations are present and honest.
