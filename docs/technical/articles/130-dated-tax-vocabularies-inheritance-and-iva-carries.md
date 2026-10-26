# Dated tax vocabularies, inheritance, and IVA carries

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-130` · **Topic:** [Tax calculation domain](../topics/tax-calculation-domain.md)

<!-- preserved:article -->
## Scope and method

This chunk covers 19 registry-domain modules, 4,020 physical lines, 159,311 bytes, and 35,555 measured `o200k_base` proxy tokens. All seven bounded pages were read. Most modules project dated IRPF/IVA/IRNR vocabularies; the remainder govern keyed-family inheritance, IVA compensation carries, and ledger selector contracts. Static inspection only; no application code or tests were run and no source was changed.

## Dated tax vocabularies

The Modelo 210 income-type catalogue combines conceptual `TipoRentaIrnr` definitions with official two-character codes. It makes the split explicit: each official code must be either projected to a declared concept or explicitly marked fetch-gated, never both, and the official code inventory must equal the union of those two sets. Projected codes retain the rate legal-reference and grounding-tier metadata; fetch-gated codes carry a description but no invented concept or rate. The catalog also exposes the pension, EU/EEA resident and real-estate semantic tokens through the same fact. M210 code and concept catalogue (`src/cadrumo/domain/calculations/registry/irnr_tipo_renta.py`) Code projection surface (`src/cadrumo/domain/calculations/registry/irnr_tipo_renta.py`)

IRPF catalogues project income categories and estimation/special regimes with descriptions, legal refs, tax regime and applicable models. The activity-income category is required to carry both activity-gate and payment-model metadata; special regimes may declare a positive time window, exposed by the impatriado helper. IVA catalogues similarly project categories and named membership projections, deduction kinds/evidence authorities, cash-accounting treatments, flow directions and settlement sides, legal exemption/service vocabularies, regimes, rate kinds and rate roles. These token sets are dated facts rather than locally authored enums at consumer boundaries. Most readers validate declared order, unique tokens, pointer membership and referenced sets before returning typed projections. IRPF income categories (`src/cadrumo/domain/calculations/registry/irpf_income_categories.py`) IRPF regime vocabulary (`src/cadrumo/domain/calculations/registry/irpf_regimes.py`) IVA category projection (`src/cadrumo/domain/calculations/registry/iva_category_catalogue.py`) IVA deduction authorities (`src/cadrumo/domain/calculations/registry/iva_deduction_catalogue.py`)

IVA flow entries map each declared flow to a set of settlement sides and require distinct semantic pointers for issued, received, recipient reverse charge and supplier reverse charge. The “no settlement” token is kept outside the settlement-side vocabulary. Rate-kind projections check positive tiers against the full rate-kind set and keep zero/exempt outside the positive list. Rate-role declarations require exactly one default and prevent that default from superseding the tier default. The IVA regime projection validates its default, `NO_APLICA`, semantic pointers and self-assessment subset against the declared regime list. IVA flow semantics (`src/cadrumo/domain/calculations/registry/iva_flow_catalogue.py`) Rate-kind rules (`src/cadrumo/domain/calculations/registry/iva_rate_kind_catalogue.py`) Rate-role default (`src/cadrumo/domain/calculations/registry/iva_rate_role_catalogue.py`) IVA regimes (`src/cadrumo/domain/calculations/registry/iva_regime_vocabulary.py`)

The shared IVA schema-vocabulary source resolves one mapping fact into immutable entries and reuses projections keyed by authority incarnation/date with weak references and a cache bound. This avoids rebuilding the same schema map while isolating generations. The cash-accounting reader uses the active candidate fact scope during registry validation rather than reaching back into a published authority artifact. One temporal point merits validation in caller review: `require_registry_declared_iva_flow_direction` resolves at `today_madrid()` because it accepts no effective-date argument; confirm that candidate validation is meant to check the present-date token, particularly when compiling historical fact windows. Shared IVA vocabulary authority/cache (`src/cadrumo/domain/calculations/registry/iva_schema_vocabulary_source.py`) Scoped vocabulary resolution (`src/cadrumo/domain/calculations/registry/iva_schema_vocabulary_source.py`) Cash-accounting vocabulary (`src/cadrumo/domain/calculations/registry/iva_cash_accounting_vocabulary.py`)

## IVA carry and family semantics

The annual compensation-partition provider fixes the four quarterly source periods and four canonical Modelo 303 compensation-state casillas. Its output token identifies last-period compensation, generated-not-in-last-period compensation, or prior-year credit applied; the schema encodes the shared FIFO partition rather than asking each 390 output to declare unrelated source sets. The iva-wallet carve-out is revision-exact for the listed Modelo 303 carry binding; reuse of the same binding ID elsewhere does not inherit the exception. Annual compensation selector (`src/cadrumo/domain/calculations/registry/iva_compensation_annual_partition_bindings.py`) Exact wallet carry coordinates (`src/cadrumo/domain/calculations/registry/iva_wallet_carry_targets.py`)

`KeyedFamilySpec` is the central policy table for identity, inheritance mode, period scoping, restatement/drop eligibility and source-reference defaults. It separates casilla continuity inheritance from ordinary keyed identity joins and from per-edition/full-copy families. Binding semantic identity includes provider kind, data type and value channel, so a successor cannot reuse a stable ID for a different semantic provider. `bound_family_source_refs` and `inline_family_source_default` add edition-level source defaults plus member additions once, while preserving a member's explicit source list as a full replacement. This shared contract gives the compiler and migration/delta consumers one inheritance vocabulary. Family policy model (`src/cadrumo/domain/calculations/registry/keyed_families.py`) Canonical inheritance census (`src/cadrumo/domain/calculations/registry/keyed_families.py`)

## Ledger selector boundaries

Shared ledger support closes income and IVA fact vocabularies and distinguishes taxable/gross measures from cash received and declared withholding. The shared validator permits only `sum`, uses strict provider-model narrowing, and applies source-kind, target-casilla and fact gates before binding build. The Modelo 151 impatriado provider requires an explicit fact and restricts its target to the base casilla; gross-income aggregation uses taxable base when available and gross otherwise, while cash-received aggregation always uses gross. The resolver is intentionally passed only Spanish-scoped observations: the application classifier owns foreign/unresolved source segregation, and this module does not independently re-enforce that jurisdiction. Ledger fact vocabulary (`src/cadrumo/domain/calculations/registry/ledger_binding_selector_support.py`) Shared build diagnostics (`src/cadrumo/domain/calculations/registry/ledger_binding_validation.py`) Impatriado selector (`src/cadrumo/domain/calculations/registry/ledger_impatriado_bindings.py`) Impatriado resolver (`src/cadrumo/domain/calculations/registry/ledger_impatriado_bindings.py`)

## Security, quality and limits

The principal trust boundary in this chunk is the selection of the dated fact authority and the upstream ledger classifier. Projection code is mostly pure and returns frozen records or read-only mappings; caches are generation-aware. IRNR official codes are described as two-digit codes but checked with `str.isdecimal()`, which admits non-ASCII decimal numerals; if canonical wire codes must be ASCII, that check should be narrowed. No ledger source fetch or IVA compensation arithmetic implementation is included in the assigned files, so those data pipelines and FIFO calculations are not independently assessed. No tests were run; findings describe static contracts and specific follow-up candidates.

## Coverage appendix

All 19 assigned files were read fully across seven bounded pages. Line counts use physical source lines.

- registry/irnr_tipo_renta.py (`src/cadrumo/domain/calculations/registry/irnr_tipo_renta.py`) — 1–351
- registry/irpf_income_categories.py (`src/cadrumo/domain/calculations/registry/irpf_income_categories.py`) — 1–195
- registry/irpf_regimes.py (`src/cadrumo/domain/calculations/registry/irpf_regimes.py`) — 1–350
- registry/iva_cash_accounting_vocabulary.py (`src/cadrumo/domain/calculations/registry/iva_cash_accounting_vocabulary.py`) — 1–171
- registry/iva_category_catalogue.py (`src/cadrumo/domain/calculations/registry/iva_category_catalogue.py`) — 1–283
- registry/iva_compensation_annual_partition_bindings.py (`src/cadrumo/domain/calculations/registry/iva_compensation_annual_partition_bindings.py`) — 1–138
- registry/iva_deduction_catalogue.py (`src/cadrumo/domain/calculations/registry/iva_deduction_catalogue.py`) — 1–218
- registry/iva_flow_catalogue.py (`src/cadrumo/domain/calculations/registry/iva_flow_catalogue.py`) — 1–366
- registry/iva_legal_vocabulary.py (`src/cadrumo/domain/calculations/registry/iva_legal_vocabulary.py`) — 1–160
- registry/iva_rate_kind_catalogue.py (`src/cadrumo/domain/calculations/registry/iva_rate_kind_catalogue.py`) — 1–183
- registry/iva_rate_role_catalogue.py (`src/cadrumo/domain/calculations/registry/iva_rate_role_catalogue.py`) — 1–156
- registry/iva_regime_vocabulary.py (`src/cadrumo/domain/calculations/registry/iva_regime_vocabulary.py`) — 1–258
- registry/iva_schema_vocabulary_source.py (`src/cadrumo/domain/calculations/registry/iva_schema_vocabulary_source.py`) — 1–152
- registry/iva_schema_vocabulary_tokens.py (`src/cadrumo/domain/calculations/registry/iva_schema_vocabulary_tokens.py`) — 1–43
- registry/iva_wallet_carry_targets.py (`src/cadrumo/domain/calculations/registry/iva_wallet_carry_targets.py`) — 1–76
- registry/keyed_families.py (`src/cadrumo/domain/calculations/registry/keyed_families.py`) — 1–403
- registry/ledger_binding_selector_support.py (`src/cadrumo/domain/calculations/registry/ledger_binding_selector_support.py`) — 1–96
- registry/ledger_binding_validation.py (`src/cadrumo/domain/calculations/registry/ledger_binding_validation.py`) — 1–106
- registry/ledger_impatriado_bindings.py (`src/cadrumo/domain/calculations/registry/ledger_impatriado_bindings.py`) — 1–315
<!-- /preserved:article -->
