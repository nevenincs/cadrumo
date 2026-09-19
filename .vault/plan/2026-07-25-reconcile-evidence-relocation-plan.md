---
tags:
  - '#plan'
  - '#reconcile-evidence-relocation'
date: '2026-07-25'
modified: '2026-07-26'
body_hash: 'sha256:5d5f6a780818f362c2354b75cdbdbe1256cc561144e11f83c32b227b9ac7e88e'
tier: L1
related:
  - '[[2026-07-25-reconcile-evidence-relocation-adr]]'
  - '[[2026-07-25-reconcile-evidence-relocation-research]]'
---

# `reconcile-evidence-relocation` plan

- [x] `S01` - Register the MODELO_RECONCILIATION_RECORDS secure-object namespace at AUDIT sensitivity and PROFILE_LOCAL scope and STRUCTURED_CUSTODY disposition, enrolling its durability floor and version and empty upgrader registry at birth as compatibility-lifecycle-checkpoint requires; `src/cadrumo/adapters/persistence/storage/_namespace_registry.py`.
- [x] `S02` - Design the object key to admit N reconciliations per work unit rather than overwriting, and to admit the runs that carry no persisted revision at all, since receipt-total and declaracion-casilla reconciles emit a no_persisted_revision advisory and still produce a report and identity-header reconcile needs no revision; `src/cadrumo/application/modelo/_reconcile.py`.
- [x] `S03` - Add the strict-frozen reconciliation record model carrying verdict and source kind and source reference and work unit id and the grounded diffs and advisories and instant and actor, reusing the existing strict-frozen diff and advisory models unchanged, with grounding stored rather than re-derived; `src/cadrumo/application/modelo/_reconcile.py`.
- [x] `S04` - Write the reconciliation record and the slimmed bucket event atomically through the existing co-emit write discipline, so a crash between them cannot desynchronise the event log from the detail store; `src/cadrumo/application/modelo/_reconcile.py`.
- [x] `S05` - Repoint list_modelo_reconciliations at the new store while keeping its return type so the CLI payload schema and the round-trip test are undisturbed, and delete diffs_detail from the payload rather than migrating it, leaving the event carrying verdict and count; `src/cadrumo/application/modelo/_reconcile.py, src/cadrumo/entrypoints/cli/_modelo_reconcile_cli.py`.
- [x] `S06` - Prove the new persisted format with a strict save-load-equality roundtrip populating every defaultable field to a non-default value, plus an anti-tautology proof that a mutated stored payload surfaces a refusal, using real adapters and a real master-key provider rather than doubles; `src/cadrumo/application/modelo/tests/`.
- [x] `S07` - Rewrite the ModeloReconciliationHistoryEntry docstring whose no-parallel-reconciliation-store sentence the new store makes false, and re-affirm the provenance-carried constraint of the superseded Decision 2.B at the new site; `src/cadrumo/application/modelo/_reconcile.py, .vault/adr/2026-07-01-reconcile-value-comparison-adr.md`.
- [x] `S08` - Rule whether the bucket-event substrate deserves a standing guard against joining a variable-length value into a capped payload slot, four instances found and three closed by hand, and give the un-ratified 500-character cap its first declared home; `src/cadrumo/domain/buckets/_event.py, new ADR`.
## Description

Executes option (e) of the accepted relocation decision. Modelo 100 reconciliation
cannot persist its own result: the per-divergence detail is serialised into one
capped payload value, and at a median encoded diff of 303 characters two
divergences are unpersistable for 99.6% of casillas while 175 overflow on the
first divergence alone. The write raises before anything is saved, so the operator
meets an unhandled validation error rather than a reconciliation.

The detail moves to a dedicated encrypted profile-scoped store, enrolling under
the shipped IVA-wallet reconciliation precedent, and the bucket event reduces to
verdict plus count. Grounding is stored rather than re-derived, so a routine
re-grounding sweep cannot silently rewrite the legal basis of a historical
reconciliation.

S01 through S07 are the decision. S08 is the last systemic item and is a separate
ruling: three sibling instances of the same shape have now been closed by hand,
which is a pattern rather than a coincidence.

## Steps

S01 through S03 build the store, its key and its record model. S04 and S05 move the
write and the read onto it. S06 discharges the roundtrip obligations. S07 corrects
the prose and the superseded decision. S08 is a separate ruling, not
implementation.

## Parallelization

S01 through S05 are a chain and resist splitting across owners: the namespace, the
key design and the record model together determine whether N reconciliations
persist distinctly, and that is the decision's riskiest property.

S04 and S05 must land together with S01 through S03 or the event and the store
disagree about where the detail lives. S06 follows the format being complete. S07
is prose plus a decision-record edit and is independent once the store exists —
but it must not be deferred past the store landing, since a docstring asserting no
parallel store exists becomes false the moment one does, and stale prose here has
a documented history of manufacturing false findings on later audit passes.

S08 shares no files with the rest and can proceed independently.

## Verification

Two risks are correctness risks in encrypted storage rather than matters of
effort, and both need a gate rather than a review.

The key must admit N reconciliations per work unit without overwriting, and must
admit the runs that carry no persisted revision at all. Prove both by writing
several reconciliations against one work unit and reading them all back, and by
reconciling with no persisted revision and reading that record back — a key that
silently collapses runs destroys exactly the history this work exists to preserve.

Write atomicity must be proven, not assumed: the record and the slimmed event land
together or neither lands.

The new format owes a strict save-load-equality roundtrip with every defaultable
field set to a non-default value, plus an anti-tautology proof that a mutated
stored payload surfaces a refusal. Use real adapters and a real master-key
provider throughout — a double that returns what the test expects is the canonical
false positive here.

The existing round-trip test binding grounding across a persist-and-read-back cycle
is a genuine gate on the relocation because it binds only to the public read API,
never to the payload. It must stay green without being touched.
