---
tags:
  - '#adr'
  - '#rental-income-hardening'
date: '2026-04-29'
modified: '2026-04-29'
related:
  - "[[2026-04-29-rental-income-hardening-research]]"
  - "[[2026-04-28-modelo-100-renta-full-calc-reference]]"
  - "[[2026-04-27-modelo-100-renta-full-calc-adr]]"
---



# `rental-income-hardening` adr: per-finca + per-contract register, Ley 12/2023 tier auto-resolver, art. 23.1.f amortización 3% ledger | (**status:** `accepted`)

## Problem Statement

The PR-#448 Modelo 100 Anexo C surface lands the full LIRPF arts.
22-24 + 85 ruleset for ejercicios 2024 / 2025 / 2026 with caller-
supplied aggregates on every numeric casilla (0061 ingresos, 0066
gastos, 0072 amortización, 0078 reducción art. 23.2, 0085
imputación). Per the research artefact, the post-Ley 12/2023 four-
tier reducción (50/60/70/90 %), the multi-year art. 23.1.f
amortización ledger, and the art. 85 imputación each depend on per-
finca + per-contract metadata that the project does not yet model.
Kent currently has to look up the right tier himself and compute the
amortización across years by hand, with no audit trail of which
contract triggered which tier. This ADR commits to a per-finca +
per-contract register with engine-derived Anexo C casilla
aggregates, an explicit tier-resolver applying the BOE priority
order, and a multi-year amortización ledger with a per-finca cost-
basis cap.

## Considerations

- BOE primary source for the tier framework: Ley 12/2023, de 24 de
  mayo, disposición final segunda, BOE-A-2023-12203 (BOE núm. 124,
  páginas 71525-71526). The four tiers and their literal trigger
  conditions are reproduced verbatim in the research artefact §2;
  the priority order (90 → 70 → 60 → 50, highest applicable wins) is
  BOE-explicit through the recurring "no cumpliéndose los requisitos
  de las letras anteriores" formula.

- Two effective dates apply: the law is in force from 2023-05-26 for
  the housing-law side, but the IRPF amendment (apartado 2 art. 23 +
  DT 38ª) takes effect 2024-01-01 per disposición final novena.
  Filings of ejercicio 2023 use the prior flat 60 % regardless of
  contract date; filings of ejercicio 2024 + onwards apply the new
  tier framework only to contracts celebrated since 2023-05-26 and
  apply DT 38ª (= flat 60 %) to older contracts.

- LIRPF art. 23.1.f remains "3 por ciento sobre el mayor del coste
  de adquisición o del valor catastral de la construcción". The
  project ruleset already cites the rule correctly; the gap is the
  multi-year ledger.

- The per-tenant qualifying-share on tier 70-b-1 (joven inquilino in
  zona tensionada) is a non-trivial split: BOE allows the 70 %
  reducción to apply only on the share of rendimiento neto
  attributable to qualifying co-tenants. The resolver must therefore
  return both the tier identifier and a `qualifying_share` fraction.

- LAU art. 17.6 (rent cap for new contracts in declared zonas
  tensionadas where the landlord is a gran tenedor) is a non-tier
  forfeit condition: contracts that violate art. 17.6 lose the
  reducción entirely. The resolver dispatch must check this before
  emitting any tier amount.

- The procedural cap (reducción only on rendimiento declared in an
  autoliquidación submitted before AEAT verification) is enforced at
  the M100 import boundary, not at the resolver level — the resolver
  computes what the law allows; the import path applies the
  procedural cap when the input filing carries an
  `under_verification` flag.

- The merge of `feature/216-bank-import-persistence` into this branch
  brings SQLAlchemy 2 + alembic + the encrypted-column substrate
  (`EncryptedString`, `EncryptedJSON`) + the `Repository[RecordT]`
  pattern. Three exemplar repositories already exist (Modelo,
  Portal, CorpusArtifact). Path B (SQLite) is fully feasible.

