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

## Review follow-up — actioned

- **MEDIUM-2 — reconcile-from-capture operator surface. RESOLVED.**
  `aeat app modelo reconcile` now accepts `--from-capture <snapshot-id>`, which
  resolves the persisted live capture and runs the unchanged local
  `modelo_reconcile` against it. This realises the ADR's "the existing local
  reconcile runs against the persisted artefact" on the local verb, and is
  reconciled with the ADR wording: `--from-capture` is local-only (reads the
  already-persisted artefact, no AEAT contact), explicitly distinct from the
  ADR-rejected live `--from-sede` flag. Landed in the follow-up commit
  `58f177d83`; CLI tests prove MATCHES against a persisted capture and the
  mutual-exclusivity refusal. The ADR Implementation section was updated to name
  `--from-capture` and the best-effort in-flow stamp so the decision record and
  the code agree.
