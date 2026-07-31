---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:7852fac7b71fb03c5e288ced7f80d4f8b349c40e34312d3c6f130e90639959ee'
step_id: 'S06'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# re-point the external-oracle grounding gate at the lifted library in the same commit, keeping both honesty directions asserted

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_external_oracle_grounding_enrolled.py`

## Description

- Replace the module's seven private fold helpers with two calls into the lifted
  library, leaving the gate to assert rather than to compute.
- Keep the oracle-to-registry direction asserting over the typed findings: bundled
  evidence must exist, the registry read must yield revisions, at least one bundled
  filing year must attribute to a revision, and no casilla may be stranded as
  uncomputed or unenrolled.
- Keep the registry-to-oracle direction asserting that the registry declares grounding
  to cross-check at all, and that no declaration lacks bundled evidence for an
  applicable filing year.
- Carry every anti-vacuity floor across unchanged in meaning, translating the two
  counters the trapped implementation accumulated into named audit properties, and add
  a fourth floor asserting the registry read yielded revisions at all.
- Add a third test proving every payload on disk surfaces either as attributed evidence
  or as a recorded attribution gap.
- Rewrite the module docstring to describe the gate's role over the library rather than
  the fold it used to own.

## Outcome

No assertion was weakened. Both honesty directions and all anti-vacuity floors survive;
the third test adds a guarantee the module did not previously carry. The gate shrank
from 267 lines to 133, of which the assertions are now the substance.

The floors map across without loss. The bundled-evidence floor becomes a non-empty
evidence tuple; the matched-revision floor becomes a checked-revision count; the
declared-grounding floor becomes a declared-grounding count, still counting
casilla-level declarations and measuring 58 exactly as the counter it replaces did.

The added third test closes a real hole rather than a hypothetical one. A payload the
fold skipped silently was indistinguishable from one it read and found clean, and one
bundled Modelo 303 manual oracle is exactly that case today. The test compares the
payload names the fold accounted for against the names on disk, so a future silent drop
fails loudly instead of quietly shrinking the gate's reach.

Verification, run at the commit:

- `pytest src/cadrumo/domain/calculations/registry/tests/test_external_oracle_grounding_enrolled.py -m integration -v`
  collected 3 items, all three PASSED, exit line `3 passed in 6.92s`, process exit
  status 0. The three are `test_every_externally_grounded_casilla_is_computed_and_enrolled`,
  `test_every_declared_externally_grounded_casilla_has_oracle_evidence`, and
  `test_every_bundled_oracle_payload_is_accounted_for`.
- The `-m integration` selector is required and was used: the module carries the
  integration and hex_domain marks, and the repository default selector would have
  collected nothing from it and exited green on zero tests.
- The pre-change baseline on the same selector was `2 passed in 8.62s`, so the gate went
  from two passing assertions to three with none removed.
- Both honesty directions were separately proven to fail when breached, against the real
  registry: starving the evidence yields 54 unevidenced-declaration findings, and
  injecting a stranded oracle figure yields 1 stranded finding, both flipping the audit
  verdict to not-ok while the unmutated control holds at 0 findings.
- `ruff check` and `ruff format --check`: clean.

## Notes

The lift and the re-point share one commit, as the plan Step and the governing decision
record both require of a test-trapped fact lift.

The re-pointed module keeps reading the registry through the non-validating loader, by
way of the library's bundled entry point. That choice was inherited deliberately, not by
default: the gate runs in a worktree where peers edit the registry concurrently, and the
validating authority can refuse a mid-edit tree outright, which would red the gate for a
reason that has nothing to do with grounding. The library stamps that read as unvalidated
so the resilience does not quietly masquerade as validated authority.

The module still names the two corpus directories, because proving the fold visited every
payload requires an independent listing of what is on disk. Reading the same directories
from the library instead would have made the test assert the fold against itself.
