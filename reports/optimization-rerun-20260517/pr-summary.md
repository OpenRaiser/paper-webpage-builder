## Skill Change Summary

- Baseline: `paper-webpage-builder@0.4.0`
- Current: `paper-webpage-builder@0.5.0`
- Validation: pass
- Golden tests: pass
- Risk: `review-required`
- Suggested version bump: `minor`

### Semantic Diff

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

### Prompt/Reference Text Summary

- `PROMPT summary skill: +17 -8; headings: Paper Webpage Builder, Core Rule, Workflow, Output Expectations, Reference Files`

### Reproduce

```bash
sit validate /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder
sit test /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder
sit diff /tmp/paper-webpage-builder-head-20260517232243 /mnt/shared-storage-user/xuxinglong-p/paper-webpage-builder
```
