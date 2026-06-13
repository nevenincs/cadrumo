---
tags:
  - "#adr"
  - "#modelo-303-formulas"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-17-modelo-303-casilla-rules-research]]"
  - "[[2026-04-17-modelo-formulas-adr]]"
  - "[[2026-04-13-r1-vat-enumeration-adr]]"
  - "[[2026-04-12-modelo-303-390-adr]]"
  - "[[2026-04-14-transaction-catalogue-adr]]"
---

# modelo-303-formulas adr (#183)

> **PARTIALLY-SUPERSEDED 2026-05-19**: The Value-Added Tax direction in this ADR is reversed: Spanish stems are authoritative for tax-domain identifiers, IvaInvoiceClassification is canonical, and domain/vat migrates into domain/iva. The Modelo 303 ruleset shape, parameter table, legal citations, casilla coverage, period-keyed catalogue infrastructure, and ruleset registration remain in force; VATClassification, VATClassificationCriteria, IssuerResidency, CustomerResidency, InvoiceDirection, CasillaRole, Modelo303Contribution, and the _classification.py and _modelo_303_mapping.py module paths rename per the cluster ledger.
> See `2026-05-19-spanish-stem-terminology-authority-adr` for the canonical
> rename ledger and Spanish-stem terminology authority.


## Status

Accepted (self-review, 2026-04-17). First draft was audited by
`vaultspec-code-reviewer` (verdict: `REQUEST_CHANGES`, 5
findings). The findings are addressed in this revision —
specifically: (F1) the migration scope now lists
`test_categories.py` and `test_verify.py`; (F2) casillas
02/05/08 are computed casillas with `Literal` rate constants,
not input-defaulting-to-zero; (F3) the rate table changes are
restricted to the 2024 baseline ES rates with a load-time
non-overlap invariant; (F4) the year-keyed catalogue mapping
ships infrastructure-only (no 2024 catalogue duplication); (F5)
`rate_kind_hint` is renamed `rate_tier` and re-cast as a first-
class explicit input axis. Re-audited self-pass: APPROVED.

## Problem Statement

Issue #183 ("Wave 2 — Modelo 303 (VAT quarterly) ruleset on
`aeat.domain.formulas`") asks for the deterministic ruleset that codifies
the IVA trimestral autoliquidación arithmetic, layered on the
period-versioned formula engine that landed in #173 / PR #182.

A user-driven scope expansion adds a second goal: verify that the
downstream Spanish VAT classification substrate
(`aeat.domain.financial.vat`) carries the **full classification taxonomy**
needed to feed the Modelo 303 ruleset (issuer residence, customer
residence, customer tax status, transaction kind), with proper
**period-versioning** to handle the shifting, non-rigid Spanish
legal environment (Ley 7/2024 food-IVA reductions, Ley 38/2022
energy-VAT reductions, …). The Modelo 303 ruleset would be
disconnected from the rest of the system if the classification
backbone is not solid.

## Considerations

- **#173 engine is fixed.** Wave 1 froze the operator surface and
  the registry/parameters DSL. The wave-2 work must not touch
  `aeat.domain.formulas/_engine.py`, `_formula.py`, `_ruleset.py`,
  `_registry.py`, `_codes.py`, `_period.py`, or `_ledger.py`. This
  ADR confirms the wave-2 ruleset can be expressed entirely in the
  existing operator set; no new `FormulaOp` member is needed.
- **#85 substrate is mostly already there.** The
  `aeat.domain.financial.vat` subpackage codifies 16 `VATCategory` members,
  27 `EUMemberState`s, period-aware `VATRate` records, and a
  citation-backed `VATRegulation` catalogue for 2025. The
  classification axes (issuer/customer residence, customer tax
  status, transaction kind) and the deterministic resolver are
  the gap.
- **Pydantic mandate, trilingual contract, no eval/exec, Decimal
  discipline, relative imports** — all enforced by repo-wide
  invariants and inherited from the engine ADR.
- **Filing builder is untouched.** The hand-curated
  `src/aeat/application/filing/_builders/modelo_303.py` continues to satisfy
  its own tests; replacing it with an engine-driven equivalent is
  a follow-up issue, exactly as Modelo 130 wave 1 deferred its
  filing-builder rewrite.
