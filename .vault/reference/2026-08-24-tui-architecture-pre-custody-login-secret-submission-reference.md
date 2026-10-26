---
tags:
  - '#reference'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:329486f86bb4964dd7ef169d8381cfe3d43a3b4f369d86d7903d6620ef169138'
related:
  - "[[2026-08-11-tui-architecture-adr]]"
---

# `tui-architecture` reference: `pre custody login secret submission`

## Summary

The existing supervisor has one durable encrypted-operand path and cannot safely
register a profile login before the password opens custody. This reference fixes
the implementation boundary for an operation-owned transient secret channel:
the durable request is credential-free, the secret is exact-bound and consumed
only from process memory, and restart before that consumption is a terminal
interruption before any executor effect.

The concrete secure-reference adapter is intentionally unsuitable for a profile password. Before login neither condition exists. Reusing either path would be circular, would persist a secret, or would create a second unlock authority.

The registered executor must call that existing authority once after an operation-owned one-shot secret acquisition; it must not first call login outside the supervisor or persist a callback reference.

The new channel therefore needs an explicit pre-effect, non-resumable restart rule rather than silently inheriting created-operation recovery.

The accepted interface contract already demands an operation-owned public
`EphemeralSecretSubmission` capability with exact operation/interaction binding,
expiry, single use, duplicate and mismatch refusal, cancellation, cleanup, and
non-retention proof, but deliberately leaves its placement undecided
(`.vault/adr/2026-08-11-tui-interface-adr.md:176-199`,
`.vault/adr/2026-08-11-tui-interface-adr.md:435-453`). The operation ADR owns
the missing generic capability; frontends must neither embed callbacks in an
operation envelope nor gain a second lifecycle authority
(`.vault/adr/2026-08-11-tui-architecture-adr.md:132-221`).
