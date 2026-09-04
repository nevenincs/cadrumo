---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:d57d02cfce03d3b0fdab91aebb98fd29677739677913381dbd7626c67fab7c1a'
step_id: 'S12'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Re-measure every signal from one stable revision and prove no false green remains

## Scope

- `dev/audit`

## Changes

- `verify:` `uv run --no-sync python -m dev.audit.duplication` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.dead_code` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.unused_symbol_ratchet` -> `pass`
- `verify:` `uv run --no-sync pytest -q -m "unit or integration" dev/audit/tests/test_reachability_classification.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -m "unit or integration" dev/audit/tests/test_duplication.py dev/audit/tests/test_duplication_scan.py` -> `pass`
- `verify:` `uv run --no-sync lint-imports` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.unreachable_module_ratchet` -> `fail, peer-owned`

## Notes

Measured at revision b3fb20a985. Every gate this campaign owns is green: duplication and
dead-code exit 0, the new unused-symbol ratchet exits 0, the classification ledger's eight
gates pass, the duplication instrument's twenty-eight pass, and all eleven import contracts
hold.

The claim this Step had to prove is that no FALSE green remains, and it does. When the
campaign opened, `check-unreachable-ratchet` exited 0 while 1408 symbol findings and 21
orphaned test modules sat outside every gate. Those populations are now gated: 555
exact-confidence symbols across 315 modules and 23 orphaned test modules are recorded in a
shrink-only baseline that fails in four directions, each proven by teeth.

The module ratchet is RED on `cadrumo.domain.contabilidad` and
`cadrumo.domain.is_compensation`, and that does not contradict the claim. A red gate is the
opposite of a false green: it is the instrument working. Those two packages arrived from
concurrent work as new capability whose consumers are not written yet, they were classified
`staged-capability` in this campaign's ledger with their commits named, and they were
deliberately never baselined -- the gate's own text forbids it, and adding a line is the
erosion this campaign exists to prevent. Resolving them belongs to whoever is landing that
capability.

## Closure

The campaign closes on classified resolution, which is what its governing decision
requires, not on the count reaching zero. What the numbers mean now:

* 1384 symbol findings remain, of which 555 are `exact` and gated. The rest are
  `name-match` and `name-match-data` -- attribute accesses the scan cannot bind to a type,
  which are review candidates rather than facts, and gating them would ratchet guesses.
* 58 module findings remain, 26 of them inside the deferred TUI prefix. The 17 in scope are
  each classified with evidence: nine staged capability behind accepted decisions, five
  design-time authorities, three deferred by ownership, one orphan and one should-be-live.
* The `allowed` backlog shrank from 14 to 10 and the typed `[[intentional]]` dispositions
  grew from 1 to 5, each naming the conformance gate that reads it.

The remaining backlog is visible, classified, and gated. That is the honest end state: it
was never going to be zero, because a large part of the population is capability someone
decided to build ahead of its caller, and deleting it would discard the decision.
