---
tags:
  - '#audit'
  - '#tui-registry-api-gate'
date: '2026-09-30'
modified: '2026-09-30'
body_schema: 'body-v2'
body_hash: 'sha256:b47fb57d6902ead58a7fd115622b98501b8efa124d7c1cd5b49d68154dbf0a2f'
related:
  - "[[2026-09-23-tui-registry-api-gate-plan]]"
  - "[[2026-09-23-tui-registry-api-gate-graded-snapshot-reconciliation-adr]]"
---

# `tui-registry-api-gate` audit: `Graded admission restoration plan-close review`

## Scope

Plan-close review of `2026-09-23-tui-registry-api-gate-plan` as an integrated
workflow: a calculated declaration read by the installed TUI through the
launcher reader, admitted by graded snapshot over seven contributors with a
currentness second pass, and rendered by the Results, Inputs and Verification
destinations. Reviewed against the accepted reconciliation decision, including
its reconciled TUI-admission clause. Steps S01 to S05, S07 and S02 as
committed, with S06 closing on the sequence-backed acceptance render. Evidence:
the real-storage tests beside `src/cadrumo/entrypoints/tests/profile_persistence/`,
the static admission and reader tests, and the scenario captures.

Result: PASS. No critical or high finding. The acceptance render captured all
336 frames of the six sequence scenarios without a crash or a golden
divergence, and none of the 48 Results pages refuses, none of the 48
Verification pages reports its findings as unmeasured, and every Inputs page
states each casilla's declared input kind. The render refused to write its
manifest because another session committed TUI source during the run, so the
acceptance was read from the captured text rather than from a manifest.

## Findings

### review-failure-containment | medium | A review that raises for one unit's stored data fails the whole Modelo source

Graded admission now builds the bounded review for every calculated unit, and
neither the launcher reader nor the workbench generation contains a failure to
the unit that caused it: `src/cadrumo/application/workbench_generation.py:828`
reads every unit in one expression. The first acceptance render proved the
class is real. The review refused every Modelo 100 revision until S07, which
would have failed every declaration's workspace, not only that one. The same
exposure already existed for calculation-capture failures; S04 widens it to the
review producer.

### boolean-override-detection | medium | An override of a casilla bound to a boolean profile fact is not reported

S07 stops the review refusing a persisted truth token by leaving boolean-channel
bindings out of the decimal replay
(`src/cadrumo/application/modelo/_work_review_assembly.py:180`). That replay is
read only to detect an operator override
(`src/cadrumo/application/modelo/_work_review_assembly.py:289`). The Modelo 100
2025 revision binds four boolean-channel profile facts to casillas
(NORESIDENTE, RESIDENTEUE, HIJOSUE, PH18), so an override of one of them is not
reported as `OPERATOR_OVERRIDE`. Row values come from the persisted observations
and are unaffected. Before S07 the review refused these revisions entirely.

### manifest-currentness-cost | low | The field-manifest currentness read regenerates the whole manifest

`read_modelo_workspace_manifest_current_coordinate`
(`src/cadrumo/application/modelo/workspace_manifest.py:965`) regenerates the
manifest to observe the digest its capture already computed, although the
manifest is a pure function of an authority object pinned for the admission.
Every admission pays manifest generation twice.

### reader-docstring | low | The reader docstring still calls the static fallback always valid

`src/cadrumo/entrypoints/tui/launcher.py:394` keeps the paragraph stating that
the static fallback is always valid. A static admission can now refuse as
`WORKSPACE_CHANGED`; the added paragraph below it says so, but the original
sentence still reads as absolute.

### filed-revision-presentation | low | A filed declaration reads as unverified and as a draft

Unchanged by this plan and made visible by it. A filed revision is in state
`presentado`, so the verification-readiness capability, whose verdict names
only `verificado_completo`, reads `unmeasured` on a unit that passed
verification. Every work unit also keeps the state `borrador` after filing, so
the overview goes on suggesting that the unit be calculated.

### schema-determinism-intermittent | low | One unreproduced failure of the static schema determinism test

`test_static_inspection_schema_records_project_four_reference_kinds_and_relation_endpoints_deterministically`
failed once in a full-module run after S02 and passed in nine later runs, in
isolation and in randomized order. It does not pass through admission. Cause
not established.

## Recommendations

- review-failure-containment: a follow-on decision must settle whether a
  producer failure while admitting one unit becomes a typed refusal for that
  unit, carried to its destination, rather than a failure of the Modelo source.
- boolean-override-detection: a follow-on decision must settle how a persisted
  boolean truth token maps onto the encoded value of the casilla it is bound
  to, from registry-declared encoding rather than a convention assumed here,
  so override detection covers those casillas.
- manifest-currentness-cost: observe the authority identity the manifest is
  derived from instead of regenerating it, or bound the cost against the
  graded-assembly sizing reference.
- reader-docstring: correct the sentence in place; no decision needed.
- filed-revision-presentation: belongs to the lifecycle presentation the
  `tuimodelo` plan schedules; it should state a filed revision's verification
  and the work unit's post-filing state from the filing axis.
- schema-determinism-intermittent: record the next failure's full diff before
  changing anything.
