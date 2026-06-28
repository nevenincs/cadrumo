---
tags:
  - "#plan"
  - "#modelo-303-formulas"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-17-modelo-303-formulas-adr]]"
  - "[[2026-04-17-modelo-303-casilla-rules-research]]"
  - "[[2026-04-17-modelo-formulas-adr]]"
---

# modelo-303-formulas plan (#183)

Date: 2026-04-17
Branch: `feature/183-modelo-303-formulas`
Worktree: `Y:/code/aeat-worktrees/feature-183-modelo-303-formulas`

## Goal

Ship the Modelo 303 ruleset on the `aeat.domain.formulas` engine for fiscal
years 2024 and 2025, plus the VAT classification substrate
extensions (issuer/customer residence, customer tax status,
transaction kind axes; period-keyed catalogue mapping infrastructure;
ES 2024 baseline rate table; classification → casilla bridge), in a
single PR per the user-expanded #183 scope.

Adheres to the audited ADR
`[[2026-04-17-modelo-303-formulas-adr]]`.

## Phases

The plan is split into six executable phases. Each phase is small
enough to be one or two commits; the executor runs them in
declared order. Each phase ends with `just lint && just test`
green on its scoped slice, and the final phase locks in the full
gates (`just lint && just typecheck && just test && just hooks`).

## Phase 1 — VAT substrate enum + record additions

Goal: add the new classification axes (`IssuerResidency`,
`CustomerResidency`, `CustomerTaxStatus`, `TransactionKind`,
`InvoiceDirection`), the new `VATCategory.DOMESTIC_REVERSE_CHARGE`
member, and the bridge types (`CasillaRole`,
`Modelo303Contribution`).

### Step 1.1 — Extend `VATCategory` enum

File: `src/aeat/domain/financial/vat/_schema.py`

- Append `DOMESTIC_REVERSE_CHARGE = "domestic_reverse_charge"` to
  `VATCategory`. Place it after `DOMESTIC_NOT_SUBJECT` to keep
  domestic items grouped; before `INTRA_COMMUNITY_SUPPLY`.
- Update the docstring to mention the new member.

### Step 1.2 — Update `test_categories.py`

File: `src/aeat/domain/financial/vat/test_categories.py`

- Bump `expected_members` to 17, including
  `DOMESTIC_REVERSE_CHARGE`.

### Step 1.3 — Add classification module

New file: `src/aeat/domain/financial/vat/_classification.py`

- Imports: `date`, `StrEnum`, pydantic v2, relative imports of
  `EUMemberState`, `VATCategory`, `VATRate`, `VATRateKind`,
  `_StrictFrozen` from `._schema`, `lookup_rate` from `._lookup`,
  `get_logger` from `...logging`.
- `IssuerResidency`, `CustomerResidency`, `CustomerTaxStatus`,
  `TransactionKind`, `InvoiceDirection` StrEnums per ADR §9.
- `CasillaRole(StrEnum)` with `BASE` and `CUOTA` members.
- `Modelo303Contribution(_StrictFrozen)` with `casilla_id: str`
  (`Field(min_length=2, max_length=4)`), `role: CasillaRole`,
  `sign: int` (`Field(ge=-1, le=1)`, model_validator rejects 0),
  `rate_kind: VATRateKind | None = None`.
- `VATClassificationCriteria(_StrictFrozen)` with the fields per
  ADR §9 — note the renamed `rate_tier`.
- `VATClassification(_StrictFrozen)` with the fields per ADR.
- `_ClassificationRule(_StrictFrozen)` carrying `rule_id: str`,
  `description: str`, plus a private `predicate: Callable`
  attribute. **Pydantic forbids non-serializable fields**; instead
  we keep predicates as module-level `def _r01_match(criteria)
  -> bool` functions and the `_RULES` tuple holds
  `(rule_id, description, predicate, target)` plain `NamedTuple`s
  — falling back to `typing.NamedTuple` is allowed here because
  `_RULES` is a private compile-time constant, not boundary-
  crossing data. Confirmed against the project's pydantic
  mandate (boundary-crossing data only).
- `classify_vat(criteria) -> VATClassification` walks `_RULES` in
  order, returns the first match's `VATClassification` (rate
  resolved via `lookup_rate` for ES domestic rules), or the
  `UNKNOWN` sentinel for fall-through.
- All 14 rules from research-doc §"Classification resolution
  table" implemented as `_rNN_*` predicates.

### Step 1.4 — Add Modelo 303 casilla bridge module

New file: `src/aeat/domain/financial/vat/_modelo_303_mapping.py`

