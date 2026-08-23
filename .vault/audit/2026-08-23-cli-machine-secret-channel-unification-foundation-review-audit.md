---
tags:
  - '#audit'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:2f75ffa94bb54555c5a07fdbf25b64f737f91ca6b9d576daf03d626e9b0628be'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---



# `cli-machine-secret-channel-unification` audit: `canonical machine-secret foundation review`

## Scope

Reviewed commit `3da7874b13` against the accepted machine-secret ADR, its
research record, and `W01.P01.S01`. The review covered secret-free errors,
conflict-before-read ordering, descriptor 0 and reserved descriptors 1/2,
descriptor closure, reusable Typer declarations, strict frozen payload
enforcement, compatibility with unmigrated callers, and deferred deletion of
legacy helpers.

## Findings

### canonical-reader-model-bound | medium | Canonical reading does not enforce the canonical payload base

`read_machine_secret_payload` accepts any `BaseModel` subtype even though it is
the new canonical reader and the accepted contract requires command-local models
to inherit the shared strict frozen base. A future migrated command can therefore
pass a permissive Pydantic model and silently lose the canonical
unexpected-field and frozen-model guarantees while still appearing to use the
shared capability. The legacy `read_secrets_stdin` and `read_secrets_fd`
signatures may remain broad for unmigrated callers, but the new reader's generic
bound should require `MachineSecretPayload`; migration and inventory tests should
prove every registered payload inherits it.

### selection-channel-runtime-validation | low | Exported selection accepts a non-enum channel at runtime

`MachineSecretSelection.__post_init__` checks descriptor consistency only for
the two enum members. Python does not enforce its annotation at runtime, so an
external construction with an arbitrary string and a descriptor survives, and
`read_machine_secret_payload` treats every non-stdin value as the descriptor
channel. The selector itself always constructs valid state, so this is not
reachable through the intended CLI path, but the exported typed boundary should
reject an unknown channel instead of broadening it implicitly.

## Recommendations

- Bind the canonical reader's model parameter to `MachineSecretPayload` and add
  a type/runtime conformance test showing a permissive `BaseModel` is not a
  supported canonical payload.
- Make `MachineSecretSelection` reject any channel that is not a
  `MachineSecretChannel`, and test that invalid manual construction fails before
  a descriptor can be read.
- Retain the delegating conflict wrapper and the two legacy readers until the
  planned command migrations are complete; current exact-symbol evidence shows
  live unmigrated consumers, so deleting them in S01 would not be atomic.

