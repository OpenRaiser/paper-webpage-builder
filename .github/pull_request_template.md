## Skill Change Summary

Run locally before opening the PR:

```bash
sit validate
sit test
sit pr-summary origin/main..HEAD
```

## Checklist

- [ ] `sit validate` passes
- [ ] `sit test` passes
- [ ] Generated webpage assets were link-checked when relevant
- [ ] Breaking schema or output-contract changes are explained
