## Skill Change Summary

- Baseline: `paper-webpage-builder@0.2.0`
- Current: `paper-webpage-builder@0.3.0`
- Validation: pass
- Golden tests: pass
- Risk: `review-required`
- Suggested version bump: `minor`

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
sit validate /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder
sit test /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder
sit diff /tmp/paper-webpage-builder-test/head /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder
```
