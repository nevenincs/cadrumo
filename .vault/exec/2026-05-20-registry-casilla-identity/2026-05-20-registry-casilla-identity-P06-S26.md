---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S26'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` `P06.S26`

Refocused the load-blocking completeness gate from `declared == manifest`
to `manifest-required ⊆ declared`, per the ADR amendment of 2026-05-20.

- Modified: `src/aeat/domain/calculations/registry/_validate.py`

## Description

`_emit_completeness_gate_failures` previously enforced an exact-set
equality (`declared == manifest`): both a manifest casilla missing from
the revision and a revision casilla missing from the manifest were hard
failures. Under the ADR amendment the gate must enforce
calculation-completeness, not full-Diseño coverage, so it is refocused to
subset semantics: `manifest-required ⊆ declared`.

The refocused gate iterates the manifest's required calculation-closure
casillas and, for each, emits a failure when (1) no casilla is declared
at the manifest's `(segmento, number)` identity — the identity check is
intrinsic to keying the declared lookup on the pair — or (2) the declared
casilla at that identity carries empty `legal_refs` or empty
`source_refs` — the legal-grounding check the amendment adds. The
extra-casilla branch is removed: a declared casilla absent from the
calculation manifest is a pure accounting-statement field and is no
longer a failure.

The gate stays rollout-staged and per-modelo: a revision with no
`completeness_manifest` still produces zero failures, so the gate remains
dormant until P05 authors the calculation-completeness manifests. No
manifests are checked in yet, so all 26 modelos continue to load valid.

## Tests

`pytest src/aeat/domain/calculations/registry/test_modelo_parity_coverage.py`
passes — all 26 modelos load valid and the gate stays dormant. The three
pre-existing gate tests in `test_referential_integrity.py`
(`test_completeness_gate_fails_on_missing_casilla`,
`test_completeness_gate_fails_on_extra_casilla`,
`test_completeness_gate_fails_on_diverging_segment_qualified_manifest`)
still assert the old `declared == manifest` message text and exact-set
semantics; they are refocused to the subset-plus-grounding semantics in
`P06.S29`. `ruff check` on the touched file passes clean.