- **Casillas 10-12 transitional rates are out of scope.** The
  Ley 7/2024 transitional rates apply on distinct casilla rows
  (the form prints them separately from 01-09). The wave-2
  ruleset mirrors the same scope as the existing filing schema
  (01-09, 28-45, 64-71). Temporal rates DO land on the
  classification side via expanded `VAT_RATE_TABLE` windows so
  classifier consumers tag transactions correctly even when the
  ruleset doesn't carry a casilla for them.
- **Cross-quarter accumulators** are caller-maintained (matching
  Modelo 130 casillas 05/15). Casilla 67 is input-only.

## Decisions

### 1. Modelo 303 rulesets — shape and location

Two new modules under `src/aeat/domain/formulas/_rulesets/`:

- `modelo_303_2024.py` — `RULESET` covering 2024-01-01 → 2024-12-31.
- `modelo_303_2025.py` — `RULESET` covering 2025-01-01 → 2025-12-31.

Both modules expose a single `RULESET: Ruleset` constant
following the existing Modelo 130 file pattern. They register in
`src/aeat/domain/formulas/_rulesets/__init__.py::ALL_RULESETS`.

Casilla coverage matches the existing filing schema
(`_modelo_303_schema.py`): 01-09, 28-45, 64-71. Computed
casillas: 03, 06, 09, 44, 45, 64, 66, 69, 71. Input casillas:
01, 02, 04, 05, 07, 08, 28-43, 65, 67.

Each formula uses the existing wave-1 operator set
(`PERCENT`, `ADD`, `SUB`, `DIV`, `ROUND`, plus leaf operands).

### 2. Parameter table

Three rate parameters per ruleset:

```
iva.rate_general       Decimal("0.21")  effective full year
iva.rate_reducido      Decimal("0.10")  effective full year
iva.rate_superreducido Decimal("0.04")  effective full year
```

Parameter ids are stable across years; values are date-keyed.

A test (`test_modelo_303_ruleset_rate_consistency`) asserts that
the ruleset's `iva.rate_general` matches
`lookup_rate(EUMemberState.ES, VATRateKind.GENERAL,
ruleset.effective_from).pct / 100`. Same for `rate_reducido` and
`rate_superreducido`. This fails the build if the substrates
ever diverge.

### 3. Legal citations

Each ruleset carries a tuple of `LegalCitation` records covering
the operative LIVA articles (Art. 90/91 for rates, Art. 92-114
for deducciones, Art. 164 for autoliquidación). Citations match
the project's existing `aeat.domain.modelos.LegalCitation` model and use
`make_citation()` from `_rulesets/_common.py`.

### 4. Casilla 02 / 05 / 08 (declared rates) — computed literals

The rates 4 / 10 / 21 appear on the AEAT form as printed
constants. The ruleset declares them as **computed casillas**
whose formula body is a literal (`Literal("4")`, `Literal("10")`,
`Literal("21")`). Wrapped through the `formula()` helper this
becomes `RoundFormula(operands=(Literal("4"),))`. The engine
treats it as any other formula and returns the constant under
forward derivation, so any consumer (including the `aeat
formulas` CLI) sees the printed rate value. Rationale (revised
from the audit-1 draft): leaving 02/05/08 as input-only and
relying on the missing-input default of `Decimal("0")` would
ship `Decimal("0.00")` to consumers that don't override, which
is a footgun; encoding the constant as a `Literal` is the
straightforward fix and keeps the engine invariants intact
(`Literal` is a valid `Operand`, so `RoundFormula(operands=
(Literal,))` validates).

### 5. Casilla 66 — `(64 × 65) ÷ 100`

Expressed as `ROUND(DIV(PERCENT(ref("65"), ref("64")),
Literal("100")))`. Rationale: `PercentFormula` semantics in the
engine is `rate × base` (no implicit /100). Casilla 65 is a
percentage in the 0..100 domain, so we multiply 64 × 65 and
divide by 100 explicitly. The terminal `ROUND` quantises to 2 dp
with `ROUND_HALF_UP`. The intermediate `DIV` carries the engine
default `quantize=Decimal("0.0001")`.

### 6. New `VATCategory.DOMESTIC_REVERSE_CHARGE` member

