---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:faf2321a0c346eeaeecd8ebdbf7c8570cda5c4e5d6989d3c5307ab608c36441e'
step_id: 'S70'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Gate the defect class the draft-review findings belong to instead of adjudicating them one at a time: add dev/quality/secure_store_write_path.py, which separates read sites from write sites for every SecureBoundRepository in the shipped tree and fails on a store production reads that nothing fills. Four of twenty-four are read-never-written, including two withholding observation stores backing filing-grade aggregation sources, so an absent source reads as a zero; declare the four with their kind and rationale, and prove the detector with eighteen isolated-tree cases covering each binding shape, token-matched mutation, and a spent declaration.

## Scope

- `dev/quality/secure_store_write_path.py`
- `dev/quality/secure_store_write_path.toml`
- `dev/quality/tests/test_secure_store_write_path.py`
- `dev/audit/reachability_classification.toml`

## Changes

- `A` `dev/quality/secure_store_write_path.py`
- `A` `dev/quality/secure_store_write_path.toml`
- `A` `dev/quality/tests/test_secure_store_write_path.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `python -m dev.quality.secure_store_write_path` exit 0 with the four
  stores declared; exit 1 with the declaration empty
- `verify:` `pytest dev/quality/tests/test_secure_store_write_path.py` 18 passed
- `verify:` `ruff check` and `ty check` clean on both new modules
- `verify:` ledger validated by direct script -- 113 clusters, 274 symbols, no
  double classification, all twenty cited paths resolve

## Notes

The detector needed four rounds of tuning before it was worth shipping, and
each round is recorded in the module because each was a real false positive:

- a repository passed as an annotated parameter is written through that
  parameter name, not through a construction;
- `x if x is not None else Repository()` and `x or Repository()` hide the
  construction inside an `IfExp` or `BoolOp`, so the inject-or-default idiom
  made the most carefully written repositories look unwritten;
- mutation is not always the leading verb -- a repository in an atomic commit
  exposes `to_secure_object_write`, which a prefix rule reads as a query;
- excluding the defining module from writes hid every write helper sited beside
  its repository, which is where they belong. The exclusion is right for reads
  and wrong for writes.

The false-positive count fell 5 to 5 to 5 to 4 across those rounds while the
membership changed almost completely, which is the useful signal: a stable
count concealed that the detector was wrong about nearly every store.

Two of the four survivors are worse than unreached. `RetencionObservationRepository`
and `PercepcionObservationRepository` back filing-grade aggregation sources, and
their `save_observation` has no caller anywhere, so the aggregation reads an empty
store and contributes zero withholding where the honest answer is that the source
is absent.

### Correction, 2026-09-06

Three of the four stores this record named were detector false positives, found
by extending the same detector rather than by reading the code again. Only
`ModeloDraftRepository` was genuinely unwritten.

- `PurchaseInvoiceEvidenceRepository` is written at `evidence.py:425` through a
  module-level accessor annotated with the repository type.
- `RetencionObservationRepository` and `PercepcionObservationRepository` are
  written by `persist_retencion_observations` and
  `persist_percepcion_observations`, which the aggregate CLI calls. The detector
  missed a method named `replace_observations` because `replace` was absent
  from its mutating verbs.

Both gaps are closed and both are covered by the detector-teeth cases. The
declaration is now empty: every secure store the application reads has a
production writer.

The claim that two withholding stores fed filing-grade aggregations from empty
stores was wrong, and it was wrong in the direction that reads as most alarming.
A detector's first output is a hypothesis; this one needed six rounds before it
stopped producing false positives, and the count moved 5, 5, 5, 4, 2, 0.
