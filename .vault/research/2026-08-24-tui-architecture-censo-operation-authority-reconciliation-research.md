---
tags:
  - '#research'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:36db38c2099d6dd9122d4a72e6c380038972a86cfb72387b7e1494b08547b09c'
related:
  - "[[2026-08-11-tui-architecture-research]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-07-25-censal-profile-autofill-adr]]"
  - "[[2026-08-08-sync-control-surface-adr]]"
---

# `tui-architecture` research: `Censo operation authority reconciliation`

The censo operation can reuse the accepted supervisor without choosing a new
merge policy, but only if its reviewed proposal is frozen before orchestration
and its apply continuation delegates to the existing cotejo writer. The plan
currently orders composition before those contracts. The evidence therefore
favors defining the secure proposal and exact-apply continuation first, then
composing the resumable executor around them.

## Findings

### The surviving merge and write authority already exists

The accepted autofill decision requires pulled facts to adopt only blank paths,
surface disagreements, and commit through `apply_cotejo`; live code follows
that shape through `reconcile_censal_read`, `apply_censal_read`, and
`apply_cotejo`. The operation needs no new merge algorithm or writer.
`.vault/adr/2026-07-25-censal-profile-autofill-adr.md:235`,
`src/cadrumo/application/user_profile/_censo_sync.py:267`,
`src/cadrumo/application/user_profile/_censo_sync.py:372`,
`src/cadrumo/application/user_profile/_cotejo_apply.py:249`.

### Exact approval requires a durable reviewed preimage

D9 requires one identity across acquisition, review, apply, and cleanup, no
effect before approval, stale-baseline refusal, and application of the exact
reviewed operand. Secure references, revision-bound interactions, and the
irreversible section can bind the proposal without putting censo policy in the
generic envelope. `.vault/adr/2026-08-11-tui-architecture-adr.md:397`,
`.vault/adr/2026-08-11-tui-architecture-adr.md:406`,
`src/cadrumo/application/operations/_interactions.py:92`,
`src/cadrumo/application/operations/_executor.py:38`.

### The supervisor lacks the post-acquisition checkpoint write and continuation contract

The executor context exposes secure operand resolution but no supervisor-owned
way to store a typed proposal produced after submission. `respond` consumes and
clears the checkpoint but does not schedule the executor, while restart resume
receives only an unconsumed pending interaction. The consumed record retains no
apply/reject intent or response reference. Therefore crash-safe continuation
after review cannot be implemented by the censo executor alone. The operation
platform must first atomically persist the typed proposal, journal only its
digest, record sufficient response continuation state, and schedule or recover
that continuation. `src/cadrumo/application/operations/_executor.py:99`,
`src/cadrumo/application/operations/_supervisor.py:442`,
`src/cadrumo/application/operations/_supervisor.py:672`,
`src/cadrumo/application/operations/_interactions.py:177`.

### The plan orders composition before its authority

`S29` composes the executor, while `S30` defines the encrypted reviewed
observation, baseline and proposal, and `S31` defines exact apply and stale
refusal. Building `S29` first either creates placeholders or embeds those
contracts in the executor. Moving `S30` and `S31` before `S29` corrects the
dependency without expanding scope.
`.vault/plan/2026-08-11-tui-architecture-plan.md:99`,
`.vault/plan/2026-08-11-tui-architecture-plan.md:100`,
`.vault/plan/2026-08-11-tui-architecture-plan.md:101`.

### Resume must consume the reviewed checkpoint, not repeat acquisition

Re-running the remote read after approval can produce a proposal different
from the one reviewed. Resume should consume the persisted interaction and
secure operand; a changed local baseline returns to review or refuses without
effect. An in-memory proposal was rejected because detach loses it. Putting
the authority response in the safe journal was rejected because the persisted
snapshot is credential-free. `.vault/adr/2026-08-11-tui-architecture-adr.md:227`,
`.vault/adr/2026-08-11-tui-architecture-adr.md:255`,
`src/cadrumo/application/operations/_supervisor.py:731`.

### Generic sync policy does not displace censo consent

The sync-control ADR rejects preview-by-default for mirrors and observation
caches, but names cotejo as the case where review protects a competing human
declaration. Censo autofill remains that case; explicit review is retained
rather than generalized. `.vault/adr/2026-08-08-sync-control-surface-adr.md:49`,
`.vault/adr/2026-08-08-sync-control-surface-adr.md:70`.

## Sources

- `.vault/adr/2026-07-25-censal-profile-autofill-adr.md:235`
- `.vault/adr/2026-08-08-sync-control-surface-adr.md:49`
- `.vault/adr/2026-08-08-sync-control-surface-adr.md:70`
- `.vault/adr/2026-08-11-tui-architecture-adr.md:227`
- `.vault/adr/2026-08-11-tui-architecture-adr.md:255`
- `.vault/adr/2026-08-11-tui-architecture-adr.md:397`
- `.vault/adr/2026-08-11-tui-architecture-adr.md:406`
- `.vault/plan/2026-08-11-tui-architecture-plan.md:99`
- `.vault/plan/2026-08-11-tui-architecture-plan.md:100`
- `.vault/plan/2026-08-11-tui-architecture-plan.md:101`
- `src/cadrumo/application/operations/_executor.py:38`
- `src/cadrumo/application/operations/_executor.py:99`
- `src/cadrumo/application/operations/_interactions.py:92`
- `src/cadrumo/application/operations/_interactions.py:177`
- `src/cadrumo/application/operations/_supervisor.py:442`
- `src/cadrumo/application/operations/_supervisor.py:672`
- `src/cadrumo/application/operations/_supervisor.py:731`
- `src/cadrumo/application/user_profile/_censo_sync.py:267`
- `src/cadrumo/application/user_profile/_censo_sync.py:372`
- `src/cadrumo/application/user_profile/_cotejo_apply.py:249`
