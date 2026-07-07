## Pattern: `doc agent: recommendation-only doc deliverable` — when user-facing classification yields no edits

### When to use

Apply this template when:

1. The `doc_classifier` stage classified the change as **`user-facing`** (triggering the full doc agent run)
2. The doc agent ran but determined **no documentation edits are needed**
3. The deliverable note should record that this was an intentional no-op, not a missed step

This is an established edge case mentioned in `doc-classifier-boilerplate.md` ("Edge cases" section), but it lacked a dedicated template until now.

### Why this happens

The doc agent may decide no edits are needed when:

- The change exports a symbol that already has adequate docstrings (the auto-generated API reference suffices)
- The change is user-facing in principle (public API change) but the existing tutorials/examples already describe the usage pattern
- The change touches a module whose reference docs are already complete via mkdocstrings auto-generation

### Template

```
doc agent: recommendation-only doc deliverable (user_facing=True but no edits applied)
```

No further justification is needed — the parenthetical `(user_facing=True but no edits applied)` is the explanation.

### Concrete example from this repo

**Public API export with adequate existing docs** (ticket `20260706T185749Z` — export `handle_add_to_calendar`):

This ticket exported `handle_add_to_calendar` from the package namespace (added to `__init__.py` and `__all__`). The doc classifier correctly flagged this as user-facing:

> doc_classifier: user-facing — exporting handle_add_to_calendar as public API for external consumers — running full doc agent

The doc agent ran but found no documentation gaps — the function already had a complete docstring, and the auto-generated mkdocstrings reference was sufficient:

> doc agent: recommendation-only doc deliverable (user_facing=True but no edits applied)

### When this is NOT appropriate

Do NOT use this template when:

- The doc classifier classified the change as `internal-only` — in that case the doc agent is skipped entirely with `skipping doc agent`
- The doc agent actually made edits — use the standard deliverable note describing what was changed
- The change genuinely needs documentation but the doc agent missed it — that would be a gap, not a recommendation-only deliverable

### Decision flowchart

1. Did the doc classifier output `user-facing`? → If no, the doc agent was skipped — this template does not apply.
2. Did the doc agent produce any file edits? → If yes, use the standard deliverable note, not this template.
3. Did the doc agent run successfully but found no edits needed? → If yes, use `doc agent: recommendation-only doc deliverable (user_facing=True but no edits applied)`.

### Relationship to `doc-classifier-boilerplate.md`

This template fills the gap noted in `doc-classifier-boilerplate.md`'s "Edge cases" section, which described this pattern but provided no dedicated template, examples, or decision criteria. The parent boilerplate remains the authoritative source for the `user-facing` vs `internal-only` classification decision; this file covers what happens when the classification is `user-facing` but the doc agent's deliverable is a no-op.

<!-- triage_boilerplate-gap-id: doc-recommendation-only-boilerplate -->
<!-- triage_boilerplate-gap-id: doc-recommendation-only-boilerplate -->
