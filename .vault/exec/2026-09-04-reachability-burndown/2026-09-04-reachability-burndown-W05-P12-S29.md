---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:669ae4b7a1922c6041701c9f5c11551e3cad68e7903ee7a2da0f3fa84996f6e7'
step_id: 'S29'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Close the orphan-walk blind spot in which 239 of 3334 test modules name no shipped subject because they reach their code through a support module inside their own test package, so a dead test behind that hop can never be reported; traverse the hop without letting a live subject reached that way suppress an existing finding

## Scope

- `dev/audit/unreachable_code.py`

## Changes

- `M` `dev/audit/unreachable_code.py`
- `M` `dev/audit/tests/test_unreachable_code.py`
- `verify:` `uv run --no-sync pytest -q dev/audit/tests/test_unreachable_code.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --json` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/audit` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.unused_symbol_ratchet` -> `fail, two peer-owned symbols unrelated to this step`

## Notes

Test modules are excluded from the shipped population, so a test importing a
helper inside its own tests package resolved that import to nothing and looked
subjectless. The walk skipped it, and a dead test sitting behind such a helper
could never be reported. Subject resolution now takes one hop through a support
module in the test's own package.

The hop is applied ONLY to a test that resolved no shipped subject of its own,
and that restriction is the safety property, not an optimisation: it can give a
subjectless test some subjects, so a test whose support reaches nothing but dead
code is newly reportable, but it can never add a live subject to a test that is
already reported and thereby silence an existing finding. The real tree confirms
the direction: orphaned tests 25 before and 25 after, zero newly reported, zero
no longer reported.

That zero delta is the honest outcome and not a no-op, which was checked rather
than assumed. Test modules naming no shipped subject fall from 239 of 3334 to
78, so 161 tests gained subjects through the hop and every one of them reaches
live code. The remaining 78 sit behind deeper indirection or genuinely exercise
no shipped subject.

Both directions carry teeth in the synthetic tree. A test importing only a
helper that imports the dead module is reported; a test importing only a helper
that reaches live code is not, so the change cannot trade a blind spot for a
false accusation. Four pinned fixture expectations moved because the tree gained
a deliberately-orphaned test.

One support module serves many tests, so parsing it per importer took the walk
past ten minutes; parsed support subjects are cached per path.

No threshold, exclusion, baseline, skip or allowlist was changed.
