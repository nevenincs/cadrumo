---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:4aac9059281c32fa42d172e0ae2846fb64532c714c030a7409749f13022a31bf'
step_id: 'S309'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Give modelo 347 claves D and E a real source: both gate on the FILER's own institutional type rather than on any transaction property -- public administrations, political parties, unions, business associations, propiedad-horizontal and article 20.tres social entities, per RD 1065/2007 art. 31.2 and its cross-reference to LGT art. 94 -- and no taxpayer entity-type classification exists anywhere in the profile domain; add the closed classification to the taxpayer profile, add the separate transaction-level fact clave E additionally needs to distinguish a subvencion or ayuda from an ordinary payment, and prove each clave declares only for the filer types its article names

## Scope

- `the invoice and profile domain facts each clave requires`
- `the modelo 347 clave classifier`
- `the contraparte row bindings in both revisions`
- `and grounded per-clave classification tests`

## Changes

- `M` `src/cadrumo/domain/invoices/_models.py` -- new `Invoice.is_subvencion_ayuda` and `outside_economic_activity` fields, BOTH tri-state (`bool | None = None`): neither a silent `False` (under-declares) nor a silent `True` (over-declares) default is safe for either fact
- `M` `src/cadrumo/domain/invoices/tests/test_secure_storage_roundtrip.py` -- both new fields added to the strict roundtrip fixture and its assertions
- `M` `src/cadrumo/application/aggregation/_source_mesh.py` -- new `unclassified_declarant_role_fact` diagnostic reason
- `M` `src/cadrumo/application/invoices/_source_resolver.py` -- `_m347_operation_clave` classifies clave E (fact + `PUBLIC_ADMINISTRATION_ENTITY` role) and clave D (fact + membership in the new `_M347_CLAVE_D_ROLES` frozenset of all four disjoint filer roles), every fact checked with `is True` so an undeclared `None` never silently classifies either way; new `_m347_role_fact_advisories`, called from `resolve()`, surfaces a non-blocking advisory when a role-carrying filer's invoice leaves the relevant fact undeclared -- scoped to RECEIVED invoices for D (the article's own "adquisiciones" text) and any invoice for E's public-administration population
- `M` `src/cadrumo/application/invoices/tests/test_source_resolver.py` -- clave E tests updated for the tri-state default; new clave D discrimination tests (role+fact declares D, same role WITHIN activity stays A, fact alone without any of the four roles stays A) and two advisory tests (proportionate -- never fires for a role-less filer; fires for an undeclared fact and clears once declared)
- `verify:` `uv run --no-sync python -c "from cadrumo.domain.calculations.registry.authority import bundled_authority; bundled_authority()"` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/invoices/tests/test_source_resolver.py src/cadrumo/domain/invoices/tests/test_secure_storage_roundtrip.py -q -m unit` -> `pass` (54 passed)

## Notes

Rejected the option to scope D narrowly to `PROPIEDAD_HORIZONTAL_ENTITY`/
`SOCIAL_CHARACTER_ENTITY` alone on the premise those entities "typically
have no economic activity" -- the coordinating session's correction: Spanish
comunidades de propietarios commonly earn rooftop-antenna or premises-rental
income, so that premise is an empirical generalisation the law does not
make, and building D on it would have embedded a stereotype where art.
31.1/31.2 require a per-invoice fact. Built the fact for all four roles
instead.

Considered reusing `derive_taxpayer_files_economic_activity`
(`applicability.py:1101`) to avoid a new fact; rejected as a substitutability
trap -- it answers an IRPF-specific question (does this taxpayer file
actividad-económica pagos fraccionados) keyed to natural-person income
categories, and returns `None` for exactly D's population (comunidades,
public administrations), which carries no IRPF income categories at all.

The advisory fires per-invoice for every RECEIVED invoice a D-role filer
leaves undeclared (and every invoice for a public-administration filer's
undeclared subvención fact). This is proportionate to the population the
roles exist to cover (an empty role set never fires it), but a filer who
declares a D/E role and never sets either fact on any invoice will see one
advisory per qualifying invoice, every calculate run, until they do. Noted
here as an accepted design tradeoff per the coordinating session's explicit
instruction, not silently decided.
