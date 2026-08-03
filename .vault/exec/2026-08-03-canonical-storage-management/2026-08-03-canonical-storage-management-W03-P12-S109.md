---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:ff13876f424018553c6ee6d00ff3837321aa54b04c84a076a68be29cae009266'
step_id: 'S109'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---
<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace canonical-storage-management with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S109 and 2026-08-03-canonical-storage-management-plan placeholders are machine-filled by
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
     The Fix the stale expected tuples in the compatibility-lifecycle gate's enrollment-predicate test, campaign-caused by this campaign's own persisted-format declarations adding bucket_database_file and secret_index, currently red at HEAD across all three parametrised cases, routed and ## Scope

- `consider deriving the expectation from the declared formats rather than restating it by hand`
- `since a hardcoded census of uncovered formats is the gate shape this project forbids elsewhere`
- `src/cadrumo/tests/test_compatibility_lifecycle_gate.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Fix the stale expected tuples in the compatibility-lifecycle gate's enrollment-predicate test, campaign-caused by this campaign's own persisted-format declarations adding bucket_database_file and secret_index, currently red at HEAD across all three parametrised cases, routed

## Scope

- `consider deriving the expectation from the declared formats rather than restating it by hand`
- `since a hardcoded census of uncovered formats is the gate shape this project forbids elsewhere`
- `src/cadrumo/tests/test_compatibility_lifecycle_gate.py`

## Description

- Confirm `bucket_database_file` is genuinely declared `DURABLE` in the
  persisted-format inventory, grounded in its own documented rationale (the
  per-bucket SQLite file carrying the encrypted `secure_object` rows -- real
  taxpayer data at the container level, no rebuild path).
- Update the three parametrised `floors` -> `expected` tuples in the
  enrollment-predicate test to include `bucket_database_file` in its correct
  sorted position, and correct the accompanying "two durable formats" comment
  to "three".
- Deliberately did NOT derive the expected tuples from the declared format
  set programmatically, despite the Step row's suggestion to consider it.

## Outcome

Fixed all three parametrised cases (`floors0/1/2`), previously red at HEAD.
The test's own docstring states its purpose is non-vacuity: proving the
predicate under test is not "always return an empty tuple". Deriving the
expected value by re-computing the same filter the predicate itself applies
(durable-and-not-in-floors) would make the test tautological -- it would
verify only that the predicate agrees with itself, exactly the failure mode
the test exists to rule out. The hand-typed literal tuples are the
independent oracle; the fix updates that oracle's one stale entry rather than
routing around the discipline that makes it a real check.

## Notes

None. No skipped work, no scaffolds left in code.