- The issue body §2 explicitly chooses "SQLite via existing
  `aeat.adapters.persistence.storage`". The issue is the authoritative scope; the
  handover prompt's Path-A preference (JSON file) was a hedge
  against the #216 branch not yet being merged into the rental
  branch. With #216 merged in this worktree, the scope can land
  on Path B without rebase risk on this PR.

- CLI namespace: the issue specifies `aeat rental finca` and `aeat
  rental contract`. The handover prompt's `aeat profile rental`
  hedge was a coordination ask with #452 — with #452 in flight on a
  separate worktree and not yet merged, and the issue text being
  authoritative, this ADR commits to top-level `aeat rental`.

- Per-CCAA stressed-area auto-detection is out of scope: each finca
  carries an explicit `is_stressed_area` boolean set at registration.
  A follow-up issue post-#452 will source the active resolution
  list automatically (the BOE wording cites "la resolución que ...
  apruebe el Ministerio de Transportes, Movilidad y Agenda urbana").

## Constraints

- **Pydantic v2 strict mandate** — every public record is
  `BaseModel(model_config=ConfigDict(strict=True, frozen=True,
  extra="forbid"))`. Closed enumerations are `enum.StrEnum`. No
  bare `dict[str, Any]` at boundary surfaces.

- **`AeatError` discipline + #398 registration** — every new
  exception subclasses `aeat.core.errors.AeatError` and registers an
  `ErrorCode` row in `_DECLARED_ERROR_CODES`. The `bind_error_code`
  hook in `__init_subclass__` rejects any class without a
  registry entry.

- **Logging via `aeat.core.logging.get_logger(__name__)`** only.

- **Public API** — callers outside `aeat.domain.rental` import only from
  the package root. Internal modules carry an underscore prefix.

- **Trilingual contract** — every Translatable on the user-visible
  surface (CLI help, error messages, casilla labels) provides
  Spanish + English + Hungarian. Tests cover ES + EN explicitly.

- **NO mocks / stubs / fakes / freezegun / pytest-mock** — every
  test uses real Pydantic instances, real Repositories against
  `tmp_path`-bound SQLAlchemy engines, real Typer CliRunner.

- **Module-level pytest markers** —
  `pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]`
  for unit tests under `aeat.domain.rental`. M100 wiring tests under
  `aeat.domain.formulas._rulesets.modelo_100` retain the existing
  `domain_submission` marker pair.

- **NO wave / phase numbering in source code or docstrings** —
  delivery cadence is dev-process metadata for vault docs and
  commit messages only.

- **No live AEAT submission surfaces** — this work is local-state +
  filing-calc only. Charter #116 / #432 is unaffected.

- **Coverage floor 60 %** on `src/aeat` (CI gate); `just lint && just
  typecheck && just test && just hooks` must stay green on Windows.

## Implementation

### Subpackage layout

`src/aeat/domain/rental/` is a new top-level subpackage. Public API is the
package `__init__.py`; private modules carry underscore prefixes.

- `aeat.domain.rental._models` — Pydantic v2 records:
  - `RentalFinca` — finca registration. Fields: `id`, `identifier`,
    `address` (encrypted at rest), `valor_catastral_total`,
    `valor_catastral_construccion`, `valor_catastral_revision_year`,
    `coste_adquisicion`, `coste_adquisicion_construccion` (derived
    or explicit), `acquisition_date`, `disposal_date | None`,
    `use_type` (enum: `VIVIENDA_ARRENDADA`, `VIVIENDA_HABITUAL`,
    `OTRO_INMUEBLE_NO_AFECTO`, `LOCAL_COMERCIAL`,
    `VIVIENDA_DESOCUPADA`), `is_stressed_area` (per-year overrides
    via the contract record), `schema_version: str = "1"`.
  - `RentalContract` — per-contract metadata. Fields: `id`,
    `finca_id` (FK), `contract_celebration_date`,
    `contract_termination_date | None`, `tenant_count`,
    `qualifying_co_tenant_count` (0-tenant_count), `tenant_min_age`,
    `tenant_max_age`, `tenant_is_public_admin`,
    `tenant_is_ley_49_2002_entity_with_social_use`,
    `tenant_is_imv_beneficiary`, `dwelling_in_public_program`,
    `prior_contract_last_rent | None`, `prior_contract_indexation`
    (None for no clause; Decimal otherwise), `initial_rent`,
    `is_first_rental` (boolean — was this the dwelling's first
    rental contract), `rehabilitation_finished_date | None`
    (most recent rehab per RD 439/2007 art. 41.1),
    `lau_17_6_compliant` (boolean — defaults `True`; `False` forfeits
    the reducción), `schema_version: str = "1"`.
  - `RentalIncomeRecord` — per-finca per-period income detail.
    Fields: `id`, `contract_id` (FK), `period_year`,
    `gross_rent_received`, `dias_alquilados` (1-366),
    `schema_version: str = "1"`.
  - `RentalExpense` — per-finca categorized gasto. Fields: `id`,
    `finca_id` (FK), `period_year`, `category` (StrEnum:
    `FINANCIACION_INTERESES`, `CONSERVACION_REPARACION`,
    `IBI_TRIBUTOS_NO_ESTATALES`, `COMUNIDAD`, `SEGUROS`,
    `SUMINISTROS`, `ADMINISTRACION_PORTERIA_VIGILANCIA`,
    `FORMALIZACION_CONTRATO`, `DEFENSA_JURIDICA`,
    `SALDOS_DUDOSO_COBRO`, `OTROS`), `amount`,
    `schema_version: str = "1"`.
  - `RentalAmortizationLedgerEntry` — cap-tracking ledger. Fields:
    `id`, `finca_id` (FK), `period_year`, `dias_alquilados`,
    `basis_used` (max of coste_construccion vs valor_catastral_
    construccion at year), `amortization_amount`,
    `cumulative_amortization_through_year`,
    `schema_version: str = "1"`.

- `aeat.domain.rental._enums`:
  - `UseType` (StrEnum, see above)
  - `ExpenseCategory` (StrEnum, see above)
  - `ReduccionTier` (StrEnum: `TIER_50`, `TIER_60_REHAB`,
    `TIER_60_GRANDFATHERED_DT38`, `TIER_70_JOVEN`,
    `TIER_70_PUBLIC_ADMIN`, `TIER_90`, `FORFEIT_LAU_17_6`).
    Distinct identifiers for the two 60 % paths preserve audit
    traceability — DT 38ª vs art. 23.2.c — even though the
    numeric reducción is the same.

- `aeat.domain.rental._tier_resolver`:
  - `resolve_reduccion(contract: RentalContract, finca:
    RentalFinca, period_year: int, ejercicio_amendment_year:
    int = 2024) -> TierResolution` where `TierResolution` is a
    frozen Pydantic record carrying `tier: ReduccionTier`,
    `reduccion_pct: Decimal`, `qualifying_share: Decimal`,
    `boe_citation_id: str` (e.g. `"art_23_2_a"`,
    `"art_23_2_b_1"`, `"dt_38"`). The dispatch:
    1. If `period_year < ejercicio_amendment_year` → return
       `(TIER_60_GRANDFATHERED_DT38, 0.60, 1, "pre_amendment")`.
    2. If contract was celebrated before 2023-05-26 → return
       `(TIER_60_GRANDFATHERED_DT38, 0.60, 1, "dt_38")`.
    3. If `not contract.lau_17_6_compliant` → return
       `(FORFEIT_LAU_17_6, 0, 0, "art_23_2_par_4")`.
    4. Apply tiers in BOE priority order: 90 → 70 → 60 → 50.
    5. Tier 70-b-1 multi-tenant case computes `qualifying_share =
       qualifying_co_tenant_count / tenant_count`.

- `aeat.domain.rental._amortization_ledger`:
  - `compute_amortization_for_year(finca: RentalFinca, contract:
    RentalContract, income: RentalIncomeRecord, ledger:
    AmortizationLedger) -> Decimal` — applies LIRPF art. 23.1.f
    with the cap. Internal helper `_basis_for_year(finca,
    period_year)` returns `max(finca.coste_adquisicion_construccion,
    finca.valor_catastral_construccion)` for the requested year.
    The ledger reads the cumulative-through-year-N-1 sum and clamps
    the year-N amortización to `coste_adquisicion_construccion -
    cumulative_through_year_N_minus_1`.

- `aeat.domain.rental._expense_rollup`:
  - `compute_gastos_for_year(finca, expenses, prior_year_carry) ->
    GastosForYear` — rolls up per-category expenses, applies the
    art. 23.1.a) cap (financiación + reparación capped at
    ingresos; excess returns as a 4-year carry-forward).

