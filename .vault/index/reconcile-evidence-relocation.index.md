---
generated: true
tags:
  - '#index'
  - '#reconcile-evidence-relocation'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:205ab0b127971b989a72b228ed30eebdf567252e4a52ab27ddedb04447a92391'
related:
  - '[[2026-07-25-reconcile-evidence-relocation-adr]]'
  - '[[2026-07-25-reconcile-evidence-relocation-plan]]'
  - '[[2026-07-25-reconcile-evidence-relocation-research]]'
---

# `reconcile-evidence-relocation` feature index

Auto-generated index of all documents tagged with `#reconcile-evidence-relocation`.

## Documents

### adr

- `2026-07-25-reconcile-evidence-relocation-adr` - `reconcile-evidence-relocation` adr: `where reconcile diff detail persists` | (**status:** `accepted`)

### exec

- `2026-07-25-reconcile-evidence-relocation-S01` - Register the MODELO_RECONCILIATION_RECORDS secure-object namespace at AUDIT sensitivity and PROFILE_LOCAL scope and STRUCTURED_CUSTODY disposition, enrolling its durability floor and version and empty upgrader registry at birth as compatibility-lifecycle-checkpoint requires
- `2026-07-25-reconcile-evidence-relocation-S02` - Design the object key to admit N reconciliations per work unit rather than overwriting, and to admit the runs that carry no persisted revision at all, since receipt-total and declaracion-casilla reconciles emit a no_persisted_revision advisory and still produce a report and identity-header reconcile needs no revision
- `2026-07-25-reconcile-evidence-relocation-S03` - Add the strict-frozen reconciliation record model carrying verdict and source kind and source reference and work unit id and the grounded diffs and advisories and instant and actor, reusing the existing strict-frozen diff and advisory models unchanged, with grounding stored rather than re-derived
- `2026-07-25-reconcile-evidence-relocation-S04` - Write the reconciliation record and the slimmed bucket event atomically through the existing co-emit write discipline, so a crash between them cannot desynchronise the event log from the detail store
- `2026-07-25-reconcile-evidence-relocation-S05` - Repoint list_modelo_reconciliations at the new store while keeping its return type so the CLI payload schema and the round-trip test are undisturbed, and delete diffs_detail from the payload rather than migrating it, leaving the event carrying verdict and count
- `2026-07-25-reconcile-evidence-relocation-S06` - Prove the new persisted format with a strict save-load-equality roundtrip populating every defaultable field to a non-default value, plus an anti-tautology proof that a mutated stored payload surfaces a refusal, using real adapters and a real master-key provider rather than doubles
- `2026-07-25-reconcile-evidence-relocation-S07` - Rewrite the ModeloReconciliationHistoryEntry docstring whose no-parallel-reconciliation-store sentence the new store makes false, and re-affirm the provenance-carried constraint of the superseded Decision 2.B at the new site
- `2026-07-25-reconcile-evidence-relocation-S08` - Rule whether the bucket-event substrate deserves a standing guard against joining a variable-length value into a capped payload slot, four instances found and three closed by hand, and give the un-ratified 500-character cap its first declared home

### plan

- `2026-07-25-reconcile-evidence-relocation-plan` - `reconcile-evidence-relocation` plan

### research

- `2026-07-25-reconcile-evidence-relocation-research` - `reconcile-evidence-relocation` research: `the 500-char payload ceiling on reconcile diff detail`
