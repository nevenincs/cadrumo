---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:6e95ead4d9672124c3175aa17ccf4494841209ce07022e632a3eadc333af56f7'
step_id: 'S91'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Sweep the shipped tree for the docstring shape the filing-status token carried, an unreached symbol whose own sentence asserts a live consumer, and correct the two real ones: the corpus-drift assertion claimed the CI gate uses it when only its package test does, and the first-slice routing table claimed the snapshot-time referential-integrity gate confirms its targets when that confirmation is performed by the routing test instead. Do not ship the scan as a gate: half its hits are grammatical, the claim verb attaching to a different noun.

## Scope

- `src/cadrumo/core/corpus_manifest/manifest.py`
- `src/cadrumo/domain/renta/_first_slice_routing.py`
- `dev/audit/reachability_classification.toml`

## Changes

- `M` `src/cadrumo/core/corpus_manifest/manifest.py`
- `M` `src/cadrumo/domain/renta/_first_slice_routing.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `pytest .../corpus_manifest/tests/test_manifest.py
  .../renta/tests/test_first_slice_routing.py` 15 passed
- `verify:` the three ledger gates 19 passed; `docstring_reference_ratchet`
  exit 0; module ratchet and secure-store gate exit 0
- `verify:` duplication 10 / 0.05%; dead code 0; unused 1038, exact 409
- `verify:` `ruff check` and `ty check` clean

## Notes

Two more docstrings asserting a consumer that does not exist, found by scanning
for the shape the filing-status token carried. `assert_corpus_clean` called
itself the operator-facing assertion used by the CI gate; no gate calls it, only
its own package test. `first_slice_target_casillas` said the snapshot-time
referential-integrity gate uses it to confirm every routing target is a real
casilla; that confirmation IS performed, by the package's routing test, not at
snapshot build. The second correction is the more useful, because the check
exists and the sentence named the wrong runner -- a reader trusting it would
believe a snapshot build catches a casilla removal that in fact only a test run
catches.

The scan is NOT shipped as a gate. Six hits, and three are grammatical: the
claim verb attaches to a different noun, as in "every binding source used by the
revision", which describes the sources rather than a consumer of the function.
A fourth matched my own corrected docstring, because quoting a false sentence in
order to retract it reads exactly like making it. Half the population being
noise is the answer to whether this should fail closed.

The shape it does catch is worth carrying by hand: a docstring is the one claim
in the tree that no gate reads, and an unreached symbol is exactly where an
unchecked claim survives longest.
