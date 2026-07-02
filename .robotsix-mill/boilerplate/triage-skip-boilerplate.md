## Pattern: `triage SKIP` — implementation-ready draft fast-path

### When to use

Apply `triage SKIP` when a draft ticket already contains **all** of:
- At least one exact file path (verified present in the repo)
- A specific, mechanical change with **no design ambiguity**
- Single-scoped: the change is one coherent unit, not multiple unrelated modifications
- Clear acceptance criteria

### When NOT to use

Do NOT skip when:
- The draft is vague about which files to change
- There are design choices to make (multiple plausible approaches)
- The scope is unclear or multi-headed
- The draft references files or paths that don't exist in the repo
- The change requires exploration beyond what the spec provides

### Template

```
triage SKIP: Draft is [already implementation-ready / precise, single-scoped, and implementation-ready]: [citation of exact file paths, line numbers, and the mechanical nature of the change]. [Optional verification note: "Both cited files confirmed present and..." / "The target directory already exists with..."]. No refinement needed — route directly to implement.
```

### Concrete examples from this repo

**Mechanical docstring fix** (ticket `20260702T200901Z`):
> triage SKIP: Draft is already an implementation-ready spec: exact file path (tests/intent_parser/test_intent_parser.py), precise line (~138), and the exact mechanical change (8→10 in docstring). Verified the file and the stale docstring exist at the cited location — the parametrize list indeed has 10 cases while the docstring says 8. No refinement needed; route directly to implement.

**Config-only presence file** (ticket `20260702T110238Z`):
> triage SKIP: Draft is precise, single-scoped, implementation-ready, and grounded. It names an exact file path (.robotsix-mill/periodic/changelog_autofill.yaml), provides the exact YAML content, and the target directory already exists with 13 periodic workflows — only the changelog_autofill file is missing. This is a mechanical config-only change with no ambiguity.

**Documentation-only change** (ticket `20260702T133649Z`):
> triage SKIP: Documentation-only change with exact files (README.md, AGENT.md), specific content (one-line robotsix-standards link), and clear acceptance criteria. Both files confirmed present and neither already contains the link — the draft is implementation-ready.

**Module classification** (ticket `20260630T202002Z-855b`):
> triage SKIP: The draft is a precise, single-scoped, implementation-ready change: add one line to the doc_paths list under the existing module entry in docs/modules.yaml. Both cited files exist and the module entry is confirmed. This is a mechanical config-only documentation classification — no refinement needed.

### Decision flowchart

1. Does the draft name ≥1 exact file path? → If no, do NOT skip.
2. Is the change mechanical (no design choices)? → If no, do NOT skip.
3. Are the cited files/paths confirmed present? → If no, do NOT skip.
4. Is the scope single-headed? → If no, do NOT skip.
5. All yes → SKIP, route to implement.
