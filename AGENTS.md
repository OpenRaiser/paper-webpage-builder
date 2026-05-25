# paper-webpage-builder — Agent Instructions

This is a **sit-managed Skill Package**. The `sit` CLI provides semantic
versioning, validation, testing, and diff for prompts, schemas, and golden tests.

## When working in this package, always:

1. **Detect changed files**: after edits, inspect `git status --short`.
2. **Run checks for Skill changes**: if `skill.yaml`, `prompts/`, `schemas/`,
   `tests/`, `scripts/`, `assets/`, `references/`, or `deps.yaml` changed, run
   `sit validate` and `sit test`.
3. **Review semantic impact**: for uncommitted changes in a Git work tree, run
   `sit diff HEAD..WORKTREE`; for committed branches, run `sit diff main..HEAD`
   or the relevant range.
4. **Commit through sit**: use `sit commit` instead of `git commit` so validation,
   golden tests, dependency warnings, and version gates run before the commit.
5. **For PRs**: run `sit pr-summary` to generate a structured change summary.
6. **Read JSON output**: use `--format json` for machine-readable output.
   Schema definitions are at `docs/schemas/` in the sit repository.

## Codex workflow

Codex reads this `AGENTS.md` automatically when working in this directory. Treat
the rules above as the default loop: modify files, detect changes, run the
appropriate `sit` commands, and report validation/test/diff results before
finishing.

## Key commands

| Command | Purpose |
|---------|---------|
| `sit info` | Package metadata + git state |
| `sit validate` | Check manifest, paths, schemas |
| `sit test` | Run golden expected-vs-schema tests |
| `sit diff HEAD..WORKTREE` | Semantic diff of uncommitted working-tree changes |
| `sit diff main..HEAD` | Semantic diff of committed branch changes |
| `sit pr-summary` | Generate PR summary (Markdown or JSON) |
| `sit report` | Full validation report |
| `sit release` | Bump version and create release |

## JSON output contracts

- `sit info --format json` → `sit.info.v1`
- `sit pr-summary --format json` → `sit.pr_summary.v1`
- `sit test --format json` → `sit.test.v1`
- `sit report --format json` → `sit.report.v1`

## MCP integration

If your editor supports MCP (Model Context Protocol), the `.mcp.json` file
in this directory configures the `sit` MCP server automatically. Claude Code,
Cursor, and other MCP-aware editors can call sit tools directly via MCP without
shell commands. Codex should use this `AGENTS.md` workflow even when MCP is not
configured.

## Package structure

```
paper-webpage-builder/
  skill.yaml              # manifest: name, version, paths
  prompts/                # prompt files
  schemas/                # input & output JSON schemas
  tests/golden.jsonl      # deterministic test cases
  reports/                # generated reports
  .mcp.json               # MCP server config (auto-generated)
  AGENTS.md               # this file (auto-generated)
```
