## Pattern: `auto-approve: APPROVE` — standardized justifications by source and change type

### When to use

Every draft ticket must carry an `auto-approve: APPROVE` or `auto-approve: REJECT` line with a justification. The justification signals to the reviewer the risk profile of the change and why it can skip human design review.

### Source-based templates

Use these for tickets filed by deterministic periodic agents — the rule engine has already vetted the proposal:

| Ticket source | Template |
|---|---|
| `agent_check` | `agent_check (deterministic rule: mill-internal periodic-agent proposal, no design risk)` |
| `audit` | `audit (deterministic rule: mill-internal periodic-agent proposal, no design risk)` |
| `module_curator` | `module_curator (deterministic rule: mill-internal periodic-agent proposal, no design risk)` |
| `security_posture` | `security_posture (deterministic rule: mill-internal periodic-agent proposal, no design risk)` |
| `bc_check` | `bc_check (deterministic rule: mill-internal periodic-agent proposal, no design risk)` |
| `completeness_check` | `completeness_check (deterministic rule: mill-internal periodic-agent proposal, no design risk)` |
| `state_sync` | `state_sync (deterministic rule: mill-internal periodic-agent proposal, no design risk)` |
| `test_gap` | `test_gap (deterministic rule: mill-internal periodic-agent proposal, no design risk)` |

**Note:** `survey` is not a deterministic periodic agent — survey tickets use change-type-based
justifications (see "Change-type-based templates" below), not the source-based template above.

### Change-type-based templates

Use these when the source is not a deterministic periodic agent, or to supplement the source-based template:

| Change type | Template |
|---|---|
| Doc-only | `This is a routine documentation update that adds [description] — no code, no security boundary, no destructive operation, no public-API change, and no new dependency.` |
| Test-only | `Test-only change — no production code, no behavioral changes, no security or destructive risk.` |
| Config-only (lint, ruff, pre-commit) | `Routine config fix adding [description] — no security, destructive, cross-repo, public API, or new runtime dependency concerns.` |
| Periodic presence file | `Adding a periodic [name] YAML file is a routine internal config addition — no code, no dependency, no destructive or cross-repo change, no public API breakage, and the content is a non-executable metadata file.` |
| Refactor (single-repo) | `This is a single-repo refactor that [description] — no security, destructive, public-API, infrastructure, or new-dependency concern is involved.` |
| CI workflow | `Adding a new [name] CI workflow is a routine [security/quality] tooling improvement that does not alter production code, external APIs, or runtime dependencies, and carries no destructive or cross-repo risk.` |

### Concrete examples from this repo

**agent_check source + mechanical fix** (ticket `20260702T200901Z`):
> auto-approve: APPROVE — agent_check (deterministic rule: mill-internal periodic-agent proposal, no design risk)

**user source + doc-only change** (ticket `20260702T133649Z`):
> auto-approve: APPROVE — This is a routine documentation update that adds a plain-text hyperlink to both README.md and AGENT.md — no code, no security boundary, no destructive operation, no public-API change, and no new dependency.

**meta source + periodic presence file** (ticket `20260702T110238Z`):
> auto-approve: APPROVE — The spec introduces an optional agent config file with no executable effect, no security or destructive impact, no cross-repo/infra changes, no public API break, and no new dependencies.

**review source + config-only** (ticket `20260701T205021Z`):
> auto-approve: APPROVE — Routine config fix adding a per-file lint ignore for a deliberately allowed pattern; no security, destructive, cross-repo, public API, or new runtime dependency concerns.

**security_posture source + CI workflow** (ticket `20260701T034453Z`):
> auto-approve: APPROVE — Adding a new OpenSSF Scorecard CI workflow is a routine security tooling improvement that does not alter production code, external APIs, or runtime dependencies, and carries no destructive or cross-repo risk.

### Decision criteria

APPROVE (skip human design review) when:
- Source is a deterministic periodic agent (agent_check, audit, module_curator, etc.)
- Change is purely mechanical with no design ambiguity
- Change has no security, destructive, cross-repo, public-API, or new-dependency risk

DO NOT auto-approve (route to human review) when:
- Change introduces a new dependency or external API call
- Change modifies authentication, authorization, or cryptographic code
- Change alters public API signatures
- Change has cross-repo implications
- Change is destructive (deletes data, removes features without deprecation)
