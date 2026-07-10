---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S12'
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
     The S12 and 2026-07-06-cross-period-prorrata-plan placeholders are machine-filled by
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
     The record the source observation identity on the seeded entry so the register stays cross-checkable against the prior filing forever after and ## Scope

- `src/aeat/application/prorrata_register/_seed.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# record the source observation identity on the seeded entry so the register stays cross-checkable against the prior filing forever after

## Scope

- `src/aeat/application/prorrata_register/_seed.py`

## Description

- Record the prior Modelo 303 observation identity on every seeded carried entry via `source_observation_ref`.
- Use the existing register convention `303:<source-year>:<source-period>` so the entry can be cross-checked against the prior filing later.
- Keep the S10/S11 seed and finding behavior unchanged.

## Outcome

- A clean 2025 Modelo 303 4T prior observation now seeds the 2026 carried entry with `source_observation_ref` equal to `303:2025:4T`.
- Scoped gates passed: `ruff check src/aeat/application/prorrata_register/_seed.py`, direct import smoke, real encrypted-repository smoke for the source identity, and `pytest -q src/aeat/domain/prorrata_register/tests/test_prorrata_register.py src/aeat/adapters/persistence/profile/tests/test_prorrata_register_roundtrip.py src/aeat/application/modelo/tests/test_prorrata_regularizacion_advisory.py` (`27 passed`).

## Notes

- The broader committed seed tests remain the dedicated `W02.P03.S13` row.
