---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S18'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-vocabulary-cli-cohesion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S18 and 2026-06-26-binding-vocabulary-cli-cohesion-plan placeholders are machine-filled by
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
     The Verify W03.P05 no-shift: run pytest --collect-only -q clean, the affected aggregation / sede / oracle test modules green, and assert the calc/registry-tier anchor carriers (CasillaObservation, RegistryModeloObservation) and all role-suffixed *ObservationRequirement / *Repository / *Store / *Protocol names were NOT renamed and ## Scope

- `src/aeat/application/aggregation/tests`
- `src/aeat/domain/calculations/registry/tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Verify W03.P05 no-shift: run pytest --collect-only -q clean, the affected aggregation / sede / oracle test modules green, and assert the calc/registry-tier anchor carriers (CasillaObservation, RegistryModeloObservation) and all role-suffixed *ObservationRequirement / *Repository / *Store / *Protocol names were NOT renamed

## Scope

- `src/aeat/application/aggregation/tests`
- `src/aeat/domain/calculations/registry/tests`

## Description

- Run `pytest --collect-only -q` over the aggregation, registry, sede, declaracion, and borrador test surfaces; observe clean collection (no import or collection errors).
- Run the affected aggregation / sede / oracle carrier test modules and observe all green.
- Assert the calc/registry-tier anchor carriers `CasillaObservation`, `RegistryModeloObservation`, and `OracleModeloObservation` were NOT renamed and remain defined in `_bindings.py`.
- Assert the role-suffixed families (`*ObservationRequirement`, `*ObservationRepository`, `*ObservationStore`, `*ObservationProtocol`, `*ObservationEnvelopePayload`) were NOT renamed and their stems are intact.

## Outcome

W03.P05 verified no-shift. Collect-only is clean (4019 tests collected, no errors). The affected carrier suites pass (341 passed across the retenciones, counterpart, retención-repository roundtrip, sede NIF-IVA, declaracion, and the two oracle modules). The anchor carriers and every role-suffixed `*Observation*` family name are unchanged, and the ledger / sede / oracle base carriers each carry a domain-discriminating prefix with no cross-tier class-name collision.

## Notes

W03.P05 closed as a verify-and-assert phase: the genuine bare-stem sede/inbound renames landed via peer relocation commits (recorded under `S16`); the ledger and oracle tiers required no rename (`S15`, `S17`). The two ledger carriers a stricter reading might further prefix are family-anchored and locale-WIP-blocked, deferred rather than family-de-syncing. No production code was modified in this phase.
