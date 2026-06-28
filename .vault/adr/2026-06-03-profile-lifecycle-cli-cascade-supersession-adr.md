---
tags:
  - '#adr'
  - '#profile-lifecycle-cli-cascade-supersession'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-16-profile-lifecycle-cli-plan]]'
  - '[[2026-05-19-profile-lifecycle-disaster-adr]]'
  - '[[2026-06-03-plan-triage-approach-adr]]'
  - '[[2026-06-04-profile-lifecycle-cli-cascade-supersession-research]]'
---

# `profile-lifecycle-cli-cascade-supersession` duplicate-date plan supersession ADR

## Context

Two plans share the `#profile-lifecycle-cli` feature tag:

- `2026-05-16-profile-lifecycle-cli-plan` (L2). P01 `typed identity
  primitives (DONE)` marker; P02 active-profile-pointer cutover and
  P03-onwards bucket-resolution wiring all checked. Tracks the
  long-running profile-axis hardening through the schema-axis tasks
  (#162 Beckham foundation, #191 axis hardening, #261
  representante_fiscal_nombre schema gap, #244 manifest
  lifecycle-status crash).

- `2026-05-18-profile-lifecycle-cli-plan` (L2). P01 crypto cutover
  + NIST passphrase floor; P02 engine cutover + WorkflowState
  retirement; P03 operator CLI tail (delete validate/preflight/get/
  set/unset; rename init → profile create NAME); P04 per-feature
  surface gate. Every Step is `[x]`.

Both plans nominally address the "profile lifecycle CLI" concept
but at different layers and on overlapping timelines. The 2026-05-18
plan was authored two days after the 2026-05-16 plan as a *cascade
closure* — its `cascade-closure-research` companion document treats
it as the broader cleanup that propagates the 05-16 primitives
through the storage, engine, and CLI surfaces. The disaster ADR
`2026-05-19-profile-lifecycle-disaster-adr` records the chaos that
followed when the cascade landed against an in-flight tree.

The plan-triage classification pass on 2026-06-03 surfaced the
05-18 plan as Bucket 3: every Step is checked, the disaster ADR
captures the after-action, the 05-16 sibling is the surface that
continues to absorb new profile-axis work, and there is no live
follow-up Step or task referencing the 05-18 plan by stem. Per
`2026-06-03-plan-triage-approach-adr`, this is the "stale-with-
implicit-supersession" shape that requires an explicit
supersession-ADR before archive rather than silent archival that
would lose the supersession direction and leave future agents
confused about which plan is the authoritative surface.

## Decision

`2026-05-18-profile-lifecycle-cli-plan` is **superseded by**
`2026-05-16-profile-lifecycle-cli-plan` as the canonical
profile-lifecycle-cli surface. The 05-18 plan is approved for
archive under this supersession-ADR.

The supersession direction is **reverse-chronological**: the
later-dated 05-18 plan is the *superseded* one, and the earlier-
dated 05-16 plan is the *surviving* one. This inversion reflects
the actual code state — the 05-18 cascade-closure Steps all landed
into the tree (their `[x]` marks are honest), but the durable
profile-axis surface that subsequent campaigns continue to extend
is the 05-16 plan, whose P01 typed identity primitives are the
foundation that every later schema-axis task builds on.

## What the 05-18 cascade carried that survives

The 05-18 plan's landed work is preserved in the codebase, not in
the plan body. Specifically:

- **P01 crypto cutover.** The `ContextVar`-backed `BucketSession`
  active-session model, `get_active_master_key()`, NIST
  passphrase floor, and ClassVar-cache elimination all shipped and
  are load-bearing for the
  `secure-storage-production-hardening-refactor-plan`. That
  campaign owns the ongoing hardening of this surface; the 05-18
  plan's body has no further Steps to contribute.

- **P02 engine cutover.** `Settings.aeat_database_url` as a
  computed property, per-bucket SQLite isolation, `WorkflowState.
  profiles` retirement, and manifest-scan bucket enumeration all
  shipped. The `secure-backend-passkey-bucket-plan` and the
  `cli-workflow-redesign-epic-plan` umbrella now own the live
  surface.

- **P03 operator CLI tail.** Deletion of `validate`/`preflight`/
  `get`/`set`/`unset`, the `init` → `profile create NAME` rename,
  the wizard `--profile` → positional `NAME` migration, and the
  five `aeat config profile edit` suggestion-string flips all
  shipped. The `cli-workflow-redesign-epic-plan` and the
  `cli-workflow-redesign-modelo-145-reopen-plan` continue to evolve
  the operator surface.

- **P04 per-feature surface gate.** The
  `feature-surface-gate.md` skill shipped and is the canonical
  authoring path for path-scoped CI scope; ongoing maintenance
  rides with the `codebase-solidification` epic.

## What's orthogonal in the 05-18 plan that doesn't carry forward

The 05-18 plan's scope at authoring time included the NIST
passphrase floor and the ClassVar-elimination crypto cutover — both
of which are now owned by the **secure-storage hardening campaign**
under its own ADR cluster, not by the profile-lifecycle surface.
That partial orthogonality is precisely why the 05-18 plan cannot
serve as the surviving profile-lifecycle plan even though it is
the more comprehensive of the two: half of its scope migrated to a
different feature tag.

The 05-16 plan stays narrowly on profile identity and active-
profile resolution — the surface that *remains* a profile-lifecycle
concern after the secure-storage and engine concerns are factored
out into their own campaigns. That narrower focus is what makes
05-16 the durable surviving plan.

## Why the 05-19 disaster ADR is the third document, not a third plan

The `2026-05-19-profile-lifecycle-disaster-adr` records the
operational chaos that followed the cascade closure landing. It is
an *audit-shaped ADR* — a backwards-looking record of what broke,
not a forward-looking decision — and so does not itself constitute
a successor plan. The lessons it records have been absorbed into
the standing `aeat-swarm-orchestration` and
`aeat-git-worktree-safety` rules; no Steps from it remain
unactioned.

## Consequences

- The `2026-05-18-profile-lifecycle-cli-plan` archives cleanly with
  a recorded supersession contract; no information is lost.
- Future agents looking for "the profile-lifecycle-cli plan" find
  `2026-05-16-profile-lifecycle-cli-plan` as the surviving
  authoritative surface.
- The 05-18 plan's archived body remains discoverable through the
  `related:` graph for historical context — the cascade-closure
  scope is preserved as evidence even though it does not need a
  live plan slot.
- The PM dispatches
  `vaultspec-core vault feature archive` against the **plan stem**,
  not against the broader `#profile-lifecycle-cli` feature tag —
  the 05-16 sibling shares the tag and must remain unarchived. The
  `vaultspec-archive-discipline.builtin.md` rule requires the
  incoming-references discovery pass before invocation; the
  `cascade-closure-research` companion document and the 05-19
  disaster ADR are both inbound references the operator must
  inspect.

## Status

Accepted. Archive of `2026-05-18-profile-lifecycle-cli-plan`
authorised on landing of this ADR. The 05-16 sibling and its
ongoing schema-axis follow-ups remain active.
