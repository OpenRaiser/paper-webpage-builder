## Skill Change Summary

- Baseline: `paper-webpage-builder@0.3.0`
- Current: `paper-webpage-builder@0.4.0`
- Validation: pass
- Golden tests: pass
- Risk: `review-required`
- Suggested version bump: `minor`

### Semantic Diff

- `PACKAGE paper-webpage-builder@0.3.0 -> paper-webpage-builder@0.4.0`
- `MANIFEST changed version: '0.3.0' -> '0.4.0'`
- `PROMPT changed design_principles: design_principles.md -> design_principles.md`
- `PROMPT changed module_patterns: module_patterns.md -> module_patterns.md`
- `PROMPT changed skill: SKILL.md -> SKILL.md`
- `RISK review-required`

### Reproduce

```bash
sit validate .
sit test .
sit diff HEAD~1..HEAD
```
