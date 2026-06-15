---
tags:
  - '#exec'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S16'
related:
  - "[[2026-06-15-bindings-interface-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace bindings-interface-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S16 and 2026-06-15-bindings-interface-hardening-plan placeholders are machine-filled by
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
     The add silent-zero refusal tests per family asserting a positive unrouted observation raises an advisory rather than resolving to zero and ## Scope

- `src/aeat/application/modelo/tests/test_unrouted_observation_screen.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# add silent-zero refusal tests per family asserting a positive unrouted observation raises an advisory rather than resolving to zero

## Scope

- `src/aeat/application/modelo/tests/test_unrouted_observation_screen.py`

## Description

- Add registry-layer screen tests, one positive and one false-fire per family, using real registry fixtures (M100 expense slice, M130 income, M369 esquema-union) and real observations, no mocks.
- Renta expense: assert a 0199-routed deductible against a single-0186-binding revision is reported as unrouted, and that a zero-deductible observation (real protocol stand-in) is not flagged.
- Renta income: assert a casilla-03-routed income against the casilla-01-only bindings is reported, and that a zero-income observation is not flagged.
- OSS: assert an IT-destination line against the DE/FR bindings is reported, and that a zero-base-zero-IVA line is not flagged.
- Add an application-layer live-wiring test asserting the OSS resolver surfaces exactly one `unrouted_observation` advisory for an IT-destination candidate while still resolving the DE binding to zero (non-blocking).

## Outcome

Six registry-layer screen tests plus one application-layer live-wiring advisory test pass. Each asserts diagnostic/observation presence and absence and structure, never a hand-computed calc value.

## Notes

The renta-expense zero-deductible case uses a minimal structural pydantic stand-in satisfying the observation protocol because the production deductibility evaluator rejects a zero-gross fact at construction; this mirrors the existing `_IncomeObservation` stand-in pattern in the income binding test and exercises real protocol behaviour, not a mock.
