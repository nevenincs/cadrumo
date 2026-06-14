---
tags:
  - '#exec'
  - '#legal-grounding-centralization'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S04'
related:
  - "[[2026-06-14-legal-grounding-centralization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace legal-grounding-centralization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S04 and 2026-06-14-legal-grounding-centralization-plan placeholders are machine-filled by
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
     The F1: wire resolve_reduccion to the dormant _resolve_tier_reduccion_rate registry reader and ## Scope

- `constant becomes documented fallback`
- `prove parity against tier oracle tests`
- `src/aeat/domain/fincas/_tier_resolver.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# F1: wire resolve_reduccion to the dormant _resolve_tier_reduccion_rate registry reader

## Scope

- `constant becomes documented fallback`
- `prove parity against tier oracle tests`
- `src/aeat/domain/fincas/_tier_resolver.py`

## Description

- Add `_with_registry_rate(template, period_year, tier_id)` to `_tier_resolver.py`:
  it sources the tier rate from `_resolve_tier_reduccion_rate` (the previously
  dormant registry reader) and returns the frozen template unchanged when the
  registry rate equals the documented rate (identity preserved), or a `model_copy`
  carrying the registry rate when they differ.
- Route the four genuine four-tier dispatch returns through it in
  `resolve_reduccion`: TIER_90 → `tier-90`, tier_70 (public-admin / joven) →
  `tier-70`, TIER_60_REHAB → `tier-60`, TIER_50 → `tier-50`. Left the grandfathering
  (`_PRE_AMENDMENT`, `_DT_38`) and forfeit (`_FORFEIT_LAU_17_6`) resolutions on their
  documented constants — distinct provisions, not the four-tier rates.
- Add three causality proofs to `test_threshold_registry_grounded.py`: a parametrized
  test that `_with_registry_rate` overrides a deliberately-wrong (0.99) template with
  the real registry value; an identity test (matching rate returns the same singleton);
  and a qualifying-share-preservation test for the joven co-tenant override.

## Outcome

The previously dormant `_resolve_tier_reduccion_rate` now has a live production caller,
making the Modelo-100 `renta-<year>-rental-reduccion-rate-tier-{50,60,70,90}` parameter
the causal authority for the deductible percentage. Verified all registry values
(2020–2025) equal the inline constants (0.50/0.60/0.70/0.90), so the wiring is
parity-preserving; 185 fincas tests pass (including the tier dispatch and the 3 new
causality proofs); `ruff` clean. Closes F1 and the dormant-resolver shape flagged by
two independent swarm agents and carried unclosed from the May renta-scope audit.

## Notes

The causality proof is real-behavior (it reads the actual registry parameter and asserts
`_with_registry_rate` corrects a wrong template rate to the registry value) — not a mock
or monkeypatch. If the wiring is ever reverted to return the inline singleton, the
override test fails. No divergent registry value exists today (every supported year
matches the constant), so the override test uses a deliberately-wrong in-test template to
exercise the override branch without authoring a fixture registry.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
