---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S30'
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
     The S30 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
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
     The Make secure-object namespace enumeration stream decrypted rows instead of materialising and sorting the full set and ## Scope

- `src/aeat/adapters/persistence/storage/sql/secure_objects.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Make secure-object namespace enumeration stream decrypted rows instead of materialising and sorting the full set

## Scope

- `src/aeat/adapters/persistence/storage/sql/secure_objects.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Audit the enumeration path: `SecureObjectRepository.iter_records_with_failures` already streams the raw SQL scan (`stream_results=True`, `yield_per`, `ORDER BY object_key`, per-row decrypt, fault-isolated).
- Trace the materialise+sort named by M8 to `SecureBoundRepository.iter_ids` / `iter_records` (`envelope/_secure_repository.py`): both buffer every decrypted row and `sorted(...)` in Python.
- Audit the ~12 enumeration consumers and the contract test for order-dependence.

## Outcome

STEP DEFERRED — constraint-bound, not a mechanical edit.

The materialise+sort in `SecureBoundRepository.iter_records` / `iter_ids` exists to
honour a **declared, tested lexicographic-natural-id ordering contract**
(`test_secure_bound_repository.py:90` — "Lexicographic id ordering is part of the
contract" — asserts `iter_ids() == ("alpha","beta")` and
`iter_records() == (first, second)`). The SQL secure-object store is keyed and
ordered by an **HMAC/`HashedLookup` digest of the id**, never the natural id
(storing the natural id in an order-preserving column would leak sensitive ids —
e.g. justificante CSVs, submission ids — in plaintext, violating the encryption
model). The natural id is recoverable only **after** decrypting each row, so
yielding in natural-id order is impossible without first decrypting and buffering
the whole namespace. True O(1) streaming therefore cannot satisfy the ordering
contract.

It also cannot satisfy the **fail-closed scan-all-before-yield contract** of
`SecureObjectRepository.list_records` (which raises `SecureObjectUnreadableError`
*before* yielding any readable row when any row is unreadable). Streaming would
weaken this to "yield the readable prefix, then raise mid-iteration" — a real
safety regression for a partial-namespace consumer.

Resolving M8 is a **design decision**, not a mechanical streaming edit: either
relax the lexicographic-ordering contract (and audit/adjust the id-list display
consumers — `list_draft_ids`, `list_submission_ids`, `list_csvs` — plus the
contract test) or accept a CPU-for-memory trade (two-pass: stream to collect
`(id, row_id)`, sort the small key set, re-fetch+decrypt by row id in order). The
raw SQL scan is **already memory-bounded** (`yield_per`); only the
fail-closed/sort buffer of decrypted records is O(n), and that buffer is required
by the two contracts above.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

Deferred deliberately rather than silently break a tested ordering contract and a
fail-closed safety contract for a medium performance finding. Follow-up: a focused
design slice that decides the ordering-contract relaxation (with a per-consumer
order-dependence audit) or implements the two-pass key-sort. No production
consumer that needs a specific order relies on this method's order today — they
re-sort (`_iva_compensation_history`, `_rule_repository`, `_iva_remote_state`,
submission `list_filings`) or document "unspecified order"
(`_observations_repository`); the binding constraint is the display id-lists and
the contract test.
