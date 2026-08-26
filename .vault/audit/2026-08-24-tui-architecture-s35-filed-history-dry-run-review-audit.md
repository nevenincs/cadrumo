---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:efc6da8389564b3eb4ccf5b05fdfa2f0b26af7dbfd3e375ebc197bbfbde9aafa'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: `S35 filed-history dry-run review`

## Scope

Independent review of `W03.P07.S35` against the accepted operation ADR, related research, plan row, implementation record, and the canonical filed-history composition. The review covered discovery parity, effect-event truthfulness, persisted writer suppression, provenance, normal-run preservation, and real-behavior test coverage.

## Findings

### preview-artefact-sink | high | Preview supplied a persisted artefact writer before the dry-run guard

`_absorb_declarations` originally passed `store.persist_artefact` into the register capture before `_CaptureAccumulator.absorb` could apply its dry-run return. A reached declaration could therefore persist financial artefacts while the operation reported `NONE`. The remediation passes no artefact sink for previews, retaining the existing store writer only for normal execution. The independent reviewer re-audited that change and marked the finding resolved.

## Recommendations

Keep preview writes guarded at their earliest capture boundary; a later accumulator or finalizer guard cannot protect an already-invoked artefact sink. The focused composition, byte-level write, and encrypted-supervisor tests cover the completed S35 scope. No open review findings remain.

## Independent closure review

The final implementation keeps one canonical filed-history composition. The
operation request forwards `dry_run` into `pull_filed_history`; both modes use
the same profile/today inputs, discovery port, discovered pair ordering, modelo
and year derivation, limit, register walk, declaration selection, capture parser,
and reconciliation reads. Preview changes only the effectful boundaries: it
withholds the artefact sink before capture, returns from the shared accumulator
before observation/evidence/calculation writes, selects the read-only bulk report
before finalization and `record_sync_run`, and omits the independently persisted
IVA-wallet and notification stages.

The supervisor executor publishes pre-accounting `UNKNOWN` only for normal
execution. Preview publishes no `UNKNOWN` effect event and settles its executor
phase with `NONE`; its typed result carries `dry_run=True` and no sync-run
reference. The default `dry_run=False` path retains the original artefact sink,
accumulator persistence, finalization, provenance, wallet, notification, and
truthful effect classification. No duplicate discovery, capture, writer, or
preview-only business orchestration was introduced.

The independent focused run passes four operation integration tests and six
composition/write unit tests. The byte-level encrypted-store proof shows a dry
accumulator pass leaves the warmed bucket database identical and its positive
normal-write control changes the same database. Ruff lint, Ruff format, focused
BasedPyright, and scoped diff integrity are clean. The reviewed tests use real
ports and production models/adapters and contain no mock, fake, patch, skip, or
xfail mechanism.

Close verdict: PASS. The earlier artefact-sink finding is resolved and no open
S35 finding remains.
