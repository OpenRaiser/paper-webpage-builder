# paper-webpage-builder 0.4.0 SIT Report

Date: 2026-05-16

## Package

- Name: `paper-webpage-builder`
- Version: `0.4.0`
- Root: `/tmp/sit-ref-5k01_r1z/new`
- Manifest: `/tmp/sit-ref-5k01_r1z/new/skill.yaml`
- Description: Build polished single-page academic project webpages from paper sources, figures, references, and validation scripts.

## Validation

- Result: pass
- `OK  name: paper-webpage-builder`
- `OK  version: 0.4.0`
- `OK  manifest exists: /tmp/sit-ref-5k01_r1z/new/skill.yaml`
- `OK  prompt.skill exists: /tmp/sit-ref-5k01_r1z/new/SKILL.md`
- `OK  prompt.module_patterns exists: /tmp/sit-ref-5k01_r1z/new/references/module_patterns.md`
- `OK  prompt.design_principles exists: /tmp/sit-ref-5k01_r1z/new/references/design_principles.md`
- `OK  schema.input exists: /tmp/sit-ref-5k01_r1z/new/schemas/input.schema.json`
- `OK  schema.output exists: /tmp/sit-ref-5k01_r1z/new/schemas/output.schema.json`
- `OK  test.golden exists: /tmp/sit-ref-5k01_r1z/new/tests/golden.jsonl`
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

- Baseline: `paper-webpage-builder@0.3.0`
- Current: `paper-webpage-builder@0.4.0`
- `PACKAGE paper-webpage-builder@0.3.0 -> paper-webpage-builder@0.4.0`
- `MANIFEST changed version: '0.3.0' -> '0.4.0'`
- `PROMPT changed design_principles: design_principles.md -> design_principles.md`
- `PROMPT changed module_patterns: module_patterns.md -> module_patterns.md`
- `PROMPT changed skill: SKILL.md -> SKILL.md`
- `RISK review-required`

## Reproducibility

- Re-run validation with:
  `python3 -m sit.cli validate .`
- Re-run golden schema tests with:
  `python3 -m sit.cli test .`
- Re-run package diff with:
  `python3 -m sit.cli diff HEAD~1..HEAD`
