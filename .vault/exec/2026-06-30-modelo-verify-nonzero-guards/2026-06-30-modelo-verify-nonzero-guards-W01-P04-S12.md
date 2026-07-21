---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-07-17'
step_id: 'S12'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
---

# Author the modelo-714-cuota-integra-implica-total-cuota-integra ADVISORY predicate implies_nonzero(["patrimonio.cuota-integra", "patrimonio.total-cuota-integra"]) with legal_refs ley-19-1991:art-30, creating the verification_expectations directory on the 2021-y-siguientes revision -- the base-liquidable and cuota-a-ingresar edges are explicitly NOT authored here

## Scope

- `src/aeat/_data/registry/aeat/modelos/714/revisions/2021-y-siguientes/verification_expectations/0001-verification_predicates.toml`

## Description

- Confirm casilla 29 (`patrimonio.cuota-integra`, computed via the art. 30 escala formula) and casilla 40 (`patrimonio.total-cuota-integra`, manual transcription) both already carry `ley-19-1991:art-30` legal grounding and resolve against the bundled BOE corpus.
- Create the `verification_expectations` directory under the 2021-y-siguientes revision (it did not previously exist on this revision).
- Author a new `0001-verification_predicates.toml` fragment declaring the `modelo-714-cuota-integra-implica-total-cuota-integra` ADVISORY predicate, expression `implies_nonzero(["patrimonio.cuota-integra", "patrimonio.total-cuota-integra"])`, grounded in `ley-19-1991:art-30`.
- Explicitly scope out the base-imponible-to-base-liquidable and total-cuota-integra-to-cuota-a-ingresar edges per the ADR's SAFE-edge-only decision; those remain deferred to Wave W02.
- Add the `application.modelo.findings.modelo_714_cuota_integra_implica_total_cuota_integra` operator-facing finding message to all four locale catalogues (en, es, ca, hu) via the locale CLI, mirroring the existing M131/M200/M151 advisory message style.

## Outcome

The verification predicate is registered on the 2021-y-siguientes revision and resolves cleanly through `RegistryValidator`: the registry-build legal-refs and casilla-existence checks pass, and the predicate loads off the validated snapshot with the expected `predicate_id`, `expression`, `finding_kind`, and `legal_refs`. Confirmed via the registry-shape and gate-behaviour tests authored in `W01.P04.S13` and `W01.P04.S14`.

## Notes

The riskier M714 edges (base-imponible to base-liquidable; total-cuota-integra to cuota-a-ingresar) are deliberately not guarded in this Step -- they carry meaningful false-positive risk from the minimo exento and limite conjunto mechanics and are tracked for a grounded decision in Wave W02 Phase P06, not silently dropped.
