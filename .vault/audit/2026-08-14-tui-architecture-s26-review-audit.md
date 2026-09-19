---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-14'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:66cea74db08951e8006717c18ca5b10dfbbc650619d27a77dd3d66110f4ad982'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: `W02.P05.S26 startup reconciliation final review`

## Scope

Independent final review of `W02.P05.S26` against the accepted TUI architecture decision, architecture research, live plan row, S17-S25 execution evidence, canonical registry, journal, lease, executor, event, and supervisor contracts, and the complete current production and test diff. Semantic RAG was attempted but unavailable because its shared service could not start with the available CPU-only Torch installation. This audit makes no `S96` process-crash or process-reaping claim.

## Findings

### checkpoint-policy-binding | high | resolved before final review

The initial implementation admitted a structurally valid persisted checkpoint without proving that its interaction kind remained declared by the current operation definition. Remediation computes resume eligibility before lease takeover and requires the exact checkpoint kind to belong to `definition.interaction_kinds`. A real registry-drift proof changes the declared kind across restart, observes `INTERRUPTED` with `UNKNOWN` effect, and proves no resumable executor re-entry occurred.

### ephemeral-effect-compatibility | high | resolved before final review

The initial universal `UNKNOWN`-effect requirement made the accepted `EPHEMERAL` durability contract impossible because ephemeral capabilities permit only `NONE`. Remediation now requires `UNKNOWN` only for durable definitions exposed to owner-loss reconciliation, while an explicit registry proof preserves a valid ephemeral `NONE` definition.

### foreign-expired-attribution-proof | medium | resolved before final review

The initial suite lacked a durable proof for a target journal sharing its scope with a different expired operation lease. The added real filesystem and encrypted-operand test performs exact foreign predecessor takeover, records target `ORPHANED` followed by terminal `INTERRUPTED` with `UNKNOWN` effect, preserves the foreign journal byte-for-byte, and releases the acquired target scope.

No CRITICAL, HIGH, MEDIUM, or LOW finding remains open.

## Recommendations

Final verdict: PASS. The remediation preserves closed typed reconciliation outcomes and events, non-overlapping recovered, resumed, interrupted, and orphaned classifications, exact lease evidence, actual checkpoint re-entry through `OperationResumableExecutor`, fail-closed active and corrupt lease handling without journal mutation, and durable orphan classification followed by terminal interruption. Keep broader crash-and-restart and process-reaping acceptance under `W07.P16.S96`.

Final reviewed gates on the live tree: the complete supervisor integration module passed 39 tests; the direct registry module passed 14 tests; scoped Ruff check, Ruff format check, BasedPyright, and diff hygiene were clean. The final closeout `vault check all` exited 0 with 1,313 shared-corpus warnings, including stale feature-index drift. This review makes no broader readiness claim from those warnings.
