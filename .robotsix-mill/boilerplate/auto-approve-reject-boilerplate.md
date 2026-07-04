## Pattern: `auto-approve: REJECT` — rejection justifications and routing

### When to use

Apply `auto-approve: REJECT` when a draft ticket introduces **one or more risks** that disqualify it from automatic approval. Every draft ticket must carry an `auto-approve: APPROVE` or `auto-approve: REJECT` line with a justification — this template covers the REJECT path.

### Decision criteria — REJECT (route to human review)

REJECT when the change:
- **Introduces a new dependency or external API call** — any new third-party package, library, or external service integration
- **Modifies authentication, authorization, or cryptographic code** — any change to login flows, permission checks, token handling, or crypto primitives
- **Alters public API signatures** — any change to a function/class/method that is part of the public interface (re-exports, `__all__`, documented endpoints)
- **Has cross-repo implications** — changes that affect other repositories, shared schemas, or inter-service contracts
- **Is destructive** — deletes data, removes features without a deprecation path, drops backward compatibility
- **Introduces a new runtime binary dependency** — e.g., requiring a system package, database driver, or compiled extension
- **Changes agent-comm protocol or message format** — any modification to the wire format or handshake
- **Modifies CI/CD pipeline security** — changes to secret handling, deployment triggers, or protected branch rules

### When REJECT is NOT appropriate

Do NOT reject when the change is purely mechanical and carries none of the above risks. In those cases, use `auto-approve: APPROVE` with the appropriate source-based or change-type-based template from `auto-approve-boilerplate.md`.

### Template

```
auto-approve: REJECT — [specific risk category from criteria above]: [one-line description of the concern]. Route to human review.
```

If multiple risk categories apply, list the most severe one in the one-liner and enumerate the rest in the ticket body or a follow-up comment:

```
auto-approve: REJECT — public API change: [description]. Also introduces new dependency [name] and has cross-repo implications. Route to human review.
```

### Concrete examples (hypothetical — populate with real examples as they occur)

**New dependency:**
> auto-approve: REJECT — new dependency: adds `httpx` as a runtime dependency for outbound HTTP calls. Introduces supply-chain risk and a new external API surface. Route to human review.

**Public API change:**
> auto-approve: REJECT — public API change: renames `CalendarAgent.process()` to `CalendarAgent.handle()`, breaking all callers. Requires deprecation path or migration guide. Route to human review.

**Auth/crypto change:**
> auto-approve: REJECT — auth modification: changes token validation logic in `caldav_client.py`. Security-sensitive code path — requires human security review. Route to human review.

**Cross-repo impact:**
> auto-approve: REJECT — cross-repo implications: changes the agent-comm message schema, affecting all downstream agents that parse the response. Requires coordination with affected repos. Route to human review.

**Destructive change:**
> auto-approve: REJECT — destructive: removes `CalendarAgent.list_calendars()` without deprecation warning. Existing callers will break at runtime. Route to human review.

### Decision flowchart

1. Does the change introduce a new dependency or external API call? → If yes, REJECT.
2. Does the change modify auth, crypto, or security-sensitive code? → If yes, REJECT.
3. Does the change alter a public API signature? → If yes, REJECT.
4. Does the change have cross-repo implications? → If yes, REJECT.
5. Is the change destructive (data loss, no deprecation)? → If yes, REJECT.
6. Does the change introduce a new runtime binary dependency? → If yes, REJECT.
7. Does the change modify agent-comm protocol? → If yes, REJECT.
8. Does the change modify CI/CD pipeline security? → If yes, REJECT.
9. All no → APPROVE (use `auto-approve-boilerplate.md` templates).

### Relationship to `auto-approve-boilerplate.md`

This file is the companion to `auto-approve-boilerplate.md`. That file covers APPROVE justifications; this file covers REJECT justifications. The two together satisfy the requirement stated in `auto-approve-boilerplate.md` line 6: "Every draft ticket must carry an `auto-approve: APPROVE` or `auto-approve: REJECT` line with a justification."

### Source-based REJECT considerations

Even tickets from deterministic periodic agents (`agent_check`, `audit`, `module_curator`, `security_posture`, `survey`) can be REJECTED if the proposed change falls into one of the risk categories above. The source-based APPROVE justification ("deterministic rule: mill-internal periodic-agent proposal, no design risk") does NOT override the risk-based REJECT criteria. For example, if `security_posture` proposes adding a new external dependency, REJECT it despite the deterministic source.

<!-- triage_boilerplate-gap-id: auto-approve-reject-boilerplate -->