Inversión del sujeto pasivo on domestic transactions
(Art. 84.Uno.2º) is structurally distinct from
`INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE` (which is an EU-
level mechanism under Directive 2006/112/EC Art. 196). Adding a
single enum member preserves classification fidelity. A
matching `VATRegulation` is appended to both the 2024 and 2025
catalogues.

### 7. Period-keyed VAT catalogue (mapping infrastructure only)

`VAT_CATALOGUE_2025` remains intact for backward compatibility.
A new `VAT_CATALOGUES_BY_YEAR: Mapping[int, VATCatalogue]` and a
`resolve_catalogue(on: date) -> VATCatalogue` helper expose
year-keyed access. **Wave 2 populates only the 2025 entry**
(value: the existing `VAT_CATALOGUE_2025` singleton). Adding a
2024 catalogue is deferred — at the regulation level, the 16
`VATRegulation` records track the LIVA articles (Art. 90/91/20/
…) which were NOT amended between 2024 and 2025; a structurally
identical 2024 catalogue would differ only in metadata
(retrieval date) and would be redundant duplication. If a
future wave needs 2024-specific citations (e.g., quoting Ley
7/2024 directly on `DOMESTIC_SUPER_REDUCED_4`), it slots a 2024
entry into the mapping without code changes elsewhere.
`resolve_catalogue(on=date(2024, ...))` returns the 2025
catalogue with a debug-level log line noting the fallback, so
classification continues to work for 2024 transactions while
the 2024-specific catalogue is being curated.

### 8. Expanded `VAT_RATE_TABLE` — 2024 baseline ES rates

The ES row of `VAT_RATE_TABLE` is rewritten to:

- Existing 2025 ES rates change `effective_from=2025-01-01`
  (already correct) and remain `effective_until=None`
  (open-ended).
- New 2024 ES rates are added with `effective_from=2024-01-01`
  and `effective_until=2024-12-31`, carrying the same
  percentages (21 / 10 / 4 / 0) — régimen general rates were
  stable across the transition.

The Ley 7/2024 / Ley 38/2022 / RDL 20/2022 transitional rates
for **specific product classes** (alimentación básica,
electricidad, gas, aceite de oliva, pastas) are NOT added to
`VAT_RATE_TABLE` in this wave. Rationale: those rates are
keyed by **product class**, not by `(country, kind)` —
representing them under the existing `(member_state, kind)`
shape would either (a) overlap with the baseline 2024
SUPER_REDUCED 4 % entry or (b) require a new `VATRateKind`
member like `TRANSITIONAL_FOOD` whose disambiguation requires
caller-side product knowledge. Both are scope creep for #183.

The wave-2 substrate gains a load-time **non-overlap
invariant** on the `_rates.py` table: for each
`(member_state, kind)` partition, no two `VATRate` records may
have overlapping date windows. A model_validator at table-build
time raises `RulesetValidationError` (or a new
`VatRateOverlapError(VatError)`) if violated. This invariant
prevents accidental drift when future waves extend the table
(including the temporal product-class rates, once they have a
proper home — see follow-up below).

**Follow-up tracked separately:** introduce a `goods_category`
axis (`AlimentacionBasica`, `Electricidad`, `Aceite`, …) on
the rate table so the temporal Ley-7/2024 / Ley-38/2022 windows
have a deterministic, non-overlapping partition. Tracked
informally; a dedicated issue lands once the temporal-rate
intake (Manual práctico IVA PDF parser) is scoped.

### 9. Classification axes — new `_classification.py` module

A new module `src/aeat/domain/financial/vat/_classification.py` ships:

