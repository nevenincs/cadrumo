---
tags:
  - '#reference'
  - '#assets-core'
date: '2026-09-21'
modified: '2026-09-21'
body_schema: 'body-v2'
body_hash: 'sha256:c2c3dad4120ab96fb695000b9c8c6bd255f19f745e886b8386f56f9be7efec7f'
related:
  - "[[2026-08-23-amortization-casilla-mapping-adr]]"
  - "[[2026-07-01-iva-bienes-inversion-regularizacion-adr]]"
---

# `assets-core` reference: `IRPF asset ownership and integration contracts`

Source state `bbbc47407efa8fb41ff16126c9fb08aea11ee723`. This reference maps the
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

Transaction identity is content-derived from amount, narrative, provider ID,
and value date in `src/cadrumo/domain/transactions/models.py:89`. Direction,
invoice linkage, classification, allocation, and categories are not identity
inputs. An ID-changing edit creates a replacement while preserving the prior
ID in `TransactionEditLineageEntry` through
`src/cadrumo/application/ledger/actions_manual.py:884` and
`src/cadrumo/domain/transactions/lineage_models.py:229`. Asset evidence must
therefore retain the acquisition transaction ID observed by the asset revision
and follow canonical lineage for current-state invalidation; it must not mint a
second transaction identity.

Calculation identity already covers source IDs, provenance, inputs, and outputs
in `src/cadrumo/domain/modelos/calculation_revision.py:171`, with identical
reruns reusing the content-derived revision contract at
`src/cadrumo/domain/modelos/calculation_revision.py:715`. Filing identity is
derived from work unit, calculation revision, actor, and member identity in
`src/cadrumo/domain/modelos/filing_record.py:223`; idempotent re-file returns the
current record in `src/cadrumo/application/modelo/filing_actions.py:297`. No
existing identity covers asset revision, schedule fingerprint, tax year,
covered period, projection role, and claim amount together.

M130 casilla 02 currently has one owner:
`src/cadrumo/domain/calculations/registry/ledger_renta_gastos_pago_fraccionado_bindings.py:56`.
It sums cumulative year-to-date outgoing observations in
`src/cadrumo/application/aggregation/renta_gasto_ledger.py:210`. The generic
source resolution contract rejects duplicate binding or casilla ownership at
`src/cadrumo/application/aggregation/source_resolution_operations.py:296`.
Asset depreciation must therefore enter the existing expense owner as an
additional typed component, not register a second owner or replace ordinary
expenses.

Current transaction allocation maps BUSINESS to one and MIXED to the stored
business percentage in
`src/cadrumo/application/aggregation/business_proportion.py:28`. Usage-ratio facts
must equal that percentage when both exist under
`src/cadrumo/domain/usage_ratios/model.py:249`. Home-office censo facts expose
only office area divided by total area at
`src/cadrumo/application/user_profile/censo_sync.py:408`; no existing asset owner
stores construction, land, or legal ownership basis. Applying both transaction
business percentage and a new home allocation would allocate twice.
