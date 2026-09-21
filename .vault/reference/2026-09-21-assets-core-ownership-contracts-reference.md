---
tags:
  - '#reference'
  - '#assets-core'
date: '2026-09-21'
modified: '2026-09-21'
body_schema: 'body-v2'
body_hash: 'sha256:05e451b9eff8568a2f90707b7c9d7b5896285a6eb7bc5edf81ad20d51deb6b62'
related:
  - "[[2026-08-23-amortization-casilla-mapping-adr]]"
  - "[[2026-07-01-iva-bienes-inversion-regularizacion-adr]]"
---

# `assets-core` reference: `IRPF asset ownership and integration contracts`

Source state `8c3a40fecffcd98be5684dce4859c186e8a74d31`. This reference maps the
existing acquisition, persistence, calculation, filing, and frontend owners
that the new IRPF activity-asset capability must extend without duplicating.

## Summary

Invoice identity and linked transactions are defined in
`src/cadrumo/domain/invoices/models.py:126` and
`src/cadrumo/domain/invoices/models.py:272`. Stable transaction identity,
business allocation, usage-ratio identity, and the existing IVA investment
link are defined in `src/cadrumo/domain/transactions/models.py:89`,
`src/cadrumo/domain/transactions/models.py:427`, and
`src/cadrumo/domain/transactions/models.py:700`. Supported acquisition and
evidence writes are coordinated by
`src/cadrumo/application/ledger/actions_manual.py:115`; encrypted evidence is
owned by `src/cadrumo/adapters/persistence/profile/purchase_invoice_evidence.py:27`.

Canonical rounding is owned by `src/cadrumo/core/money/rounding.py:1` and
period semantics by `src/cadrumo/core/period.py:358`. The encrypted multi-year
register pattern is `src/cadrumo/adapters/persistence/profile/bienes_inversion.py:45`.
Namespace declaration and enrollment are shared seams at
`src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py:61` and
`src/cadrumo/adapters/persistence/storage/namespace_registry.py:81`.

Typed source enrollment is centralized in
`src/cadrumo/domain/calculations/registry/binding_provider_registration.py:445`.
Route ownership and collision checks live in
`src/cadrumo/application/modelo/calculation_route.py:111` and
`src/cadrumo/application/modelo/calculation_route.py:269`; source-mesh
execution is `src/cadrumo/application/modelo/calculation_actions.py:654`.
M130 and direct-estimation expenses are owned by
`src/cadrumo/application/aggregation/modelo_bindings_renta_expenses.py:48`,
`src/cadrumo/application/aggregation/modelo_bindings.py:493`, and
`src/cadrumo/application/aggregation/renta_gasto_ledger.py:154`.

Amortization-labelled categories are currently full-deductible in
`src/cadrumo/_data/registry/aeat/facts/0064-categories-profile.toml:2749` and
`src/cadrumo/_data/registry/aeat/facts/0064-categories-profile.toml:2921`.
The 2025 mapping routes them to Modelo 100 casilla 0208 at
`src/cadrumo/_data/registry/aeat/facts/2025/mapping/0090-2025-modelo-100-first-slice-expense-routing-mapping.toml:63`.
The authoritative asset source must therefore refuse or exclude this competing
path rather than becoming a second sum.

CLI composition is `src/cadrumo/entrypoints/cli/_app_ledger_command_specs.py:1`;
the nearest register pattern is
`src/cadrumo/entrypoints/cli/_bienes_inversion_cli.py:61`. TUI route and
destination ownership are closed in
`src/cadrumo/entrypoints/tui/ledger/models.py:34` and
`src/cadrumo/entrypoints/tui/ledger/routes.py:78`.

No existing IRPF activity-asset schedule owner or consumer was found in these
bounded traces. A dedicated IRPF asset domain with paired application,
profile-persistence, typed-provider, and aggregation owners fits the live
boundaries. Identity, history revisions, M130 collision semantics, mixed-use
allocation, CLI token, and namespace key remain decisions rather than code facts.