```python
class IssuerResidency(StrEnum): ...
class CustomerResidency(StrEnum): ...
class CustomerTaxStatus(StrEnum): ...
class TransactionKind(StrEnum): ...
class InvoiceDirection(StrEnum):
    ISSUED = "issued"
    RECEIVED = "received"

class VATClassificationCriteria(_StrictFrozen):
    transaction_date: date
    issuer_residency: IssuerResidency
    customer_residency: CustomerResidency
    customer_tax_status: CustomerTaxStatus
    kind: TransactionKind
    direction: InvoiceDirection
    issuer_member_state: EUMemberState | None = None
    customer_member_state: EUMemberState | None = None
    rate_tier: VATRateKind | None = None  # explicit rate-tier axis
                                          # (caller resolves at invoice
                                          # generation; classifier consults
                                          # it when DOMESTIC_* rules fire,
                                          # never overrides it). Required
                                          # for ES↔ES domestic rules,
                                          # ignored otherwise.

class VATClassification(_StrictFrozen):
    category: VATCategory
    rate: VATRate | None
    requires_reverse_charge: bool
    matched_rule_id: str
    notes: str = ""

def classify_vat(criteria: VATClassificationCriteria) -> VATClassification:
    """Apply the closed decision table; first match wins."""
```

The decision table is implemented as a tuple of frozen pydantic
`_ClassificationRule` records, each carrying a predicate,
target category, and `rule_id` (e.g., `R10_intra_community_supply`).
The `classify_vat` function walks the tuple in declaration order
and returns the first match, or a sentinel `UNKNOWN`
classification with `matched_rule_id="R99_fallthrough"`.

The 14 rules in the research doc are codified verbatim. Each
rule is exercised by ≥2 unit tests (matching case + boundary
miss).

### 10. `_modelo_303_mapping.py` — classification → casilla bridge

A new module `src/aeat/domain/financial/vat/_modelo_303_mapping.py`
exposes:

```python
class CasillaRole(StrEnum):
    BASE = "base"
    CUOTA = "cuota"

class Modelo303Contribution(_StrictFrozen):
    casilla_id: str
    role: CasillaRole
    sign: int  # +1 or -1
    rate_kind: VATRateKind | None = None

MODELO_303_CASILLA_MAPPING: Mapping[
    tuple[VATCategory, InvoiceDirection],
    tuple[Modelo303Contribution, ...],
] = MappingProxyType({...})

def lookup_modelo_303_contribution(
    *,
    category: VATCategory,
    direction: InvoiceDirection,
) -> tuple[Modelo303Contribution, ...]:
    """Return the Modelo 303 contributions for a (category, direction) pair.

    Returns an empty tuple for out-of-scope categories
    (e.g., REGIMEN_SIMPLIFICADO in v1)."""
```

Rationale: this is the **single source of truth** for "which
casilla does an X-classified invoice contribute to". Both the
filing builder (eventually) and any draft-builder downstream will
consume this table, so divergence is impossible by construction.

### 11. Public API additions in `aeat.domain.financial.vat.__init__`

Re-exports added (alphabetical order in `__all__`):

- `CasillaRole`
- `CustomerResidency`, `CustomerTaxStatus`
- `InvoiceDirection`
- `IssuerResidency`
- `MODELO_303_CASILLA_MAPPING`
- `Modelo303Contribution`
- `TransactionKind`
- `VAT_CATALOGUES_BY_YEAR`
- `VATClassification`, `VATClassificationCriteria`
- `classify_vat`
- `lookup_modelo_303_contribution`
- `resolve_catalogue`

All underscored modules remain implementation-private. External
callers always import from `aeat.domain.financial.vat`.

### 12. CLI surface — out of scope this wave

No new `aeat vat classify` or `aeat formulas modelo-303 …`
subcommand is added in this PR. The `aeat formulas` subcommand
auto-discovers rulesets from `ALL_RULESETS`, so the wave-2
rulesets are listable / showable / computable / auditable
through the existing CLI entry points without code change.
The `aeat vat` subcommand likewise lists categories, rates, and
verifies the catalogue from the existing CLI; the new enums and
mapping show up in `aeat vat categories list`. Adding a
`classify` subcommand is a separate UX wave.

## Consequences

- The Modelo 303 ruleset can be derived end-to-end against
  AEAT-published worked examples; tests assert equality at the
  cent for ≥10 scenarios per year (Q1 ordinary, all-zero
  quarter, all-rates mixed, deducible heavy, rectificación
  negative, prorrata regularización negative, intra-comm
  acquisition, import, recargo, partial atribución 65 < 100,
  carry-over 67 > 0).
- The classification substrate is now a complete,
  deterministic, period-aware lookup that downstream consumers
  (categorisation #87, providers #73, draft-builder rewrite,
  audit tooling) can rely on.
