## Skill Change Summary

Run locally before opening the PR:

```bash
sit validate
sit test
sit test --run
sit pr-summary origin/main..HEAD
```

## Checklist

- [ ] `sit validate` passes
- [ ] `sit test` passes
- [ ] `sit test --run` passes
- [ ] Generated webpage assets were link-checked when relevant
- [ ] Breaking schema or output-contract changes are explained
