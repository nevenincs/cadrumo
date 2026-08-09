---
tags:
  - '#exec'
  - '#unfalsifiable-test-sweep'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:4f0de0cd41ff7a30d227c14bd56b88d80612a656799a04d02a45d51f19aaf329'
step_id: 'S03'
related:
  - "[[2026-08-09-unfalsifiable-test-sweep-plan]]"
---
# Prove both floors bite by emptying each walker at runtime and confirming the corresponding floor fails

## Scope

- `src/cadrumo/tests/test_utf8_enrollment_inventory.py`

## Description

- Ran three distinct mutations rather than one, each isolating a different claim.
- Confirmed the module and its sibling gates stay green unmutated.

## Outcome

Each floor is proven against the specific failure it exists to catch, rather than against a single blanket mutation that would have conflated them.

**Dev walker emptied alone.** Before: `3 passed`, nothing noticed. After: the dev floor fails. This isolates the live vacuity, because the production ratchet is untouched and therefore cannot be what fires.

**Both walkers emptied.** Three failures: both floors plus the inert-entry check. Confirms the floors are independent of each other.

**Ratchet drained to empty AND production walk collapsed.** Only the production floor fires; the inert-entry check passes, having nothing left to find inert. This is the one that proves the finding's actual claim - that the pre-existing protection was accidental and self-cancelling - and it is the state no test could previously detect.

Running all three separately is what distinguishes "a floor exists" from "this floor catches this failure". A single mutation emptying everything would have failed several tests at once and told me almost nothing about which guard was doing the work.

## Verification

    uv run --no-sync pytest src/cadrumo/tests/test_utf8_enrollment_inventory.py src/cadrumo/tests/test_no_tautology.py src/cadrumo/tests/test_shared_source_corpus_floor.py src/cadrumo/tests/test_marker_integrity.py -n 0 -q
    45 passed in 66.92s (0:01:06)

The repository's own hard-zero tautology gate and its shared-corpus floor module are included deliberately: this work adds assertions and constants, and both are surfaces those gates police.

## Notes

Every mutation was applied at runtime from outside the repository, so no tracked file was modified at any point and a crashed run would have left no residue.
