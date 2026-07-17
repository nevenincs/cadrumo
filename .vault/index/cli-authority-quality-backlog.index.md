---
generated: true
tags:
  - '#index'
  - '#cli-authority-quality-backlog'
date: '2026-07-17'
modified: '2026-07-17'
related:
  - '[[2026-07-17-cli-authority-quality-backlog-P01-S01]]'
  - '[[2026-07-17-cli-authority-quality-backlog-P01-S02]]'
  - '[[2026-07-17-cli-authority-quality-backlog-P01-S03]]'
  - '[[2026-07-17-cli-authority-quality-backlog-P02-S04]]'
  - '[[2026-07-17-cli-authority-quality-backlog-P02-S05]]'
  - '[[2026-07-17-cli-authority-quality-backlog-P08-S22]]'
  - '[[2026-07-17-cli-authority-quality-backlog-P09-S23]]'
  - '[[2026-07-17-cli-authority-quality-backlog-P09-S24]]'
  - '[[2026-07-17-cli-authority-quality-backlog-P11-S26]]'
  - '[[2026-07-17-cli-authority-quality-backlog-adr]]'
  - '[[2026-07-17-cli-authority-quality-backlog-plan]]'
---

# `cli-authority-quality-backlog` feature index

Auto-generated index of all documents tagged with `#cli-authority-quality-backlog`.

## Documents

### adr

- `2026-07-17-cli-authority-quality-backlog-adr` - `cli-authority-quality-backlog` adr: `cli-authority-quality-backlog rescope grounding` | (**status:** `accepted`)

### exec

- `2026-07-17-cli-authority-quality-backlog-P01-S01` - Make every accepted as_of argument participate in revision validity selection or reject it explicitly instead of silently ignoring it
- `2026-07-17-cli-authority-quality-backlog-P01-S02` - Reject an as_of argument on the unscoped registry discovery path with an instructive refusal naming the scoped form that honours it
- `2026-07-17-cli-authority-quality-backlog-P01-S03` - Prove historical as-of boundaries are honoured on the scoped path and refused explicitly on the unscoped path rather than silently ignored
- `2026-07-17-cli-authority-quality-backlog-P02-S04` - Add an AST recurrence gate that rejects new reducible production SHA-256 constructor and one-shot hexdigest bodies while allowing streaming, HMAC, HKDF, X509, and digest-byte uses
- `2026-07-17-cli-authority-quality-backlog-P02-S05` - Prove the recurrence gate rejects a new reducible one-shot body and accepts every legitimate cryptographic use it must not block
- `2026-07-17-cli-authority-quality-backlog-P08-S22` - Give the acceptance-wall meta-test a per-worker unique temp root via tmp_path_factory so concurrent pytest workers no longer share a PID-keyed directory and race
- `2026-07-17-cli-authority-quality-backlog-P09-S23` - Audit the roughly forty select_revision callers and prove every production calculation, verification, filing, export, and projection path resolves through the law-determined canonical resolver and only asserts a stored revision_id equal, never injects it
- `2026-07-17-cli-authority-quality-backlog-P09-S24` - Assert binding validator-dispatch completeness: every BindingSourceKind member has a dispatch entry in the validator registry or a documented mesh-only deferral, so a new source kind cannot ship unvalidated
- `2026-07-17-cli-authority-quality-backlog-P11-S26` - Add a structural no-build/no-publish assertion to the publish-workflow guardrail test: denylist-scan every step run and uses in the validate job (or pin the full step allowlist) so a differently-spelled build or publish command cannot slip past the exact-substring guards, gated on the guardrail test failing if any validate-job step invokes a build or publish tool

### plan

- `2026-07-17-cli-authority-quality-backlog-plan` - `cli-authority-quality-backlog` plan