- `aeat.domain.rental._anexo_c_aggregator`:
  - `compute_anexo_c_aggregates(period_year: int, store:
    RentalRegisterRepository) -> AnexoCAggregates` — emits a frozen
    Pydantic record carrying derived 0061, 0066, 0072, 0078, 0085
    decimals plus per-finca / per-contract attribution maps for
    audit traceability.

- `aeat.domain.rental._repository`:
  - `RentalFincaRepository(Repository[RentalFinca])`,
    `RentalContractRepository(Repository[RentalContract])`,
    `RentalIncomeRepository(Repository[RentalIncomeRecord])`,
    `RentalExpenseRepository(Repository[RentalExpense])`,
    `RentalAmortizationLedgerRepository(Repository[
    RentalAmortizationLedgerEntry])`.

- `aeat.domain.rental._errors`:
  - `RentalRegisterError(AeatError)` — base.
  - `FincaNotFoundError`, `ContractNotFoundError`,
    `TierResolutionError` (raised when contract metadata is
    inconsistent — e.g. tenant_min_age > tenant_max_age),
    `AmortizationLedgerCapExceededError`,
    `AnexoCAggregationError`. Each gets an `ErrorCode` row in
    `aeat.core.errors._registry._DECLARED_ERROR_CODES` per #398.

