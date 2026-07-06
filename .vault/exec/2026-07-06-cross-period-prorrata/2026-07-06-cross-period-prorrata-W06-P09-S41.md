---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S41'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-period-prorrata with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S41 and 2026-07-06-cross-period-prorrata-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The promote `PRORRATA_REGULARIZACION` out of `DEFERRED_SOURCE_KIND_TARGETS` once `src/aeat/application/aggregation/_source_mesh.py` is owner-clean: enroll the resolver in the live mesh, remove the domain taxonomy deferred carve-out, and verify source-kind mesh parity plus the AEAT manual oracle and M303 prorrata advisory slices and ## Scope

- `src/aeat/application/aggregation/_source_mesh.py`
- `src/aeat/domain/calculations/registry/tests/test_binding_source_kind_taxonomy.py`
- `src/aeat/application/modelo/tests/test_binding_source_kind_mesh_parity.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# record the `PRORRATA_REGULARIZACION` real-source provisioning blocker

## Scope

- `.vault/exec/2026-07-06-cross-period-prorrata/2026-07-06-cross-period-prorrata-W06-P09-S41.md`
- `.vault/audit/2026-07-06-cross-period-prorrata-audit.md`
- `.vault/plan/2026-07-06-cross-period-prorrata-plan.md`

## Description

- Ran the required RAG grounding for `prorrata regularizacion live source mesh binding iva_compensation_annual_partition precedent` and a targeted selector/resolver follow-up.
- Re-read the S30 and S40 exec records, the rolling audit, and the S41 plan row before touching code.
- Confirmed `PRORRATA_REGULARIZACION` is still a deferred source kind in the source mesh and still carved out by the binding source-kind taxonomy test.
- Confirmed there is no `prorrata_regularizacion` registry binding, no selector contract entry, no binding selector registry enrollment, no live source resolver, and no application source-kind enrollment.
- Confirmed the Modelo 303 casilla 44 registry entries remain manual, the current 303 deductible-total projection does not consume casilla 44, and no Modelo 390 annual regularizacion binding target is provisioned.
- Declined the cosmetic patch of only removing `PRORRATA_REGULARIZACION` from deferred lists because that would orphan the enum and bypass real source provisioning.
- Reframed S41 as the blocker-reconciliation step and split the actual source promotion into W07 registry, resolver, enrollment, dependency-reconciliation, and close-review rows.

## Outcome

- S41 is complete as a blocker reconciliation and work-schedule correction.
- No production code or test code was changed.
- The actual live-source promotion remains open under W07, starting at `W07.P10.S42`.

## Notes

- Blocker: a correct promotion requires a typed selector contract, registry binding or bindings, a real resolver, enrollment in the application live source mesh, and parity/taxonomy/oracle/advisory tests in one coherent change.
- Additional blocker: the current source-resolution pass runs before registry calculation and does not receive the current casilla inputs or post-engine values needed to compute the prorrata regularizacion from current-year annual volumes and deductible totals.
- `src/aeat/application/aggregation/_source_mesh.py` still contains unrelated non-authored WIP for out-of-window diagnostics and was not edited.
- Verification passed: focused source-kind taxonomy, mesh parity, prorrata oracle, prorrata grounding, and M303 prorrata advisory pytest slice.
- Verification passed: `vault check features --feature cross-period-prorrata`.
- Verification passed: `vault check frontmatter --feature cross-period-prorrata`.
- The S41 plan row is checked only for this reconciliation; no source-kind promotion was claimed.
