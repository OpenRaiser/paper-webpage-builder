## SitHub CI Summary

- Package: `paper-webpage-builder@0.2.0`
- Validation: **pass**
- Golden tests: **pass**
- Golden summary: `SUMMARY 3/3 golden cases passed`
- Diff risk: **review-required**
- Suggested version bump: `minor`

### Validation

- `OK  name: paper-webpage-builder`
- `OK  version: 0.2.0`
- `OK  manifest exists: /tmp/sit-ref-t1e8x3hu/new/skill.yaml`
- `OK  prompt.skill exists: /tmp/sit-ref-t1e8x3hu/new/SKILL.md`
- `OK  prompt.module_patterns exists: /tmp/sit-ref-t1e8x3hu/new/references/module_patterns.md`
- `OK  prompt.design_principles exists: /tmp/sit-ref-t1e8x3hu/new/references/design_principles.md`
- `OK  schema.input exists: /tmp/sit-ref-t1e8x3hu/new/schemas/input.schema.json`
- `OK  schema.output exists: /tmp/sit-ref-t1e8x3hu/new/schemas/output.schema.json`
- `OK  test.golden exists: /tmp/sit-ref-t1e8x3hu/new/tests/golden.jsonl`
- `OK  schema.input JSON schema valid`
- `OK  schema.output JSON schema valid`
- `OK  test.golden JSONL parsed: 3 cases`

### Golden Tests

- `OK  latex-project-page: schema_only match passed`
- `OK  pdf-with-assets-page: schema_only match passed`
- `OK  existing-webpage-refresh: schema_only match passed`
- `SUMMARY 3/3 golden cases passed`

### Semantic Diff

- `PACKAGE paper-webpage-builder@0.1.0 -> paper-webpage-builder@0.2.0`
- `MANIFEST changed version: '0.1.0' -> '0.2.0'`
- `PROMPT changed skill: SKILL.md -> SKILL.md`
- `SCHEMA changed output: output.schema.json -> output.schema.json`
- `SCHEMA output property added quality_checks (optional)`
- `TEST changed golden: golden.jsonl -> golden.jsonl`
- `GOLDEN case added existing-webpage-refresh`
- `RISK review-required`

### Reproduce

```bash
python3 -m sit.cli validate .
python3 -m sit.cli test .
python3 -m sit.cli report . --compare main..HEAD
```
