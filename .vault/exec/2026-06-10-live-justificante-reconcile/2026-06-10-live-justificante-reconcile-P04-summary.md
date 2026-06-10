---
tags:
  - '#exec'
  - '#live-justificante-reconcile'
date: '2026-06-10'
related:
  - '[[2026-06-10-live-justificante-reconcile-plan]]'
---

# `live-justificante-reconcile` `P04` summary

Phase P04 (reconcile against the persisted artefact) is complete. Both Steps
landed with their gates green.

- Modified: `src/aeat/application/live/_justificante.py`
- Created: `src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py`

## Description

`reconcile_capture` (`S09`, commit `63f45b77e`) materialises a persisted
capture's PDF to a transient, auto-deleted `mkstemp` temp file (closed before the
path-only parser reopens it — Windows-safe) and delegates to the **unchanged**
local-only `modelo_reconcile` with `source_kind=JUSTIFICANTE`. The reconciler
gains no live branch; the live-sourced receipt simply replaces the operator's
hand-downloaded PDF. `parse_capture_to_justificante` runs the inbound parser over
the same materialisation to recover a domain `Justificante` (consumed by the P03
stamp). `S10` (commit `63f45b77e` tests) proves reconcile against a persisted
capture built from the real Modelo 130 justificante fixture yields `MATCHES`, a
303 work unit mismatches on modelo, and a malformed capture refuses with
`ReconciliationEvidenceInvalidError`.

The code review confirmed the materialisation is safe (temp file always deleted,
no caller-path privacy leak, parser path-redaction preserved) and the delegation
keeps the local reconciler unchanged.

## Deferred follow-up (formally deferred per campaign-close honesty)

- **MEDIUM-2 — reconcile-from-capture has no operator CLI surface yet.**
  `reconcile_capture` is a tested library seam, but the only operator verb today
  is `aeat app live justificante capture` (which pulls and persists). The local
  `aeat app modelo reconcile` still takes `--from-justificante PATH`, not a
  capture snapshot id. This matches the ADR's "reconciliation is a second step /
  a convenience may later chain" framing, and the headline operator value (the
  app pulling the receipt itself) is delivered by the capture verb. Wiring a
  `--from-capture <snapshot-id>` option (or a `justificante reconcile` verb) is a
  tracked follow-up increment.
