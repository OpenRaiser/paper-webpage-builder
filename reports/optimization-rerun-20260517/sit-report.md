# paper-webpage-builder 0.5.0 SIT Report

Date: 2026-05-18

## Package

- Name: `paper-webpage-builder`
- Version: `0.5.0`
- Root: `/mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder`
- Manifest: `/mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder/skill.yaml`
- Description: Build polished single-page academic project webpages from paper sources, figures, references, and validation scripts.

## Validation

- Result: pass
- `OK  name: paper-webpage-builder`
- `OK  version: 0.5.0`
- `OK  manifest exists: /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder/skill.yaml`
- `OK  prompt.skill exists: /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder/SKILL.md`
- `OK  prompt.module_patterns exists: /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder/references/module_patterns.md`
- `OK  prompt.design_principles exists: /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder/references/design_principles.md`
- `OK  schema.input exists: /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder/schemas/input.schema.json`
- `OK  schema.output exists: /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder/schemas/output.schema.json`
- `OK  test.golden exists: /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder/tests/golden.jsonl`
- `OK  schema.input JSON schema valid`
- `OK  schema.output JSON schema valid`
- `OK  test.golden JSONL parsed: 3 cases`
- `OK  command.run_case: configured`

## Golden Tests

- Result: pass
- `OK  latex-project-page: partial match passed`
- `OK  pdf-with-assets-page: partial match passed`
- `OK  existing-webpage-refresh: partial match passed`
- `SUMMARY 3/3 golden cases passed`

## Diff

- Baseline: `paper-webpage-builder@0.4.0`
- Current: `paper-webpage-builder@0.5.0`
- `PACKAGE paper-webpage-builder@0.4.0 -> paper-webpage-builder@0.5.0`
- `MANIFEST changed version: '0.4.0' -> '0.5.0'`
- `PROMPT changed skill: SKILL.md -> SKILL.md (+17 -8; headings: Paper Webpage Builder, Core Rule, Workflow)`
- `SCRIPT added scripts/convert_figures.py (review required; cover with runner or targeted tests)`
- `SCRIPT added scripts/extract_citation.py (review required; cover with runner or targeted tests)`
- `SCRIPT added scripts/extract_tables.py (review required; cover with runner or targeted tests)`
- `SCRIPT added scripts/scan_pdf.py (review required; cover with runner or targeted tests)`
- `SCRIPT changed scripts/convert_figures.sh (review required; cover with runner or targeted tests)`
- `SCRIPT changed scripts/scan_paper.py (review required; cover with runner or targeted tests)`
- `RISK review-required`

## Reproducibility

- Re-run validation with:
  `python3 -m sit.cli validate /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder`
- Re-run golden schema tests with:
  `python3 -m sit.cli test /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder`
- Re-run package diff with:
  `python3 -m sit.cli diff /tmp/paper-webpage-builder-head-20260517232243 /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder`
