---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:45174c5582a11cff5b4886fb0998381b928c235b897dad0d6f7c4e04a88f6479'
step_id: 'S116'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
  - "[[2026-08-03-canonical-storage-management-W05-P22-S115]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace canonical-storage-management with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S116 and 2026-08-03-canonical-storage-management-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Extend the W05.P22.S115 dormancy-assertion procedure to the other eight rotation-plan entries selfaudit found sharing the same declared-consumer signal (FINANCIAL_TRANSACTIONS, INVOICES, USAGE_RATIOS, SUBMISSIONS, SUBMISSIONS_AMENDMENTS, SUBMISSIONS_AMENDMENT_RESULTS, FILING_HISTORY, WORKFLOW_RUNS), checking each entry's consumer_module individually rather than inheriting the all-twelve-share-one-consumer generalisation, and writing an accessor-routed persist-then-assert-absent test for every entry with a real writer and ## Scope

- `src/cadrumo/adapters/persistence/profile/tests/test_transactions_repository_roundtrip.py`
- `src/cadrumo/adapters/persistence/profile/tests/test_invoices_secure_storage_roundtrip.py`
- `src/cadrumo/domain/usage_ratios/tests/test_service.py`
- `src/cadrumo/adapters/persistence/storage/tests/test_submission_repository.py`
- `src/cadrumo/domain/filing/tests/test_amendment_roundtrip.py`
- `src/cadrumo/application/filing/tests/test_history_repository_roundtrip.py`
- `src/cadrumo/application/workflow/tests/test_run_persistence_roundtrip.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Extend the W05.P22.S115 dormancy-assertion procedure to the other eight rotation-plan entries selfaudit found sharing the same declared-consumer signal (FINANCIAL_TRANSACTIONS, INVOICES, USAGE_RATIOS, SUBMISSIONS, SUBMISSIONS_AMENDMENTS, SUBMISSIONS_AMENDMENT_RESULTS, FILING_HISTORY, WORKFLOW_RUNS), checking each entry's consumer_module individually rather than inheriting the all-twelve-share-one-consumer generalisation, and writing an accessor-routed persist-then-assert-absent test for every entry with a real writer

## Scope

- `src/cadrumo/adapters/persistence/profile/tests/test_transactions_repository_roundtrip.py`
- `src/cadrumo/adapters/persistence/profile/tests/test_invoices_secure_storage_roundtrip.py`
- `src/cadrumo/domain/usage_ratios/tests/test_service.py`
- `src/cadrumo/adapters/persistence/storage/tests/test_submission_repository.py`
- `src/cadrumo/domain/filing/tests/test_amendment_roundtrip.py`
- `src/cadrumo/application/filing/tests/test_history_repository_roundtrip.py`
- `src/cadrumo/application/workflow/tests/test_run_persistence_roundtrip.py`

## Description

Enumeration method: queried `STORAGE_TAXONOMY` directly (`from cadrumo.core._storage_taxonomy
import STORAGE_TAXONOMY`) for every member whose `consumer_module` field equals
`"adapters/persistence/storage/_rotation.py"`, rather than inheriting the four-member set
`W05.P22.S115` had already closed. Twelve members matched, not four -- the coordinator's and a
peer's prior twelve-of-twelve claim (built by generalising `S115`'s four onto the full
`default_rotation_plan()` entry count) was itself unverified at the point it was accepted;
this Step re-derived the set from the taxonomy declaration instead of from the generalisation.

Verification actually run, per entry, individually -- not inherited from the pattern:

- Read each of the eight new members' production repository module to confirm the docstring
  states the SQL-only claim (`filing_drafts.py`/`justificante.py`-shaped "no plaintext ...
  lands on disk" sentence), rather than assuming every rotation-plan entry shares it.
- `WORKFLOW_RUNS` broke the pattern: its `consumer_module` is
  `application/workflow/_persistence.py`, not `_rotation.py`, unlike the other eleven. Read
  that module directly rather than treating the mismatch as noise; its `save_run` docstring
  states the same SQL-only claim in different words ("`runs_dir` remains part of the API as a
  logical marker path for callers and tests, but no plaintext run file is written there").
- `SUBMISSIONS_AMENDMENT_RESULTS` had no distinct writer at all -- grepped zero
  non-declaration references to the category anywhere in the tree, confirmed via
  `_rotation.py`'s own comment that `ModeloAmendmentRepository` is one consumer identity
  bound to two sibling directories under one HKDF context, not two writers.
- Wrote one accessor-routed, persist-then-assert-absent test per entry with a confirmed real
  writer (seven of the eight; the eighth, `SUBMISSIONS_AMENDMENT_RESULTS`, was asserted
  alongside `SUBMISSIONS_AMENDMENTS` in the one test that persists an amendment, since no
  production path can populate it independently).
- Measured, before committing, that every one of the eight `storage_path(StorageCategory.X)`
  resolutions used by the new tests does not exist prior to any write, inside the same
  `isolated_runtime_profile` context the tests use -- the mutation proof, not inferred from
  the docstring reading alone.
- Ran the full affected test set (`pytest` across the seven touched files): 77 passed. Ran
  `ruff check` on the same seven files: clean after one import-ordering auto-fix.

Method divergence from a per-package walk: this work followed the `W05.P22.S115` shape
(one taxonomy-derived candidate list, one test per confirmed writer, one commit), not the
`S78` band's per-package-provenance-gate shape; there was no separate provenance gate to
scope against since the target set was the twelve-member `_rotation.py` cluster, not a test
package.

## Outcome

Twelve of twelve taxonomy members declaring `_rotation.py`-or-equivalent as their sole
consumer are now accounted for by direct test evidence: `ATTACHMENTS` (pre-existing test),
`DRAFTS`/`JUSTIFICANTES` (`W05.P22.S115`), and the eight closed by this Step --
`FINANCIAL_TRANSACTIONS`, `INVOICES`, `USAGE_RATIOS`, `SUBMISSIONS`,
`SUBMISSIONS_AMENDMENTS`, `FILING_HISTORY`, `WORKFLOW_RUNS` proven by new test,
`SUBMISSIONS_AMENDMENT_RESULTS` proven to have no writer and correctly carrying no test.
Landed in commit `de226e6853` (verified `--numstat` before this record: 7 files, 217
insertions).

## Notes

This record was written after the fact, in response to a campaign-wide finding that most of
the `S78` literal-migration burndown was reported only through the team relay chain and never
reached `.vault/exec/`. This Step's own work had the identical gap: the eight-entry extension
(`de226e6853`) was reported to the team lead by message only, with no exec record, until this
backfill. The corrected consumer-module count (twelve, not four) that this Step's enumeration
produced was itself a correction of an unverified twelve-of-twelve claim already in
circulation -- recorded here so the correction survives independently of the message thread
that carried it.
