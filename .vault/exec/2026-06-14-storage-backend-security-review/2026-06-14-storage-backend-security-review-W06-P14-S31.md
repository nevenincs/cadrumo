---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S31'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace storage-backend-security-review with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S31 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
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
     The Move the transaction catalogue to one secure-object row per transaction keyed by transaction id so single-row mutations stop rewriting the whole catalogue and ## Scope

- `src/aeat/domain/transactions/_repository.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Move the transaction catalogue to one secure-object row per transaction keyed by transaction id so single-row mutations stop rewriting the whole catalogue

## Scope

- `src/aeat/domain/transactions/_repository.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Confirm the premise: `TransactionCatalogueRepository` stores the entire
  catalogue as ONE encrypted secure-object row keyed
  `transaction-catalogue:{bucket_id}` in the `aeat.domain.transactions.bucket`
  namespace, so any single-transaction add/update/remove rewrites and re-encrypts
  the whole catalogue blob.
- Scope the blast radius of the per-row redesign.

## Outcome

STEP DEFERRED — large persistence-model redesign, focused follow-up.

Moving to one secure-object row per transaction (keyed by transaction id) is a
clean target and the no-legacy rule means a straight cutover (no migration: delete
the whole-catalogue shape, ship the per-row shape). But the blast radius is the hot
ledger path and every reader of the catalogue:

- the repository read/write API (whole-catalogue load/save -> per-row load,
  namespace enumeration for list-all, single-row upsert/delete for mutations);
- the derived participation index
  (`ledger-participation-index-is-derived-rebuildable`) and its co-write atomicity;
- reconciliation, aggregation, and CLI consumers that load the catalogue;
- the uniform-quintet mutation contract (`ledger-mutation-returns-uniform-quintet`);
- the catalogue roundtrip + anti-tautology persistence tests (the whole-catalogue
  fixtures rewrite to per-row).

This is a self-contained campaign-sized slice that must land atomically with full
roundtrip coverage, not an end-of-session edit on the hot path. Deferred to a
focused pass with the ledger + persistence suites as the gate — the same
deferral-then-complete discipline that carried S23.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

Performance finding (medium): single-row mutations rewriting the whole catalogue is
O(n) write amplification per ledger edit. Correctness is unaffected today; this is a
scalability optimisation for large catalogues. No production regression to absorb.
