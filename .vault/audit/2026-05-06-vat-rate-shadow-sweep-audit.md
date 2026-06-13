---
tags:
  - '#audit'
  - '#vat-rate-shadow-sweep'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-06-modelo-369-vat-centralization-audit]]'
  - '[[2026-05-06-modelo-369-vat-centralization-research]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `vat-rate-shadow-sweep` audit: `hardcoded-rate-literals-outside-the-registry`

## Scope

This is the second loop iteration of the Modelo 369 VAT centralization
audit. The first iteration (`vat-iva-surface-and-modelo-369-readiness`)
established that `aeat.domain.vat` is the centralized substrate but
that no committed modelo registry yet consumes it; recommendation 5 of
that audit deferred a literal-sweep across the codebase to confirm
that `registry/aeat/vat/rates.toml` is the only authority for VAT and
adjacent filing-grade rate values.

This audit runs that sweep. It enumerates every Python module under
`src/aeat/` that hardcodes a filing-grade rate value (VAT, IRPF
imputación, IRPF retention, or any other rate that owns legal truth)
and classifies each as a violation of the calculation-truth-registry
ADR's Decision 6 ("Forbid filing-grade legal values, thresholds, rates,
casilla mappings, formula dependencies, and validity windows in Python
modules"), an unrelated quantization helper, or a boundary-parser
dependency on a violation.

The sweep does not modify code; it produces the punch list the
centralization ADR must close before any Modelo 369 binding lands.

## Findings

### V-1. `aeat.domain.invoices._enums` carries Spanish IVA rates

`src/aeat/domain/invoices/_enums.py` defines `IvaRate` (a `StrEnum`
with members `RATE_0`, `RATE_4`, `RATE_10`, `RATE_21`, `EXEMPT`,
`NOT_SUBJECT`) and an immutable `_IVA_RATE_PERCENTAGES` mapping that
hardcodes the Decimal percentages: `RATE_4 → Decimal("0.04")`,
`RATE_10 → Decimal("0.10")`, `RATE_21 → Decimal("0.21")`. The helper
`iva_rate_percentage(rate)` exposes those Python-owned percentages.

Severity: **high**. This is a direct violation of ADR Decision 6.
Spanish IVA rate values live in Python rather than being looked up
through `registry/aeat/vat/rates.toml` and the `lookup_rate` substrate
helper. The enum values are also written into invoice records and
ledger lines, so the shadow propagates into persisted state.

The file's own docstring flags the drift: it warns that `RATE_5` (the
transient 2022-2024 rate) is "intentionally omitted" and that "if a
future workflow ingests pre-2025 data this enum will need to be
extended alongside `_IVA_RATE_PERCENTAGES`". That admission confirms
that historical drift is a known risk and that the canonical authority
should not live as a Python literal.

Consumers of `IvaRate` outside `aeat.domain.invoices`:
`aeat.domain.invoices._models` (the invoice-line schema), the invoices
test suite, and three review-application test modules
(`aeat.application.review.test_adapters`, `test_aggregator`,
`test_models`). The shadow's blast radius is therefore the entire
invoice-and-review chain.

### V-2. `aeat.domain.rental._aggregates` carries IRPF imputación rates

`src/aeat/domain/rental/_aggregates.py` defines two module-level
constants:

- `IMPUTACION_RATE_RECENT_REVISION: Decimal = Decimal("0.011")` (the
  LIRPF article 85 1.1 % rate that applies when the property's valor
  catastral was revised in the 10 prior ejercicios).
- `IMPUTACION_RATE_OLD_OR_NO_REVISION: Decimal = Decimal("0.02")`
  (the LIRPF article 85 2 % rate when no qualifying recent catastral
  revision exists).

A companion constant `CATASTRAL_REVISION_LOOKBACK_YEARS: int = 10`
captures the LIRPF article 85 lookback window.

Severity: **high**. These values are filing-grade IRPF rates and a
filing-grade lookback window. Their docstrings cite "LIRPF art. 85"
explicitly, confirming they are legal truth that the ADR forbids
encoding in Python.

The shadow is Modelo 100-adjacent rather than Modelo 369-adjacent, but
the architectural sin is identical and the centralization ADR must
sweep both surfaces. Modelo 369 cannot land while structurally similar
hardcoded rates persist elsewhere in the registry domain.

### V-3. `aeat.application.review._edit` accepts unconstrained rates

`src/aeat/application/review/_edit.py` defines a review-edit Pydantic
model whose `iva_rate` and `retention_rate` fields are typed as
`Decimal | None` rather than as `IvaRate | None` (or as a
registry-backed enum). The review path therefore accepts arbitrary
user-edit Decimal values, allowing review operations to write
non-canonical rate values into ledger records that bypass both the
`IvaRate` shadow (V-1) and the substrate's `VAT_RATE_TABLE`.

Severity: **medium**. This is not a new rate authority but a
boundary-leak: a user-driven review surface can introduce arbitrary
rate values into persisted state, defeating the integrity that the
centralized substrate exists to provide. The centralization ADR must
decide whether the review-edit input becomes registry-validated, gets
constrained to a closed enum, or remains free-form with explicit
downstream re-validation.

