---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:f0ec5a3f3288384c597246e2333179bc1a602dca1f23be449d7884fbbf7b416d'
step_id: 'S94'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Complete conditional-applicability assessment in the profile presentation contract for the cases W01.P02.S04 left classified as OPTIONAL rather than assessed: the multi-field IVA-regime trigger resolved through modelo_iva_profile_required_paths, and every repeatable section, so a field is reported not_applicable or applicable_required_missing on its real trigger instead of defaulting to optional

## Scope

- `src/cadrumo/application/user_profile/presentation.py and src/cadrumo/application/user_profile/tests/test_presentation.py`

## Changes

- `M` `src/cadrumo/application/user_profile/presentation.py`
- `M` `src/cadrumo/application/user_profile/tests/test_presentation.py`
- `verify:` `pytest src/cadrumo/application/user_profile/tests/test_presentation.py -m integration` -> `pass` (15 passed)

## Notes

Modelo-IVA block: resolved through the domain's own
`profile_claims_modelo_iva_block` (trigger: any of the block's real claiming
paths declared) and `modelo_iva_profile_required_paths` (which fields it then
obliges) -- no reimplemented claiming-path set. Repeatable sections: every
declared row of every repeatable section now reports its fields by static
schema requiredness (previously skipped entirely, so even an unconditionally
required repeatable-row field went unclassified); the one section with a
documented conditional rule, `attribution_entity_socios`, resolves its
`country_of_residence` field per row against that same row's own
`participe_clave` (`completeness.PARTICIPE_CLAVE_BEARING_COUNTRY`), proven
on real facts reaching `needs_applicability` (clave unanswered),
`applicable_required_missing`/`present` (clave 2), and `not_applicable`
(clave 1). Every other repeatable section still reports `OPTIONAL` for its
non-required fields -- correctly, since no conditional rule for them exists
anywhere in this package; that is not the narrowing this Step closes.