### Storage layer additions

- New ORM tables in `src/aeat/adapters/persistence/storage/_orm.py`:
  - `rental_fincas` (id, identifier UNIQUE, address ENCRYPTED,
    valor_catastral_total, valor_catastral_construccion,
    valor_catastral_revision_year, coste_adquisicion,
    coste_adquisicion_construccion, acquisition_date, disposal_date,
    use_type CHECK, is_stressed_area, schema_version).
  - `rental_contracts` (id, finca_id FK, contract_celebration_date,
    contract_termination_date, tenant_count, qualifying_co_tenant_
    count, tenant_min_age, tenant_max_age, tenant_is_public_admin,
    tenant_is_ley_49_2002_entity_with_social_use,
    tenant_is_imv_beneficiary, dwelling_in_public_program,
    prior_contract_last_rent, prior_contract_indexation,
    initial_rent, is_first_rental, rehabilitation_finished_date,
    lau_17_6_compliant, schema_version).
  - `rental_income_records` (id, contract_id FK, period_year,
    gross_rent_received, dias_alquilados, schema_version,
    UNIQUE(contract_id, period_year)).
  - `rental_expenses` (id, finca_id FK, period_year, category
    CHECK, amount, schema_version).
  - `rental_amortization_ledger` (id, finca_id FK, period_year,
    dias_alquilados, basis_used, amortization_amount,
    cumulative_amortization_through_year, schema_version,
    UNIQUE(finca_id, period_year)).

