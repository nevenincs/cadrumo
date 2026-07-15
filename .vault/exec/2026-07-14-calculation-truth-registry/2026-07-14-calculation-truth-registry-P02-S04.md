---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S04'
related:
  - "[[2026-07-14-calculation-truth-registry-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace calculation-truth-registry with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S04 and 2026-07-14-calculation-truth-registry-plan placeholders are machine-filled by
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
     The Build the Modelo 100 base reductions, minimums, and bracket calculation chain against BOE/AEAT worked examples and ## Scope

- `src/cadrumo/_data/registry/aeat/modelos/100/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Build the Modelo 100 base reductions, minimums, and bracket calculation chain against BOE/AEAT worked examples

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/100/`

## Description

- Surveyed the Modelo 100 2024 revision through the validated registry authority (not a directory listing) and established that the base-reductions, minimos and state/autonomic bracket calculation chain is already BUILT: the escala/minimo/cuota-integra formulas exist and compute end-to-end. The legacy plan's "substantially unbuilt" annotations are stale (dated two months before this work); the 2024 audit explicitly deferred independent confirmation of the Modelo 100 residual to this pass.
- Reframed the residual per the verification-grounding rule: the base/minimo/bracket casillas computed correctly but were only engine-reconciled, not independently grounded against an AEAT authority. Closed that gap by adding a bundled manual worked-example oracle and a parity test.
- Grounded the chain against the AEAT Manual practico de Renta 2024, Parte 1, Capitulo 15, "Ejemplo practico: calculo de las cuotas integras estatal y autonomica" (don A.B.C., residente en Aragon). Fed the manual's givens at the nearest raw-input leaves (base liquidable general 23.900 via casilla 0102, base liquidable del ahorro 2.800 via casilla 0429, single-filer profile yielding the LIRPF art. 57 base minimo 5.550) and let the live engine compute the whole chain forward.
- Confirmed the engine reproduces every manual subtotal verbatim: cuota escala estatal 2.667,75 (0528), autonomica de Aragon 2.621,89 (0529), cuota integra general estatal 2.140,50 (0532), autonomica 2.094,64 (0533), cuota integra estatal 2.406,50 (0545), autonomica 2.360,64 (0546), plus minimo personal y familiar 5.550 (0519/0520).
- Added the oracle payload `modelo-100-2024-cuotas-integras-escala-aragon.json`, the parity test `test_m100_2024_cuotas_integras_escala_aragon_manual_worked_example.py` (grounded reproduction + a residence-CCAA anti-tautology check proving the autonomic tariff is consulted while the state tariff stays CCAA-invariant + an enrollment/independently-grounded-fraction check), and enrolled the eight casillas in both `externally_grounded_casilla_ids` and `reconcile_when_present_casilla_ids` of the `modelo-100-2024-reconcile-when-present` verification expectation.

## Outcome

The Modelo 100 2024 base-reduction / minimo / state-and-autonomic-bracket chain is now independently AEAT-grounded, not merely engine-reconciled. Gates run green: the new parity/anti-tautology/enrollment tests (3 passed), the symmetric external-oracle honesty gate `test_external_oracle_grounding_enrolled.py`, the verification-expectation source-tier tests (6 passed), the registry authority load/validation tests (7 passed), and `pytest --collect-only -q` on the registry test tree (2980 collected, clean). No existing Modelo 100 parity test regressed.

## Notes

- The base/minimo/bracket formulas were pre-existing; this Step added independent oracle grounding rather than authoring new computation, which is the honest residual once the chain was confirmed built. This matches the pattern of the four Modelo 100 2024 manual-worked-example parity tests already in the tree.
- The manual presents base liquidable general/ahorro and minimo as givens; the scenario injects the two bases at identity leaves and derives the minimo (5.550) from a single-filer profile, so the grounded casillas are the escala/cuota RESULTS the engine computes, never hand-fed figures.
- Two Modelo 100 minimo-descendientes profile bindings (`renta-2024-profile-minimo-descendientes-estatal` / `-autonomico`) are not auto-seeded by the scenario harness (they are not PROFILE-source bindings); the scenario supplies both at 0 for a single filer with no descendientes.