- Imports per ADR §10.
- `MODELO_303_CASILLA_MAPPING` as a `MappingProxyType` over a
  literal dict literal keyed by `(VATCategory, InvoiceDirection)`.
- `lookup_modelo_303_contribution(*, category, direction)` returns
  the contributions tuple, or `()` for out-of-scope categories.
- `_OUT_OF_SCOPE_V1: frozenset[VATCategory]` documents which
  enum members deliberately have no mapping in v1
  (`REGIMEN_SIMPLIFICADO`, `RECARGO_EQUIVALENCIA`,
  `ERRONEOUS_INVOICE`, `UNKNOWN`).
- A module-level invariant runs at import time: every
  `VATCategory` member is either in
  `MODELO_303_CASILLA_MAPPING` keys (some direction) OR in
  `_OUT_OF_SCOPE_V1`. Raises `RuntimeError` at import if not.

### Step 1.5 — Update package `__init__.py`

File: `src/aeat/domain/financial/vat/__init__.py`

- Re-export everything per ADR §11. Update `__all__`.

### Step 1.6 — Tests

New file: `src/aeat/domain/financial/vat/test_classification.py`

- `@pytest.mark.unit`-marked tests for every rule + boundary
  miss + UNKNOWN fall-through (≥30 cases).
- A test asserts `classify_vat` is deterministic: same inputs
  return the same `matched_rule_id` and `category` across N
  invocations.

New file: `src/aeat/domain/financial/vat/test_modelo_303_mapping.py`

- Asserts every `VATCategory` member is either mapped or
  explicitly out-of-scope.
- Asserts every contribution carries a valid casilla id (min 2,
  max 4 chars), valid sign (±1), valid role.
- Asserts no `(category, direction)` key appears more than once
  (impossible by construction with dict, but explicit guard).

### Step 1.7 — Update existing `_catalogue.py` for the new member

File: `src/aeat/domain/financial/vat/_catalogue.py`

- Add a `_DOMESTIC_REVERSE_CHARGE` `VATRegulation` record with
  trilingual labels, `triggers_when` referencing Art. 84.Uno.2º,
  `iva_treatment` describing self-assessment + deduction,
  `declares_in_modelos=("303",)`, `requires_reverse_charge=True`,
  `requires_supplier_vat_id=True` (issuer always has NIF), and
  ≥2 citations (Art. 84.Uno.2º.f for construction; Art. 84.Uno.2º.c
  for waste; Art. 89 for rectification follow-on).
- Append to `_REGULATIONS` tuple.

### Step 1.8 — Verify end-to-end

```
just lint
uv run pytest src/aeat/domain/financial/vat -m unit
```

Both must pass. Coverage on the new code ≥80 %.

## Phase 2 — Period-keyed catalogue infrastructure

### Step 2.1 — Add `VAT_CATALOGUES_BY_YEAR` + `resolve_catalogue`

File: `src/aeat/domain/financial/vat/_catalogue.py`

- Below `VAT_CATALOGUE_2025`:

```python
VAT_CATALOGUES_BY_YEAR: Mapping[int, VATCatalogue] = MappingProxyType({
    2025: VAT_CATALOGUE_2025,
})

def resolve_catalogue(*, on: date) -> VATCatalogue:
    """Return the VATCatalogue effective on ``on``.

    Falls back to the closest available year (currently 2025) with
    a debug log line if no exact-year catalogue is defined.
    """
```

- Logging: `aeat.core.logging.get_logger(__name__).debug(...)` on
  fallback. No `print`.

### Step 2.2 — Tests

File: `src/aeat/domain/financial/vat/test_catalogue.py` (extend
existing).

- Test `resolve_catalogue(on=date(2025, 6, 1))` returns the 2025
  catalogue.
- Test `resolve_catalogue(on=date(2024, 6, 1))` returns the 2025
  catalogue (fallback).
- Test the mapping is read-only.

## Phase 3 — VAT rate table 2024 baseline + non-overlap invariant

### Step 3.1 — Refactor ES rate definitions

File: `src/aeat/domain/financial/vat/_rates.py`

- Add `_EFFECTIVE_FROM_2024 = date(2024, 1, 1)` and
  `_EFFECTIVE_UNTIL_2024 = date(2024, 12, 31)`.
- Update `_rate(...)` helper to take optional `effective_from` /
  `effective_until` instead of using a module-level default.
- Replace `_ES_RATES` with two-tuple union of 2024 (bounded) +
  2025 (open-ended). The 2024 rates have
  `effective_until=_EFFECTIVE_UNTIL_2024`. The existing 2025
  rates retain `effective_from=date(2025, 1, 1)` and
  `effective_until=None`.
