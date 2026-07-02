## Pattern: `doc_classifier` — user-facing vs internal-only decision criteria

### When to use

Every ticket that reaches the `documenting` stage must be classified as either `user-facing` (triggers full doc agent) or `internal-only` (skips doc agent). The classification determines whether user-facing documentation (tutorials, reference docs, mkdocs nav) needs updating.

### Decision criteria

#### `internal-only` — skip doc agent

Classify as internal-only when the change:
- Is test-only (no production code touched)
- Fixes a docstring, comment, or stale count in existing docs
- Modifies lint/ruff/pre-commit configuration
- Is an internal refactor (no behavior change)
- Modifies CI workflows (GitHub Actions, Dependabot)
- Classifies documentation in `docs/modules.yaml`
- Adds a periodic workflow presence file in `.robotsix-mill/periodic/`
- Suppresses a lint rule for an intentional pattern
- Fixes a CI config parse error
- Is a dependency pin bump with no API change

#### `user-facing` — run full doc agent

Classify as user-facing when the change:
- Adds, removes, or changes a public API signature
- Changes behavior visible to users (error messages, output format)
- Adds a new feature or capability
- Adds new configuration options (`BaseSettings` fields)
- Enables new lint rule families that produce user-visible output (`ruff check`)
- Changes the agent-comm protocol or message format
- Modifies `mkdocs.yml` navigation
- Adds/removes reference documentation pages

### Template

```
doc_classifier: [user-facing|internal-only] — [one-line justification citing the specific nature of the change]
```

### Concrete examples from this repo

**Internal-only examples:**
> doc_classifier: internal-only — stale count in test docstring fix — no user-facing changes; skipping doc agent

> doc_classifier: internal-only — YAML change: assigning unclaimed tutorial to module's doc_paths — no user-facing changes; skipping doc agent

> doc_classifier: internal-only — suppress lint rule (T201) for healthcheck.py; no behavioral or user-visible change — no user-facing changes; skipping doc agent

> doc_classifier: internal-only — new periodic workflow file for changelog autofill, no user-facing change — no user-facing changes; skipping doc agent

> doc_classifier: internal-only — CI config fix removing invalid dependabot key — no user-facing changes; skipping doc agent

**User-facing examples:**
> doc_classifier: user-facing — enabled new Ruff rule families T10 and EXE, which will cause new lint violations to appear on user-visible output (ruff check); user may need to update code to comply — running full doc agent

> doc_classifier: user-facing — migrated ConfigContractError to canonical implementation, updated dependency pin and re-exports — running full doc agent

### Edge cases

- **"Recommendation-only doc deliverable"**: When the doc agent runs but decides no edits are needed, it reports `doc agent: recommendation-only doc deliverable (user_facing=True but no edits applied)`.
- **Mixed changes**: When a PR has both user-facing and internal-only changes, classify as user-facing and let the doc agent decide what to document.

### Quick reference table

| Change | Classification |
|---|---|
| Test addition/fix | internal-only |
| Docstring typo fix | internal-only |
| Lint rule config change | internal-only (unless new rules produce user-visible output) |
| CI workflow add/fix | internal-only |
| docs/modules.yaml classification | internal-only |
| Periodic presence file | internal-only |
| Public API change | user-facing |
| New feature | user-facing |
| Behavior change | user-facing |
| New config option | user-facing |
| New lint rules (T10, EXE, etc.) | user-facing |
| Reference doc page add/remove | user-facing |
