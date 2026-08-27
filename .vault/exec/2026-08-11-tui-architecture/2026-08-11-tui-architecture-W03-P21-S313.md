---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:5b103419bf8bc176791a71792c3c993d681b96555b240b8292aad5b8464301c8'
step_id: 'S313'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Give modelo 347 claves C, D and E a shared filer-role axis: each gates on the FILER's own institutional role rather than any transaction property, and the populations RD 1065/2007 art. 31.1's last paragraph (Ley 49/1960 propiedad horizontal, LIVA art. 20.tres carácter social entities), art. 31.2 (LGT art. 94.1/2 statutory information-duty entities, and the narrower entidades integradas en Administraciones publicas subset) and art. 31.3 (third-party fee collectors) name are disjoint from each other and from EntityType's tax-selection axis, but no classification for any of them exists anywhere in the profile domain; add one closed role axis in core/ naming each population as its own member, thread TaxpayerProfile access into the shared invoice-observation resolver (precedent: active_taxpayer_profile() in _m303_regimen_simplificado_scope.py), and prove the axis is orthogonal to EntityType by asserting the tax-selection consequence is unchanged (a LEGAL_ENTITY colegio profesional keeps its tax, its modelos and its calendar); S308 and S309 both depend on this Step and do not duplicate the axis

## Scope

- `the shared modelo 347 filer-role axis`
- `TaxpayerProfile access threaded into the invoice-observation resolver`
- `and an orthogonality proof against EntityType`

## Changes

- `M` `src/cadrumo/core/aggregation.py` -- new `ThirdPartyDeclarationRole` StrEnum, five members each traced to its own textual population (art. 31.1 last paragraph split into `PROPIEDAD_HORIZONTAL_ENTITY`/`SOCIAL_CHARACTER_ENTITY`, art. 31.2 into `STATUTORY_INFORMATION_DUTY_ENTITY`/`PUBLIC_ADMINISTRATION_ENTITY`, art. 31.3 into `THIRD_PARTY_FEE_COLLECTOR`), docstring stating the orthogonality with `EntityType` explicitly
- `M` `src/cadrumo/core/__init__.py` -- lazy-export wiring for the new type
- `M` `src/cadrumo/core/external_constants.py` -- new `M347_CLAVE_C_THRESHOLD_EUR` (300,51 EUR, arts. 32.c/33.4) beside `M347_THRESHOLD_EUR`, grounded to apply alongside it, not instead of it
- `M` `src/cadrumo/domain/deadlines/_models.py` -- new `TaxpayerProfile.declaration_roles: frozenset[ThirdPartyDeclarationRole]` field, defaulting empty, docstring stating the orthogonality with `entity_type`
- `M` `src/cadrumo/domain/deadlines/tests/test_taxpayer_model.py` -- `declaration_roles` added to the fully-populated roundtrip fixture; new `TestThirdPartyDeclarationRoleOrthogonality` proving every role membership (singly and combined) leaves `derive_tax_route` unchanged for both `LEGAL_ENTITY` and `NATURAL_PERSON` profiles -- the real production tax-route derivation, not merely field independence
- `M` `src/cadrumo/application/invoices/_source_resolver.py` -- new `_m347_filer_declaration_roles(bucket_id)` loader, mirroring the established bucket-scoped profile-fact pattern (`m111_no_retenciones_periods_for_bucket`): fails closed to an empty role set on `ProfileNotFoundError`. Not yet called from `_m347_invoice_observation` -- no clave reads the fact yet, and calling it unread would be dead work on every invoice plus an unused parameter; S308/S309 wire the call when they add the first real consumer
- `M` `src/cadrumo/application/invoices/tests/test_source_resolver.py` -- new `test_m347_filer_declaration_roles_fails_closed_to_empty_for_a_profile_absent_bucket`, exercising the real repository's `ProfileNotFoundError` path (no mock)
- `verify:` `uv run --no-sync python -c "from cadrumo.domain.calculations.registry.authority import bundled_authority; bundled_authority()"` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/deadlines/tests/test_taxpayer_model.py src/cadrumo/application/invoices/tests/test_source_resolver.py -q -m unit` -> `pass` (76 passed)

## Notes

Deliberately narrower than "thread TaxpayerProfile access into the resolver"
could be read: the loader function exists, is real (repository-backed, not
mocked), and is tested, but it is NOT called from `_m347_invoice_observation`
in this Step. Threading an unused parameter into that function ahead of any
clave that reads it would be dead plumbing -- an unused argument today, and
exactly the "built ahead of its consumer" shape this campaign has flagged
repeatedly. S308 (clave C) and S309 (claves D/E) each call
`_m347_filer_declaration_roles(context.bucket_id)` from inside
`_m347_invoice_observation` the moment they add their own clave logic; that
wiring is a two-line change at that point, not a rebuild.

Separately, and more importantly: `declaration_roles` has no operator-input
path yet. `taxpayer_profile_from_mapping` (the wizard-facts-to-TaxpayerProfile
projection) does not read or populate it, so no real persisted profile can
carry a non-empty value today -- only a directly-constructed `TaxpayerProfile`
in a test can. This Step does not build that input path (a wizard question
with locale strings in four languages, a `SetupFieldSpec` registration, and a
canonical-mapping key), because it was not in its scope and is substantial
enough to warrant its own decision. Until it exists, claves C, D and E will
correctly return `None` for every real filer even after S308/S309 land their
classification logic, because the fact they gate on can never be set. This is
recorded here as an open dependency for whichever of S308/S309 lands first,
or a follow-up Step, rather than left implicit.
