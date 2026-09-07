---
generated: true
tags:
  - '#index'
  - '#quality-gate-zero-closure'
date: '2026-08-24'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:0f732480481f84c93d05c03a121c90d8b75ae05e1ca67f518b7700b564794fa4'
related:
  - '[[2026-08-24-quality-gate-zero-closure-W08-P23-S108]]'
  - '[[2026-08-24-quality-gate-zero-closure-W08-P23-summary]]'
  - '[[2026-08-24-quality-gate-zero-closure-W08-P27-S104]]'
  - '[[2026-08-24-quality-gate-zero-closure-W08-P27-S105]]'
  - '[[2026-08-24-quality-gate-zero-closure-W08-P27-S106]]'
  - '[[2026-08-24-quality-gate-zero-closure-W08-P27-S107]]'
  - '[[2026-08-24-quality-gate-zero-closure-adr]]'
  - '[[2026-08-24-quality-gate-zero-closure-failure-cluster-topology-reference]]'
  - '[[2026-08-24-quality-gate-zero-closure-ledger]]'
  - '[[2026-08-24-quality-gate-zero-closure-live-rag-redeclaration-audit]]'
  - '[[2026-08-24-quality-gate-zero-closure-plan]]'
  - '[[2026-08-24-quality-gate-zero-closure-static-gate-matrix-research]]'
  - '[[2026-08-30-quality-gate-zero-closure-in-flight-plan-reconciliation-audit]]'
  - '[[2026-09-07-quality-gate-zero-closure-blind-green-gates-adr]]'
  - '[[2026-09-07-quality-gate-zero-closure-blind-green-implementation-review-audit]]'
  - '[[2026-09-07-quality-gate-zero-closure-blind-green-measurement-research]]'
  - '[[2026-09-07-quality-gate-zero-closure-bounded-mutmut-measurement-audit]]'
  - '[[2026-09-07-quality-gate-zero-closure-gate-consumer-parser-blindness-audit]]'
---

# `quality-gate-zero-closure` feature index

Auto-generated index of all documents tagged with `#quality-gate-zero-closure`.

## Documents

### adr

- `2026-08-24-quality-gate-zero-closure-adr` - `quality-gate-zero-closure` adr: `Perpetual rolling ratchet with revision-scoped exact-zero checkpoints` | (**status:** `accepted`)
- `2026-09-07-quality-gate-zero-closure-blind-green-gates-adr` - `quality-gate-zero-closure` adr: `Blind green is a gate failure, and most of it is mechanically detectable` | (**status:** `accepted`)

### audit

- `2026-08-24-quality-gate-zero-closure-live-rag-redeclaration-audit` - `quality-gate-zero-closure` audit: `live RAG redeclaration`
- `2026-08-30-quality-gate-zero-closure-in-flight-plan-reconciliation-audit` - `quality-gate-zero-closure` audit: `in flight plan reconciliation`
- `2026-09-07-quality-gate-zero-closure-blind-green-implementation-review-audit` - `quality-gate-zero-closure` audit: `Blind-green implementation review`
- `2026-09-07-quality-gate-zero-closure-bounded-mutmut-measurement-audit` - `quality-gate-zero-closure` audit: `Bounded mutmut measurement`
- `2026-09-07-quality-gate-zero-closure-gate-consumer-parser-blindness-audit` - `quality-gate-zero-closure` audit: `gate consumer parser blindness`

### exec

- `2026-08-24-quality-gate-zero-closure-ledger` - `quality-gate-zero-closure` ledger
- `2026-08-24-quality-gate-zero-closure-W08-P23-S108` - Correct the refuted boundary claim in all three places it lives: rewrite the scanner docstring to state which classes are decidable and which are not, and cross-link the audit finding and the closed tui-interface Step row to this decision rather than rewriting them, so the correction travels with the surfaces a future reader treats as durable (Luna max audit and mechanical)
- `2026-08-24-quality-gate-zero-closure-W08-P23-summary` - `quality-gate-zero-closure` `W08.P23` summary
- `2026-08-24-quality-gate-zero-closure-W08-P27-S104` - Install mutmut as a declared development dependency and pin it, adding no second mutation engine, and record the exact invocation so a run is reproducible outside CI (Terra xhigh fixes and refactors)
- `2026-08-24-quality-gate-zero-closure-W08-P27-S105` - Run mutmut against one bounded package and record wall clock, mutant count, killed and surviving counts, establishing this suite's real cost per package rather than an assumed one (Luna max audit and mechanical)
- `2026-08-24-quality-gate-zero-closure-W08-P27-S106` - Triage the surviving mutants into assertions that cannot fail versus mutants that are semantically inert, since an equivalent mutant is not a gate defect and treating it as one would manufacture work (Luna max audit)
- `2026-08-24-quality-gate-zero-closure-W08-P27-S107` - Declare the standing mutmut scope and cadence from the measured cost, naming which packages are in scope and how a run is triggered, verify-only and outside commit time (Sol architecture)

### plan

- `2026-08-24-quality-gate-zero-closure-plan` - `quality-gate-zero-closure` plan

### reference

- `2026-08-24-quality-gate-zero-closure-failure-cluster-topology-reference` - `quality-gate-zero-closure` reference: `Quality gate zero closure failure cluster topology`

### research

- `2026-08-24-quality-gate-zero-closure-static-gate-matrix-research` - `quality-gate-zero-closure` research: `Quality gate zero closure static-gate matrix`
- `2026-09-07-quality-gate-zero-closure-blind-green-measurement-research` - `quality-gate-zero-closure` research: `Measuring assertions that cannot fail`