- New alembic migration: `migrations/versions/0003_rental_register.py`.
  Bumps to revision `0003_rental_register`, down_revision
  `0002_constraints`. Up creates the five tables; down drops them in
  reverse FK-dependency order.

- Address (`rental_fincas.address`) and tenant identifying fields use
  `EncryptedString` columns at the FINANCIAL classification.

### M100 Anexo C wiring (backwards-compat shim)

The existing `anexo_c_2024.py / 2025.py / 2026.py` keep their
caller-supplied casilla declarations and FORMULAS unchanged. The
backwards-compat shim is a thin import-side helper:

- `aeat.domain.rental.anexo_c_provider.compute_or_passthrough(period_year,
  provided_casillas: Mapping[str, Decimal], store:
  RentalRegisterRepository | None) -> dict[str, Decimal]` — when
  `store` is None or empty (no fincas registered for the period),
  passes through every caller-supplied 0061/0066/0072/0078/0085
  unchanged. When the store is populated, computes derived
  aggregates and merges: ledger-derived values take precedence over
  caller-supplied; mismatches surface as a discrepancy via the
  existing M100 `Engine.audit_against` path (no new error class
  needed — existing `AuditDiscrepancyError` covers it).

- `aeat filing import --from-borrador` and `--from-declaracion`
  call `compute_or_passthrough` automatically when the rental store
  is configured. The dispatch is opt-in — an unconfigured store
  does not change behaviour.

### CLI surface

A new `src/aeat/entrypoints/cli/rental/` sub-app with five command groups:

- `aeat rental finca {add, list, show, update, dispose}`
- `aeat rental contract {add, list, show, update, terminate}`
- `aeat rental expense {add, list, show}`
- `aeat rental amortization {recompute, show}`
- `aeat rental anexo-c {compute, verify}`

The sub-app is registered in `src/aeat/entrypoints/cli/__init__.py` via
`app.add_typer(rental_module.app, name="rental", help="Per-finca
rental register, Ley 12/2023 tier auto-resolver, art. 23.1.f
amortización ledger (#454).")`. `decorate_typer_app(app)` at the
root applies the `command_error_boundary` automatically.

`--json` output schemas register via
`@register_schema("rental.finca.list")`,
`@register_schema("rental.finca.show")`,
`@register_schema("rental.contract.list")`,
`@register_schema("rental.contract.show")`,
`@register_schema("rental.amortization.show")`,
`@register_schema("rental.anexo-c.compute")`,
`@register_schema("rental.anexo-c.verify")`.

### Documentation

`docs/concepts/rental-income.md` — concept doc covering the per-
finca register, tier auto-resolver semantics with worked examples
per BOE primary source, and the amortización ledger cap. References
the BOE consult dates for every cited rule.

`docs/coverage/kent-capabilities.md` — appended row "Auto-derive
rental income tier per Ley 12/2023" → ✅ via #454.

## Rationale

- **Path B (SQLite) over Path A (JSON)** chosen because (a) issue
  body §2 explicitly prefers it; (b) the relational shape (finca →
  contract → income / expense / ledger) maps natively to FK
  relationships and benefits from RDBMS-level integrity; (c) the
  encrypted-column substrate handles tenant PII without bespoke
  envelope plumbing; (d) #216 is merged in this branch, so the
  rebase risk that motivated Path A in the handover prompt is
  resolved; (e) #453 (inventario) and the per-anexo expense
  registers anticipated by EPIC #455 will need similar relational
  shapes — landing the SQLite pattern here amortizes the schema
  work.

- **`aeat rental` top-level over `aeat profile rental` nested**
  chosen because (a) issue body §1 says `aeat rental finca` and
  `aeat rental contract`; (b) #452's `aeat profile` does not yet
  exist on this branch; (c) per-finca registration is a Kent-
  workflow surface, not a profile concern — the namespace cost of
  `aeat rental` is justified by the depth of the sub-app
  (5 command groups, ~15 commands).

