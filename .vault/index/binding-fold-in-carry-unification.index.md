---
generated: true
tags:
  - '#index'
  - '#binding-fold-in-carry-unification'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:9d801cbe1ff21b19296260c93563c70100c43c70a23a5896d7c39c0ba52c0562'
related:
  - '[[2026-06-26-binding-fold-in-carry-unification-P01-S01]]'
  - '[[2026-06-26-binding-fold-in-carry-unification-P01-S02]]'
  - '[[2026-06-26-binding-fold-in-carry-unification-P01-S03]]'
  - '[[2026-06-26-binding-fold-in-carry-unification-P01-S04]]'
  - '[[2026-06-26-binding-fold-in-carry-unification-P02-S05]]'
  - '[[2026-06-26-binding-fold-in-carry-unification-P02-S06]]'
  - '[[2026-06-26-binding-fold-in-carry-unification-P02-S07]]'
  - '[[2026-06-26-binding-fold-in-carry-unification-P02-S08]]'
  - '[[2026-06-26-binding-fold-in-carry-unification-P02-S09]]'
  - '[[2026-06-26-binding-fold-in-carry-unification-P03-S10]]'
  - '[[2026-06-26-binding-fold-in-carry-unification-P03-S11]]'
  - '[[2026-06-26-binding-fold-in-carry-unification-P03-S12]]'
  - '[[2026-06-26-binding-fold-in-carry-unification-P03-S13]]'
  - '[[2026-06-26-binding-fold-in-carry-unification-P03-S14]]'
  - '[[2026-06-26-binding-fold-in-carry-unification-P04-S15]]'
  - '[[2026-06-26-binding-fold-in-carry-unification-P04-S16]]'
  - '[[2026-06-26-binding-fold-in-carry-unification-P04-S17]]'
  - '[[2026-06-26-binding-fold-in-carry-unification-adr]]'
  - '[[2026-06-26-binding-fold-in-carry-unification-plan]]'
  - '[[2026-06-26-binding-fold-in-carry-unification-reference]]'
  - '[[2026-07-10-binding-fold-in-carry-unification-research]]'
---

# `binding-fold-in-carry-unification` feature index

Auto-generated index of all documents tagged with `#binding-fold-in-carry-unification`.

## Documents

### adr

- `2026-06-26-binding-fold-in-carry-unification-adr` - `binding-fold-in-carry-unification` adr: `fold-in and carry unification: one cross-filing fold-in implementation and one compensacion-carry authority` | (**status:** `accepted`)

### exec

