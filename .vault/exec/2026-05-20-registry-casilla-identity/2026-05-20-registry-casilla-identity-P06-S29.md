---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S29'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` `P06.S29`

Updated the completeness-gate tests to the refocused
`manifest-required ⊆ declared` plus identity and grounding semantics,
replacing the `declared == manifest` assertions.

- Modified: `src/aeat/domain/calculations/registry/test_referential_integrity.py`

## Description

The P03 gate-test block asserted the old exact-set equality semantics.
The block is rewritten to the ADR-amendment subset-plus-identity-plus-
grounding contract:

- `test_revision_without_manifest_passes_completeness_gate` — unchanged;
  the gate stays dormant for a manifest-less revision.
- `test_completeness_gate_passes_when_manifest_required_subset_of_declared`
  — reframed from "matches" to subset semantics: the gate passes when
  the manifest's required set is a subset of the declared set.
- `test_completeness_gate_passes_when_revision_declares_extra_accounting_casilla`
  — NEW, the inverted former extra-casilla test: a declared casilla
  absent from the calculation manifest (a pure accounting-statement
  field) must NOT red the gate.
- `test_completeness_gate_fails_on_missing_required_casilla` — updated
  to the new `calculation-completeness manifest requires casilla number`
  message wording.
- `test_completeness_gate_fails_on_mis_segmented_required_casilla` —
  NEW: a required casilla declared under the wrong `segmento` is reported
  missing at the manifest's required identity, while the wrongly-
  segmented declared casilla is NOT separately reported (subset
  semantics never red an unrequested declared casilla).
- `test_completeness_gate_fails_on_ungrounded_required_casilla` — NEW:
  a required casilla declared without `legal_refs` / `source_refs` —
  built via `model_construct` to bypass the schema's non-empty-refs
  validator and reach the gate's defensive grounding branch — is
  reported ungrounded. This proves the gate's grounding check is
  load-bearing and enforces the ADR-amendment provenance requirement
  independently of the schema-level field constraint.

The `model_construct` casilla is a real `CasillaDefinition` instance,
not a mock: pydantic's documented validation-bypass constructor produces
a genuine object so the gate's real grounding branch executes against
real data. No mocks, skips, xfail, or tautological assertions.

## Tests

`pytest src/aeat/domain/calculations/registry/test_referential_integrity.py
src/aeat/domain/calculations/registry/test_modelo_parity_coverage.py`
passes — 46 tests, including all 6 calculation-completeness gate tests;
all 26 modelos load valid and the gate stays dormant. `ruff check` on
the touched file passes clean.