### V-4. `aeat.entrypoints.cli._invoice` parses CLI rate strings

Around line 116 of `src/aeat/entrypoints/cli/_invoice.py`, the CLI
import path maps user-typed rate strings to `IvaRate` enum names via
an inline literal: `{"21": "RATE_21", "10": "RATE_10", "4": "RATE_4",
"0": "RATE_0"}`.

Severity: **low**. This is a boundary parser converting CLI strings
into the V-1 enum and not an independent rate authority. The shadow
goes away once V-1 is migrated to a registry-backed lookup; the parser
becomes a thin function that delegates to `lookup_rate` or to a
registry-aware factory.

### V-5. Documentation-only mention is not a shadow

`src/aeat/domain/calculations/registry/_citation_blocklist.py` line 71
contains the string "RIRPF art. 100 has no sub-letter structure; the
19% rate is in art. 100.1." inside a citation-blocklist message.

Severity: **none**. This is a human-readable diagnostic message and
not a rate authority; the substring is not used to compute any
filing-grade value. No action required.

### V-6. Quantization helpers are not shadows

`Decimal("0.01")` literals appear in many modules
(`aeat.adapters.outbound.aeat.export._formats._deserialise`,
`aeat.adapters.outbound.aeat.export._formats._record_spec`,
`aeat.application.filing.reconciliation._reconcile`,
`aeat.application.filing._export`,
`aeat.domain.calculations.registry._formula_runtime`,
`aeat.domain.invoices._models`, `aeat.domain.invoices._service`,
`aeat.domain.profile.assets`, `aeat.domain.profile.inventory`,
`aeat.domain.rental._aggregates`).

Severity: **none**. These are rounding-quantization tolerances
(money-cent precision) and not rate authorities. They are the correct
pattern.

### M-1. No parallel Member State enumerations

The earlier audit confirmed `EUMemberState` is the single Member State
enumeration in the codebase. This sweep re-checked: `grep` for
`class .*Country`, `EU_STATES`, `MEMBER_STATES`, `EU_MEMBER` outside
`aeat.domain.vat` returned only the `aeat.domain.calculations.registry`
binding/export modules and the import-contract test, none of which
declare a parallel enum. Member State centralization is therefore
clean and stable; the centralization ADR can rely on `EUMemberState`
as the canonical source.

### M-2. Country validation at the invoice boundary remains shadow-prone

The earlier audit already flagged `aeat.domain.invoices._validators`
`validate_country_code` for accepting any ISO-3166 alpha-2 code
without anchoring to `EUMemberState`. This sweep did not find any
additional country-validation surfaces; the issue is bounded to the
invoice validator. The centralization ADR must decide whether the
validator narrows to `EUMemberState | OtherCountry` or whether the
invoice schema gains a separate `eu_member_state` field used by
Modelo 369 binding paths.

## Recommendations

The centralization ADR for Modelo 369 must include teardown work for
V-1 and V-2 in addition to the substrate extensions for OSS / IOSS
regimes. A foundation-only Modelo 369 slice that does not address
these shadows would leave the codebase with two parallel rate
authorities (the registry and `IvaRate`) and would block the
calculation-truth-registry ADR's Decision 6 from holding even for
Modelo 369's own bindings.

Concrete actions for the ADR:

1. Migrate `IvaRate` to a registry-backed enum / factory. The enum
   shape can stay (it gives Pydantic a closed taxonomy for serialised
   ledger lines), but the percentage mapping must come from
   `registry/aeat/vat/rates.toml` via `lookup_rate`. Update every
   consumer in `aeat.domain.invoices`, `aeat.application.review.*`,
   and the CLI invoice parser to call the substrate.
2. Migrate the rental imputación constants to
   `registry/aeat/legal/irpf.toml` (or a dedicated rental subset) as
   `LegalReference` and `ParameterDefinition` entries with citations
   to LIRPF art. 85, then expose them through the registry's parameter
   lookup. The Modelo 100 rental construct will own the consumption.
3. Constrain `aeat.application.review._edit`'s `iva_rate` field to
   the registry-backed enum so review operations cannot leak
   non-canonical rate values into ledger records.
4. Narrow `aeat.domain.invoices._validators.validate_country_code` to
   the closed `EUMemberState | OtherCountry` taxonomy, or add a
   dedicated `eu_member_state` field on invoice records that Modelo
   369 bindings consume.
5. After the migrations, run the literal-sweep again with the same
   patterns this audit used and confirm that the only remaining
   `Decimal("0.21")` / `Decimal("0.04")` / `Decimal("0.011")` /
   `Decimal("0.02")` literals in the codebase are tests that
   exercise the substrate or fixtures that document expected outputs.

The centralization ADR is now adequately scoped: it must address the
OSS / IOSS regime taxonomy (per the first-loop audit), the ledger ↔
modelo binding mechanism (per the research doc), and the V-1 / V-2
teardown plus V-3 / M-2 boundary tightening (per this sweep). Any
further loop iterations should examine the actual draft ADR rather
than the substrate or the source code.