- `2026-06-26-binding-fold-in-carry-unification-P01-S01` - vaultspec-standard-executor: type RelationDefinition.aggregation as the BindingAggregation plus BindingAggregationOp model, hydrating the registry op token at the loader boundary (report-before-land, abort-on-WIP)
- `2026-06-26-binding-fold-in-carry-unification-P01-S02` - vaultspec-standard-executor: replace the three inline str(relation.aggregation).get('op') re-parses with the one binding_aggregation_op accessor at the requirement-keying and resolve sites
- `2026-06-26-binding-fold-in-carry-unification-P01-S03` - vaultspec-standard-executor: enforce the typed relation op at registry-build via the section validator, rejecting an unknown op at build not resolve time
- `2026-06-26-binding-fold-in-carry-unification-P01-S04` - vaultspec-code-reviewer: VERIFICATION GATE 5a - run full-calc, cross-period-continuity, and oracle suites after the relation-op typing and assert NO casilla value shifts and binding-aggregation-is-typed conformance green
- `2026-06-26-binding-fold-in-carry-unification-P02-S05` - vaultspec-high-executor: collapse RegistryRelationSourceRequirement and RegistryModeloObservationRequirement onto one typed requirement model with one period-offset field, atomic relocation:RegistryFoldRequirement with consumers and top-level __all__ re-export
- `2026-06-26-binding-fold-in-carry-unification-P02-S06` - vaultspec-high-executor: collapse the three near-identical observation-folding loops onto the one fold helper from the phase-2.2 resolver contract, preserving the M130 direct-carry and M353 per_grupo_member output shapes exactly (apply-cached on collision, peer-WIP likely)
- `2026-06-26-binding-fold-in-carry-unification-P02-S07` - vaultspec-high-executor: route the previous_filing observation-fold path through the one helper, removing the third duplicate loop (apply-cached on collision, peer-WIP likely)
- `2026-06-26-binding-fold-in-carry-unification-P02-S08` - vaultspec-code-reviewer: VERIFICATION GATE 5b - run full-calc, cross-period-continuity, and oracle suites after the fold-helper collapse and assert NO casilla value shifts with M130 and M353 shapes byte-identical
- `2026-06-26-binding-fold-in-carry-unification-P02-S09` - vaultspec-code-reviewer: VERIFICATION GATE 3 - assert the M303 modelo-303-compensacion-pendiente-anteriores carve-out and the relation/previous_filing collision gate still fire EXACTLY ONCE post-dedup, never a double-fire
- `2026-06-26-binding-fold-in-carry-unification-P03-S10` - vaultspec-code-reviewer: VERIFICATION GATE 1-BEFORE - run the #1 M303 refunded-period zero-carry, #7 M390 box 97 prior-pending, and #12 M390 box 662 applied-credit regression gates and record the baseline casilla values before any carry-reconciliation edit
- `2026-06-26-binding-fold-in-carry-unification-P03-S11` - vaultspec-high-executor: reconcile the registry previous_filing compensacion formula path to feed or defer to the iva-wallet authority disposition-aware, removing the back-door observation-injection second route (apply-cached on collision, peer-WIP likely)
- `2026-06-26-binding-fold-in-carry-unification-P03-S12` - vaultspec-high-executor: reconcile the derive_303_compensation_available carry path onto the one wallet authority so the M390 box 97/662 FIFO partition derives from the one projection (apply-cached on collision)
- `2026-06-26-binding-fold-in-carry-unification-P03-S13` - vaultspec-code-reviewer: VERIFICATION GATE 1-AFTER - re-run the #1 M303 refunded-period, #7 M390 box 97, and #12 M390 box 662 regression gates after each carry-reconciliation sub-step and assert ZERO casilla value shifts against the recorded baseline
- `2026-06-26-binding-fold-in-carry-unification-P03-S14` - vaultspec-code-reviewer: VERIFICATION GATE 2 - assert the #6/#28 perceptor-count and percepciones-count results in the same value layer are unchanged after the carry-authority reconciliation
- `2026-06-26-binding-fold-in-carry-unification-P04-S15` - vaultspec-low-executor: VERIFICATION GATE 4 - grep-confirm ZERO live MultiYearResolver callers across src/aeat immediately before deletion, recording the grep result in the Step Record
- `2026-06-26-binding-fold-in-carry-unification-P04-S16` - vaultspec-standard-executor: delete the MultiYearResolver class and its request/report models, cleanly separating it from the live EnrollmentRecorder in the shared module, atomic relocation:MultiYearResolver-removal with __all__ baseline
- `2026-06-26-binding-fold-in-carry-unification-P04-S17` - vaultspec-code-reviewer: assert the live EnrollmentRecorder remains intact and importable through the top-level __all__ re-export and the full collect-only gate is clean after the orphan deletion

### plan

- `2026-06-26-binding-fold-in-carry-unification-plan` - `binding-fold-in-carry-unification` plan

### reference

- `2026-06-26-binding-fold-in-carry-unification-reference` - `binding-fold-in-carry-unification` reference: `phase-2.3 fold-in and carry anchor pins`

### research

- `2026-07-10-binding-fold-in-carry-unification-research` - binding-fold-in-carry-unification research: warning closeout research grounding
