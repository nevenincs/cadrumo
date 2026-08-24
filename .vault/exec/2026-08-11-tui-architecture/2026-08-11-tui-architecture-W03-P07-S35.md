---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:454612eaf222c82a625e5bc7b734e98196bfe3f4fcb5b328ea2f54686a47208c'
step_id: 'S35'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Expose dry-run on the composed filed-history operation with identical discovery scope and effect none

## Scope

- `src/cadrumo/application/live/_filed_history_operation.py`
- `src/cadrumo/application/live/_filed_data_capture.py`
- `src/cadrumo/application/live/tests/test_filed_history_composition.py`
- `src/cadrumo/application/live/tests/test_filed_history_operation_executor.py`

## Description

- Add the immutable `dry_run` request flag and forward it to the canonical filed-history composition.
- Preserve the regular discovery inputs and bulk-capture path while forwarding preview mode to the existing read-only capture authority.
- Withhold the existing artefact persistence sink before each preview capture and omit IVA-wallet and notification capture because they are separate persisted remote-state stages.
- Mark a completed preview with `OperationEffect.NONE`, without an interim `UNKNOWN` effect event or child sync-run provenance reference.
- Prove discovery-scope parity through the composed service and effect-none behavior through the real supervisor, journal, lease, encrypted operand, and sync-run adapters.

## Outcome

The registered filed-history operation now supports a read-only preview without introducing another discovery or capture writer. Normal execution retains its truthful pre-accounting `UNKNOWN` effect event. A preview uses the same discovered pair scope, invokes no persisted artefact, observation, calculation, sync-provenance, IVA-wallet, or notification write path, and records a truthful `NONE` effect.

## Notes

The plan row remains open at the coordinator's direction. Ordered progress and the broader filed-history conformance proof remain owned by later steps.
