## SitHub CI Summary

- Package: `paper-webpage-builder@0.3.0`
- Validation: **pass**
- Golden tests: **pass**
- Golden summary: `SUMMARY 3/3 golden cases passed`
- Diff risk: **review-required**
- Suggested version bump: `minor`

### Validation

- `OK  name: paper-webpage-builder`
- `OK  version: 0.3.0`
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

### Golden Tests

- `OK  latex-project-page: partial match passed`
- `OK  pdf-with-assets-page: partial match passed`
- `OK  existing-webpage-refresh: partial match passed`
- `SUMMARY 3/3 golden cases passed`

### Semantic Diff

- `PACKAGE paper-webpage-builder@0.2.0 -> paper-webpage-builder@0.3.0`
- `MANIFEST changed version: '0.2.0' -> '0.3.0'`
- `PROMPT changed skill: SKILL.md -> SKILL.md`
- `SCHEMA changed output: output.schema.json -> output.schema.json`
- `SCHEMA output property added keywords (optional)`
- `TEST changed golden: golden.jsonl -> golden.jsonl`
- `GOLDEN expected changed existing-webpage-refresh`
- `GOLDEN expected changed latex-project-page`
- `GOLDEN expected changed pdf-with-assets-page`
- `RISK review-required`

### Reproduce

```bash
python3 -m sit.cli validate /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder
python3 -m sit.cli test /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder
python3 -m sit.cli diff /tmp/paper-webpage-builder-test/head /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder
```
