## Pattern: `maintenance triage` — CI failure routing and action verbs

### When to use

When a parent ticket's CI run fails with errors that are **out of scope** for that ticket — pre-existing failures, files the ticket didn't touch, infrastructure issues — the CI failure is spawned as a separate maintenance ticket. The maintenance triage agent routes it with an action verb.

### Template

```
maintenance triage: routed to MAINTENANCE (action=[action_verb]) — CI failure: [workflow name] on [branch]
```

### Known action verbs

| Action verb | When to use |
|---|---|
| `fork_repo` | The CI failure requires a code/config fix — fork the repo and create a PR |
| `noop` | The failure is transient (network blip, runner flake) and should be retried |
| `notify` | The failure requires human intervention (e.g., secrets rotation, org-level config) |

### Decision criteria

Route to MAINTENANCE with `action=fork_repo` when:
- The failure is reproducible and requires a code or config change
- The fix is well-understood and mechanical

Route with `action=noop` when:
- The failure appears transient (network timeout, runner disconnect)
- A retry would likely succeed

Route with `action=notify` when:
- The failure requires secrets or permissions the agent doesn't have
- The failure is in org-level configuration
- The failure pattern suggests a systemic issue needing human triage

### Concrete examples from this repo

**Scorecard CI failure** (ticket `20260701T035649Z`):
> maintenance triage: routed to MAINTENANCE (action=fork_repo) — CI failure: Scorecard on main

The maintenance agent then root-caused the failure (scorecard.yml had `security-events: write` at top-level permissions instead of job-level) and implemented the fix.

**Out-of-scope CI failure spawned from parent** (ticket `20260629T103944Z`):
> spawned by [parent_ticket_id]: CI failure is out of scope for this ticket

The ticket body explicitly declares: "All five failures target files this ticket did not modify — they are pre-existing repo debt on origin/main."

### Spawning from parent tickets

When a code review agent identifies CI failures that are out of scope:
1. The review agent approves the parent PR with a note: `approved; N out-of-scope ask(s) spawned as follow-ups`
2. One or more ci_fix tickets are spawned with `Source: ci_fix_dependency`
3. The spawned ticket's first history event links back: `spawned by [parent_id]: CI failure is out of scope for this ticket`

### Decision flowchart

1. Is the CI failure **out of scope** for the parent ticket? → If no, fix in the parent ticket directly.
2. Is the failure reproducible and requires a code/config change? → If yes, `action=fork_repo`.
3. Is the failure transient (network blip, runner flake)? → If yes, `action=noop`.
4. Does the failure require secrets, permissions, or org-level config? → If yes, `action=notify`.
5. Route the spawned ticket with `maintenance triage: routed to MAINTENANCE (action=[action_verb]) — CI failure: [workflow name] on [branch]`.
