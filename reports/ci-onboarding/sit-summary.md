## SitHub CI Summary

- Package: `paper-webpage-builder@0.1.0`
- Validation: **pass**
- Golden tests: **pass**
- Golden summary: `SUMMARY 2/2 golden cases passed`

### Validation

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

### Golden Tests

- `OK  latex-project-page: schema_only match passed`
- `OK  pdf-with-assets-page: schema_only match passed`
- `SUMMARY 2/2 golden cases passed`

### Reproduce

```bash
python3 -m sit.cli validate /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder
python3 -m sit.cli test /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder
```
