---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:3c66d7153709d78a0b7576d3c6133210141791aea1ee5d4ec1c9390d03044959'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-canonical-derivations-adr]]"
  - "[[2026-08-10-casilla-schema-research]]"
---
# `casilla-schema` audit: `S10 M390 M303 adjustment reverse join`

## Scope

Reviewed W02.P03.S10 against the accepted canonical-derivations decision, campaign plan, research, and audit template. The owned surface is the M390/M303 reconciliation target derivation in `_calculation_modelo_adjustments.py` and its new direct test. The required change is to delete the local last-write-wins primary-only mapper, consume the facade-exported canonical `casillas_by_binding`, preserve every casilla reached by a target binding including alternate bindings, and carry that complete target set into refusal context without introducing another join authority.

## Findings

No actionable findings.

The local dict comprehension is removed. Production imports `casillas_by_binding` from the public registry facade and calls it once for the law-selected snapshot revision. The relation loop now receives the canonical ordered tuple for each target binding rather than one overwritten casilla id. Empty target tuples retain the prior skip behavior. Non-empty tuples are carried through `_m390_303_reconciliation_targets`, and `_raise_if_m390_303_reconciliation_would_save_silent_zero` extends both the typed error context and precondition evidence with every target casilla. If one binding feeds multiple casillas, none is discarded; the finding count correctly remains relation/binding-grain while the target-id evidence is casilla-grain.

The new regression loads the real bundled M390 2025 annual snapshot and reconstructs only the target `CasillaDefinition` through production Pydantic validation. Moving the target binding from primary to `alternate_bindings` makes the old primary-only mapper fail while the canonical reverse join returns the expected relation and target tuple. The test does not duplicate the join predicate or implement the production relation loop, and it uses no fake, stub, mock, patch, monkeypatch, skip, or expected-failure construct.

Exact-symbol inspection finds no remaining local binding-to-casilla mapper in the owned module. The production import resolves through the public registry facade whose exported symbol is the canonical `_bindings.casillas_by_binding`; no private import, alias, compatibility path, or redeclared authority is introduced.

## Verification

- Direct S10 test module: 1 passed.
- Scoped Ruff: passed.
- Scoped BasedPyright: 0 errors, 0 warnings, 0 notes.
- Scoped `git diff --check`: passed.
- Prohibited test-construct scan: no hits.
- Exact local mapper sweep: only the facade import, canonical call, and result lookup remain.
- The reported existing M390/M303 e2e red was not rerun as a broad gate at reviewer stop. Direct fixture/corpus inspection confirms that test still pins `_M303_REVISION = "2023-y-siguientes"`, while the current M303 authoring tree declares `2023`, split 2024 revisions, `2025`, and `2026-y-siguientes`; this stale fixture id is unrelated to the S10 reverse-join diff.

## Recommendations

No corrective action is required for S10. Repair the stale e2e revision fixture in its owning workstream rather than widening this step or adding revision compatibility.

Verdict: **PASS.** W02.P03.S10 truthfully retargets the M390/M303 refusal path to the canonical reverse join, preserves alternate and multi-casilla targets, and introduces no duplicate authority.
