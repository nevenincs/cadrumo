---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S04'
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
     The S04 and 2026-07-06-cross-period-prorrata-plan placeholders are machine-filled by
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
     The implement the pure precedence-ladder resolver (authorised/inicio provenance > carried prior definitive > no value) returning the in-force provisional percentage or None, never a fabricated default, with unit tests over the ladder and ## Scope

- `src/aeat/domain/prorrata_register/tests/test_prorrata_register.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# implement the pure precedence-ladder resolver (authorised/inicio provenance > carried prior definitive > no value) returning the in-force provisional percentage or None, never a fabricated default, with unit tests over the ladder

## Scope

- `src/aeat/domain/prorrata_register/tests/test_prorrata_register.py`

## Description

- Implement the pure LIVA art. 105 precedence-ladder resolver `resolve_provisional_percentage` in `src/aeat/domain/prorrata_register/__init__.py`, returning a typed `ProrrataProvisionalResolution`.
- Rank provenances by the single declared ladder (`AEAT_AUTORIZADA` > `INICIO_ACTIVIDAD` > `CARRIED_PRIOR_DEFINITIVA`); ignore candidates that carry no provisional percentage; resolve absence to a visible unresolved state (both fields `None`), never a fabricated default.
- Add the unit-test suite in `src/aeat/domain/prorrata_register/tests/test_prorrata_register.py` covering the ladder tiers, the tie-break, the unresolved case, the entry-coupling invariants, and the aggregate lookups.

## Outcome

18 unit tests pass (`-n0`). The ladder returns the highest-precedence provenance's percentage; the no-candidate and regime-only cases resolve to `None`, proving the "no fabricated 100%" invariant. `ruff` / `ruff format` / `ty` clean; `domain-not-application` import contract KEPT (the domain register imports only `core`).

## Notes

Validator errors raised inside pydantic surface as `pydantic.ValidationError` (the custom `ProrrataRegisterValidationError` is a `ValueError` subclass pydantic wraps), so the tests assert `pydantic.ValidationError` with a message match, mirroring the `bienes_inversion` roundtrip convention.
