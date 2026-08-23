---
tags:
  - '#audit'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:309314294256f9258868fa412563347f7f932b0c3c25f1638ab266ccc5360798'
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

Resolution (2026-08-23): Closed by commit `ed0cc8d9c4`.
`read_machine_secret_payload` now binds its generic to
`MachineSecretPayload` and performs a runtime `issubclass` refusal before
reading. The focused test stages a permissive payload on a descriptor, proves
the refusal, and then proves the bytes remain unread. The complete focused
machine-channel module passes 24 tests at remediation HEAD.

### selection-channel-runtime-validation | low | Exported selection accepts a non-enum channel at runtime

`MachineSecretSelection.__post_init__` checks descriptor consistency only for
the two enum members. Python does not enforce its annotation at runtime, so an
external construction with an arbitrary string and a descriptor survives, and
`read_machine_secret_payload` treats every non-stdin value as the descriptor
channel. The selector itself always constructs valid state, so this is not
reachable through the intended CLI path, but the exported typed boundary should
reject an unknown channel instead of broadening it implicitly.

Resolution (2026-08-23): Closed by commit `ed0cc8d9c4`.
`MachineSecretSelection.__post_init__` now refuses a channel that is not a
`MachineSecretChannel` before descriptor-consistency routing. The focused test
constructs an unknown runtime channel, proves the typed refusal, and proves the
staged descriptor bytes remain unread. The complete focused machine-channel
module passes 24 tests at remediation HEAD.

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

