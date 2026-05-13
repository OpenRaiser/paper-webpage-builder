# paper-webpage-builder 0.1.0 SIT Report

Date: 2026-05-14

## Package

- Name: `paper-webpage-builder`
- Version: `0.1.0`
- Root: `/mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder`
- Manifest: `/mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder/skill.yaml`
- Description: Build polished single-page academic project webpages from paper sources, figures, references, and validation scripts.

## Validation

- Result: pass
- `OK  name: paper-webpage-builder`
- `OK  version: 0.1.0`
- `OK  manifest exists: /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder/skill.yaml`
- `OK  prompt.skill exists: /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder/SKILL.md`
- `OK  prompt.module_patterns exists: /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder/references/module_patterns.md`
- `OK  prompt.design_principles exists: /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder/references/design_principles.md`
- `OK  schema.input exists: /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder/schemas/input.schema.json`
- `OK  schema.output exists: /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder/schemas/output.schema.json`
- `OK  test.golden exists: /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder/tests/golden.jsonl`
- `OK  schema.input JSON schema valid`
- `OK  schema.output JSON schema valid`
- `OK  test.golden JSONL parsed: 2 cases`

## Golden Tests

- Result: pass
- `OK  latex-project-page: schema_only match passed`
- `OK  pdf-with-assets-page: schema_only match passed`
- `SUMMARY 2/2 golden cases passed`

## Reproducibility

- Re-run validation with:
  `python3 -m sit.cli validate /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder`
- Re-run golden schema tests with:
  `python3 -m sit.cli test /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder`