- Add `_assert_no_overlap(rates)` function called at import time
  for each `(member_state, kind)` partition. Raises
  `VatRateOverlapError` (new error type) on violation.

### Step 3.2 — Add `VatRateOverlapError`

File: `src/aeat/domain/financial/vat/errors.py`

- `class VatRateOverlapError(VatError):` with a docstring
  citing the ADR.

### Step 3.3 — Tests

New file: `src/aeat/domain/financial/vat/test_rates_temporal.py`

- `lookup_rate(EUMemberState.ES, VATRateKind.GENERAL,
  date(2024, 6, 15)).pct == Decimal("21")` (2024 baseline).
- `lookup_rate(EUMemberState.ES, VATRateKind.GENERAL,
  date(2025, 6, 15)).pct == Decimal("21")` (2025 baseline).
- Boundary tests: `lookup_rate(... date(2024, 12, 31))` returns
  the 2024 record; `date(2025, 1, 1)` returns 2025.
- Test the overlap guard: build a synthetic table with two
  overlapping ES GENERAL records and assert it raises
  `VatRateOverlapError`.

### Step 3.4 — Update existing rate tests

File: `src/aeat/domain/financial/vat/test_rates.py`

- The existing assertion that `lookup_rate(ES, GENERAL,
  date(2025, 6, 1)).pct == 21` continues to pass.
- Add coverage for the new 2024 records.

## Phase 4 — Modelo 303 ruleset modules

### Step 4.1 — `modelo_303_2025.py`

New file: `src/aeat/domain/formulas/_rulesets/modelo_303_2025.py`

- Pattern: copy structure from `modelo_130_2025.py`.
- Imports: `date`, `Decimal`, `ModeloCode` from `...models`,
  `ParameterTable`, `ParameterValue`, `Ruleset` from
  `.._ruleset`, helpers from `._common`, `LegalCitationSource`
  from `...models`.
- `_EFFECTIVE_FROM = date(2025, 1, 1)`,
  `_EFFECTIVE_TO = date(2025, 12, 31)`.
- `_CITATIONS` — tuple of 4 `LegalCitation`s (Art. 90, Art. 91,
  Art. 164, RD 1624/1992 Art. 71).
- `_CASILLAS` — 25-tuple covering 01-09, 28-45, 64-71, with
  trilingual labels and the per-casilla `computed` flag and
  `legal_basis` reference.
- `_FORMULAS` — 12-tuple covering computed casillas 02, 03, 05,
  06, 08, 09, 44, 45, 64, 66, 69, 71. Casillas 02/05/08 are
  literal-rate formulas (`formula(casilla_id="02", ...,
  body=lit("4"))` etc.); 03/06/09 are
  `percent(param("iva.rate_*"), ref("01"|"04"|"07"))`; 44 is
  `add_op(ref("29"), ref("31"), ...)`; 45 is
  `sub_op(add_op(ref("03"), ref("06"), ref("09")), ref("44"))`;
  64 is `add_op(ref("45"), lit("0"))` (workaround: `ADD`
  requires min 2 operands, so we add a literal zero); 66 is
  `div_op(percent(ref("65"), ref("64")), lit("100"))`; 69 is
  `sub_op(ref("66"), ref("67"))`; 71 is `add_op(ref("69"),
  lit("0"))` (same workaround).
- _Note on 64/71 workaround:_ `AddFormula.operands` enforces
  `min_length=2`, so a "pass-through" cannot be a bare `AddFormula`
  with one ref. The cleanest available workaround in the
  wave-1 operator surface is `add_op(ref("X"), lit("0"))`. The
  alternative is `max_op(ref("X"), ref("X"))` — equally valid
  but less readable. `add_op(ref, lit("0"))` it is. The terminal
  `ROUND` quantises to 2 dp regardless.
- `_PARAMETERS` — `ParameterTable` with three entries:
  `iva.rate_general` = `Decimal("0.21")`,
  `iva.rate_reducido` = `Decimal("0.10")`,
  `iva.rate_superreducido` = `Decimal("0.04")`. Each parameter
  has one date-bounded value covering the full year.
- `RULESET = Ruleset(...)` with `ruleset_id="modelo_303.2025"`,
  `modelo=ModeloCode.MODELO_303`, etc.

### Step 4.2 — `modelo_303_2024.py`

New file: `src/aeat/domain/formulas/_rulesets/modelo_303_2024.py`

- Mirror of 2025 module with `_EFFECTIVE_FROM = date(2024, 1, 1)`
  and `_EFFECTIVE_TO = date(2024, 12, 31)`.