- **Distinct `TIER_60_GRANDFATHERED_DT38` vs `TIER_60_REHAB`**
  preserves audit traceability. Both yield 60 % numerically; the
  tier resolver carries the BOE citation distinction so any
  downstream verifier (e.g. M100 audit, AEAT borrador cross-check)
  can explain WHY a given filing landed at 60 %.

- **Tier resolver returns `qualifying_share`** because BOE
  apartado 2 letra b) ordinal 1.º splits the 70 % reducción
  proportionally across qualifying co-tenants. Modelling the share
  at resolver level keeps the amount-attribution logic in one
  place — the aggregator multiplies share × tier_pct ×
  per_contract_rendimiento_neto.

- **`FORFEIT_LAU_17_6` as a sentinel** rather than an exception
  because LAU non-compliance is a pure property of the contract
  metadata, not a programming error. The aggregator treats this
  tier as `0 % × rendimiento` and the audit explanation surfaces
  the cause.

- **Backwards-compat shim** preserves Kent's existing M100 flow
  (caller-supplied aggregates) when the rental register is empty.
  This is cheap to implement (one passthrough branch) and
  eliminates the migration cliff for existing operator workflows.

- **Per-finca explicit `is_stressed_area`** flag rather than CCAA-
  driven auto-detection because the BOE source pins zonas
  tensionadas to "la resolución que ... apruebe el Ministerio de
  Transportes", not to the contribuyente's CCAA. The flag is the
  right level of detail for the per-finca register; CCAA-driven
  enrichment is a separate concern that #452 enables and a
  follow-up issue will deliver.

## Consequences

- **Five new ORM tables + alembic 0003 migration** add to the
  storage schema. The existing alembic round-trip test
  (`_test_migrations.py`) automatically picks them up; no test
  surface change there.

- **`aeat.domain.rental` adds ~15 new error classes** to the registry; each
  needs an `ErrorCode` row in `_DECLARED_ERROR_CODES`. The
  `bind_error_code` test (`aeat.core.errors.test_registry_enforcement`)
  enforces this at import time.

- **Backwards-compat is structural, not testimonial** — the existing
  `test_anexo_c_2025.py` cases still pass unchanged because the
  `compute_or_passthrough` shim is opt-in. No M100 megaproject
  regression risk.

- **CLI surface grows by 5 command groups** (~15 commands). The
  `decorate_typer_app(app)` walk picks them up automatically; no
  manual error-boundary wiring needed.

- **Trilingual labels** for every new casilla-equivalent surface
  (e.g. tier names, expense categories) increase the i18n surface;
  every tier identifier carries ES + EN + HU on its `Translatable`.

- **Follow-up issues** (anticipated, not blockers for this PR):
  - CCAA-driven stressed-area auto-detection (requires #452 to
    land; sources Ministerio resolution into a per-año zonas-
    tensionadas table).
  - Per-CCAA stressed-area declarations (where each CCAA publishes
    its own complementary list).
  - Imputación pro-rate refinement for partial-year non-let
    fincas (current scope handles full-year non-let; a per-finca
    `dias_no_afectos` field can be added later).
  - Multi-tenant-mid-year tier transitions (e.g. one tenant ages
    out of the 18-35 range mid-year). Current scope evaluates
    tier at contract-celebration only, per BOE "Los requisitos
    señalados deberán cumplirse en el momento de celebrar el
    contrato".

- **Sibling-branch coordination on PR open**:
  - `#452` (CCAA-in-profile) — no source collision now (different
    subpackage); future CCAA-driven stressed-area enrichment will
    consume #452's profile API.
  - `#216` (database-backend) — already merged in this branch;
    Path B uses #216's storage substrate. PR description must
    note the dependency relationship explicitly.
  - `#453` (inventory) — no collision; both will use the same
    `Repository[RecordT]` pattern.
  - `#457` (mutation harness) — no collision.
  - `#327` (M390 calc-verify) — no collision.