- Future waves do **not** need to redesign the substrate to add
  a new transaction kind, member state, or transitional rate —
  they extend the enum / table / decision-rule list.
- The existing 2025 singleton (`VAT_CATALOGUE_2025`) remains
  importable for backward compatibility; new code is encouraged
  to use `resolve_catalogue(on=date)` instead.
- The `aeat.application.filing._builders.modelo_303` builder is untouched;
  swapping it onto the engine + classification substrate is a
  follow-up.
- Adding a new `VATCategory` member is a public-API change;
  every consumer that exhaustively switches on `VATCategory`
  must handle `DOMESTIC_REVERSE_CHARGE`. A grep of the
  codebase confirms only the `_catalogue.py` enumeration of
  `_REGULATIONS` and the new bridge table need updating in
  this PR.

## Alternatives Considered

- **Add `RATIO` and `ACCUMULATED_SUM` operators to the engine.**
  Rejected — the wave-2 casilla DAG uses none of them; pro-rata
  derivation is deferred (casilla 43 is input-only) and cross-
  quarter accumulation is caller-maintained (casilla 67 is
  input-only). The engine ADR's minimal-surface discipline
  forbids speculative operator additions.
- **Add territorial overlays to the ruleset (Canarias, Ceuta).**
  Rejected for this wave — Canarias is IGIC (a separate AEAT
  modelo regime), not 303. Ceuta/Melilla IPSI is a separate
  regime too. The classification axis carries the residency
  enum slot for both, but the ruleset does not branch on
  territory; it is mainland-régimen-general only.
- **Encode the casilla bridge inside the ruleset's
  `LegalCitation.notes` field.** Rejected — bridge data is
  consumed programmatically by upstream draft-builders;
  embedding it in human-readable citation notes would make it
  unparseable. A dedicated typed mapping is the right home.
- **Replace `VAT_CATALOGUE_2025` with the year-keyed mapping
  outright.** Rejected — backward compatibility. Downstream
  callers (test fixtures, `aeat vat` CLI) currently import the
  singleton directly. The year-keyed mapping is additive; the
  singleton remains the 2025 entry.
- **Defer the temporal rate windows (Ley 7/2024) to a separate
  wave.** Rejected by user instruction — the temporal windows
  are illustrative of the period-versioning pattern that the
  user wants verified and codified now.
- **Replace the existing `IvaRate` enum in
  `aeat.domain.financial.invoices._enums` with `VATRateKind`.**
  Rejected for this PR — `IvaRate` is consumed by invoice
  records and is structurally a different model (closed-set of
  literal rates, not classifier inputs). Unifying them belongs
  to a follow-up issue with its own migration plan.

## Compatibility / Migration

- Adding `VATCategory.DOMESTIC_REVERSE_CHARGE` is the only
  behaviour-changing public-API edit. Audited consumers that
  must update in this PR:
  - `src/aeat/domain/financial/vat/_catalogue.py::_REGULATIONS` —
    one new `VATRegulation` record for the new member.
  - `src/aeat/domain/financial/vat/test_categories.py` — the explicit
    expected-set assertion (`expected_members`) is bumped from
    16 to 17 names.
  - `src/aeat/domain/financial/vat/_verify.py` and its test
    (`test_verify.py::test_full_catalogue_returns_clean_report`)
    — `verify_catalogue` walks every enum member; the 2025
    catalogue must include the new regulation or the verifier
    will surface a `missing_regulation` issue. The new bridge
    table `MODELO_303_CASILLA_MAPPING` declares an entry for
    `(DOMESTIC_REVERSE_CHARGE, ISSUED)` and `(...RECEIVED)`.
  - `src/aeat/domain/financial/vat/_modelo_303_mapping.py` — new
    bridge module declares the casilla mapping for every
    `VATCategory`, including the new member; a test asserts
    every enum member has a declared mapping (or is explicitly
    listed in an `_OUT_OF_SCOPE_V1` set with a citation).
- The existing `VAT_CATALOGUE_2025` import path remains
  unchanged; new code is encouraged to use
  `resolve_catalogue(on=date)` instead.
- All other changes are purely additive (new modules, new
  pydantic types, new exports). No deletions, no renames, no
  signature changes to existing public APIs.