- Re-import the 2025 module's `_CASILLAS` and `_CITATIONS`
  (they are stable across years), the way `modelo_130_2025.py`
  re-imports from `modelo_130_2024.py`. To avoid an import
  cycle, the 2024 module declares the shared `_CASILLAS` and
  `_CITATIONS` first; the 2025 module re-imports them.
- Same parameter set, same percentage values.

### Step 4.3 — Register both rulesets

File: `src/aeat/domain/formulas/_rulesets/__init__.py`

- Import `MODELO_303_2024` and `MODELO_303_2025` and add to
  `ALL_RULESETS`.
- Update `__all__`.

### Step 4.4 — Unit tests for ruleset loading

New file: `src/aeat/domain/formulas/_rulesets/test_modelo_303_ruleset.py`

- Round-trip: both rulesets validate at import time.
- Period bounds match the file constants.
- `evaluation_order()` is deterministic.
- A registry-resolution test: `get_registry().resolve(
  ModeloCode.MODELO_303, on=date(2024, 6, 1))` returns the 2024
  ruleset, on `date(2025, 6, 1)` returns 2025.
- Cross-substrate consistency:
  ```python
  for kind, param_id in (
      (VATRateKind.GENERAL, "iva.rate_general"),
      (VATRateKind.REDUCED, "iva.rate_reducido"),
      (VATRateKind.SUPER_REDUCED, "iva.rate_superreducido"),
  ):
      rate = lookup_rate(EUMemberState.ES, kind, on=ruleset.effective_from)
      param_value = ruleset.parameters.resolve(param_id, on=ruleset.effective_from)
      assert param_value == rate.pct / Decimal("100")
  ```
  Run for both 2024 and 2025.

### Step 4.5 — Engine derivation tests

New file: `src/aeat/domain/formulas/_rulesets/test_modelo_303_2025.py`

- ≥10 worked-example scenarios, each `Engine.derive(ruleset=
  MODELO_303_2025, inputs={...}).entries` asserted at the
  cent. Scenarios:
  1. **All-zero quarter** — every input = 0, every computed
     casilla = 0.00. Final 71 = 0.00.
  2. **General-only ordinary** — base 07 = 10000.00, every
     other input = 0; expect 09 = 2100.00, 45 = 2100.00,
     64 = 2100.00, 66 = 2100.00 (default 65=100), 69 = 2100.00,
     71 = 2100.00.
  3. **Mixed rates** — 01 = 1000.00, 04 = 2000.00, 07 = 5000.00;
     expect 03 = 40.00, 06 = 200.00, 09 = 1050.00, 45 = 1290.00,
     71 = 1290.00.
  4. **Heavy deducible** — General devengado 1000.00, deducible
     enumerated to 1500.00 (29 + 31 = 1500); 45 = -500.00,
     71 = -500.00.
  5. **Negative rectificación** — 40 = -200.00 (negative
     rectification); 44 reflects the negative.
  6. **Intra-comm acquisition** — 36 base = 5000.00, 37 cuota =
     1050.00 (self-assessed at 21%); both feed into 44; expect
     consistent flow.
  7. **Import** — 32 base = 3000.00, 33 cuota = 630.00;
     consistent.
  8. **Partial state attribution** — 65 = 50.00; 66 = 64 / 2.
  9. **Carry-over compensation** — 67 = 1000.00, 71 reduced
     accordingly.
 10. **Boundary rounding** — 07 = 333.33; 09 = 70.00 (333.33 ×
     0.21 = 70.0... → ROUND_HALF_UP to 70.00). Verify the
     terminal ROUND.

- Plus an **audit_against** test: feed the inputs + computed
  values, expect zero discrepancies.
- Plus an **audit_against** divergence test: feed the inputs +
  a wrong computed value, expect a `Discrepancy` for the
  affected casilla.

### Step 4.6 — Engine derivation tests (2024)

New file: `src/aeat/domain/formulas/_rulesets/test_modelo_303_2024.py`

- A subset of the 2025 scenarios re-targeted at the 2024
  ruleset (since rates are identical, expected values match).
  Plus a **cross-year parity** test: derive the same inputs
  against both rulesets and assert ledger equality at the
  cent.

### Step 4.7 — Filing-builder cross-check (sanity)

Optional but inexpensive: a colocated test under
`src/aeat/domain/formulas/_rulesets/test_modelo_303_vs_filing.py` that
materialises one input set, runs `Engine.derive` AND the
existing `Modelo303Builder.build`, and asserts the engine's
ledger value matches the builder's `FilingValue` for every
overlapping casilla. Catches accidental drift.

## Phase 5 — Documentation + audit artifacts

