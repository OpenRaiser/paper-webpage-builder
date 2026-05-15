## SitHub CI Summary

- Package: `paper-webpage-builder@0.2.0`
- Validation: **pass**
- Golden tests: **pass**
- Golden summary: `SUMMARY 3/3 golden cases passed`

### Validation

- `OK  name: paper-webpage-builder`
- `OK  version: 0.2.0`
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

### Reproduce

```bash
python3 -m sit.cli validate /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder
python3 -m sit.cli test /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder
```