### Step 5.1 — Vault audit record

File: `.vault/audit/2026-04-17-modelo-303-formulas-audit.md`

- Records the ADR audit verdict + remediation summary.

### Step 5.2 — Exec records

Files under `.vault/exec/2026-04-17-modelo-303-formulas/`:

- `2026-04-17-modelo-303-formulas-phase1-summary.md`
- `2026-04-17-modelo-303-formulas-phase2-summary.md`
- … etc per phase.
- One `…-phase{N}-{step}.md` per executed step, lightweight.

(Note: the executor agent generates these as it goes.)

## Phase 6 — Lint, type-check, full test suite, commit, PR

### Step 6.1 — Run gates

```
just lint
just typecheck
just test
just hooks
```

All must pass. If `just hooks` fails on staged files, fix the
offender and re-run; do NOT use `--no-verify`.

### Step 6.2 — Commit

Conventional commit:

```
feat(formulas): Modelo 303 (VAT trimestral) ruleset on aeat.domain.formulas (#183)

Adds period-versioned rulesets for fiscal years 2024 and 2025 covering
the régimen general casillas (01-09, 28-45, 64-71). Extends
aeat.domain.financial.vat with classification axes (issuer/customer
residence, customer tax status, transaction kind), period-keyed
catalogue mapping infrastructure, ES 2024 baseline rate table
records, and a deterministic VATCategory→Modelo303 casilla bridge.

Refs: #183, #182 (parent engine PR).
```

### Step 6.3 — PR

```
gh pr create --title "feat(formulas): Modelo 303 (VAT trimestral) ruleset on aeat.domain.formulas (#183)" --body "..."
```

PR body:
- Summary of casilla coverage + the substrate extensions.
- Cross-link to #183 and #173 / #182.
- Reference the ADR + research + plan vault paths.
- Test plan checklist.

## Risks + mitigations

| Risk | Mitigation |
| ---- | ---------- |
| Adding `DOMESTIC_REVERSE_CHARGE` breaks downstream consumers (exhaustive matches). | Audited via grep — no exhaustive `match` exists. The two consumers (`test_categories.py`, `_catalogue.py` `_REGULATIONS` enumeration) are updated in the same PR. |
| `add_op(ref, lit("0"))` workaround for casillas 64/71 (pass-through) is ugly. | Documented in the file's docstring; the engine's terminal `ROUND` makes the value semantically equivalent to a bare ref. Alternative is to extend the engine with a `PassthroughFormula` operator — explicitly out of scope per the engine ADR's minimal-surface discipline. |
| Cross-substrate rate consistency test ties the ruleset to `aeat.domain.financial.vat` import (creates a module-level dependency). | The test imports both modules; runtime ruleset code uses only `param("iva.rate_*")` references. No production cycle is introduced. |
| 2024 rate window boundaries (Dec 31 → Jan 1) might trip a leap-year edge case (2024 was a leap year). | All windows use explicit ISO-8601 dates; the date arithmetic in the engine and `lookup_rate` uses `<=` / `>=` against `date` objects, no day-of-year math involved. |
| Casillas 28-43 are mostly-input bases that get defaulted to 0; consumers might expect them to surface validation errors. | The wave-1 engine applies the missing-input contract uniformly; surfacing per-casilla `required` validation belongs to the filing builder layer (already implemented for the existing builder). Out of scope for #183. |

## Test plan summary

After Phase 4:
```
uv run pytest src/aeat/domain/formulas/_rulesets -m unit
uv run pytest src/aeat/domain/financial/vat -m unit
```

After Phase 6:
```
just test
just lint
just typecheck
just hooks
```

All must report green. Coverage on the new code ≥80 %; the
project floor is 60 %, so the new modules cushion that.

## Out-of-scope reminders

- No edits to `aeat.domain.formulas/_engine.py`, `_formula.py`,
  `_ruleset.py`, `_codes.py`, `_registry.py`, `_period.py`,
  `_ledger.py`. Wave-1 engine is frozen.
- No edits to `aeat.application.filing._builders.modelo_303` (the existing
  hand-curated builder). Replacement is a separate issue.
- No new operator (`RATIO`, `ACCUMULATED_SUM`) added to
  `FormulaOp`.
- No `aeat vat classify` CLI subcommand. CLI surface is
  unchanged.
- No 2024 catalogue duplication — only the `VAT_CATALOGUES_BY_YEAR`
  mapping infrastructure is added.
- No temporal product-class rates (Ley 7/2024 food, Ley 38/2022
  energy) added to the rate table — they belong to a follow-up
  with a `goods_category` axis design.
