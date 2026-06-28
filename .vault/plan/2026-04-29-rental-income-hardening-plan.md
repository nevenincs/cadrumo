---
tags:
  - '#plan'
  - '#rental-income-hardening'
date: '2026-04-29'
modified: '2026-04-29'
related:
  - "[[2026-04-29-rental-income-hardening-adr]]"
  - "[[2026-04-29-rental-income-hardening-research]]"
  - "[[2026-04-28-modelo-100-renta-full-calc-reference]]"
  - "[[2026-04-27-modelo-100-renta-full-calc-adr]]"
---



# `rental-income-hardening` rollout plan

Implements the per-finca + per-contract rental register, the LIRPF
art. 23.2 four-tier auto-resolver (post Ley 12/2023, BOE-A-2023-12203),
the LIRPF art. 23.1.f amortización 3 % multi-year ledger with cost-
basis cap, the LIRPF art. 23.1 expense rollup with art. 23.1.a) cap +
4-year carry-forward, the LIRPF art. 85 imputación 1,1 % / 2 %
computation, the M100 Anexo C wiring with backwards-compat shim, and
the `aeat rental` CLI sub-app. SQLite via the merged `aeat.adapters.persistence.storage`
substrate (Path B per ADR §Rationale).

## Proposed Changes

This plan splits delivery into seven sequential phases. Each phase is
independently green (lint + typecheck + test + hooks) before
proceeding; commits are conventional-form per phase. The phase
boundary is the unit of self-review, not a delivery cadence
identifier — the produced source code carries no wave/phase markers.

## Tasks

- **Phase 1 — Storage schema**
  1. Add five ORM tables in `src/aeat/adapters/persistence/storage/_orm.py`:
     `rental_fincas`, `rental_contracts`, `rental_income_records`,
     `rental_expenses`, `rental_amortization_ledger`. Encrypted
     columns for tenant identifying fields and finca address.
  2. Author `migrations/versions/0003_rental_register.py`:
     up creates the five tables with FKs + check constraints +
     unique constraints; down drops in reverse order.
  3. Verify `_test_migrations.py` round-trip still passes.

- **Phase 2 — Public records + repositories + errors**
  1. Create `src/aeat/domain/rental/__init__.py` public surface.
  2. Create `src/aeat/domain/rental/_enums.py` with `UseType`,
     `ExpenseCategory`, `ReduccionTier`.
  3. Create `src/aeat/domain/rental/_models.py` with the five frozen-
     strict Pydantic v2 records: `RentalFinca`, `RentalContract`,
     `RentalIncomeRecord`, `RentalExpense`,
     `RentalAmortizationLedgerEntry`. Each carries
     `schema_version: str = "1"`.
  4. Create `src/aeat/domain/rental/_errors.py` with
     `RentalRegisterError(AeatError)` base + per-class subclasses;
     register every subclass in
     `aeat.core.errors._registry._DECLARED_ERROR_CODES` per #398.
  5. Create `src/aeat/domain/rental/_repository.py` with five
     `Repository[RecordT]` subclasses mapping records ↔ ORM rows.
  6. Round-trip tests: create → upsert → list → get → delete for
     each repository against `tmp_path` SQLite engines (no mocks).

- **Phase 3 — Tier resolver**
  1. Create `src/aeat/domain/rental/_tier_resolver.py`:
     - `TierResolution` Pydantic record (frozen-strict): `tier`,
       `reduccion_pct`, `qualifying_share`, `boe_citation_id`.
     - `resolve_reduccion(contract, finca, period_year, *,
       ejercicio_amendment_year=2024) -> TierResolution`.
     - Dispatch order: pre-amendment ejercicio → DT 38ª; pre-
       2023-05-26 contract → DT 38ª; LAU art. 17.6 forfeit;
       BOE priority 90 → 70 → 60 → 50.
     - Tier 70-b-1 multi-tenant: `qualifying_share =
       qualifying_co_tenant_count / tenant_count`.
  2. Tests:
     - `2023 ejercicio + any contract → 60 % flat (pre-amendment)`.
     - `2024 ejercicio + 2023-05-25 contract → DT 38ª (60 %)`.
     - `2024 ejercicio + 2023-05-26 contract + 90-a happy path
        (all conditions met) → 90 %`.
     - `90-a near-miss: rebaja 5.00 % exactly → falls through (BOE
        says "más de un 5 por ciento")`.
     - `70-b-1 single tenant 30 yo + zona tensionada + first
        rental → 70 % × share=1`.
     - `70-b-1 multi tenant: 2 of 3 qualify → 70 % × share=2/3`.
     - `70-b-1 stressed-area + tenant 36 → fall through to 60-c
        if rehab applies, else 50-d`.
     - `70-b-2 Public Admin + alquiler social → 70 %`.
     - `70-b-2 Ley 49/2002 entity + IMV beneficiary → 70 %`.
     - `60-c rehab finished 365 days before contract → 60 %`.
     - `60-c rehab finished 730 days before contract → 60 % (boundary)`.
     - `60-c rehab finished 731 days before contract → 50 %`.
     - `50-d default`.
     - `LAU 17.6 violation → FORFEIT_LAU_17_6 (0 %)`.

- **Phase 4 — Amortización ledger + expense rollup**
  1. Create `src/aeat/domain/rental/_amortization_ledger.py`:
     - `AmortizationComputation` record: `period_year`, `basis`,
       `gross_amortization`, `capped_amortization`,
       `cumulative_through_year`.
     - `compute_amortization_for_year(finca, contract, income,
        ledger) -> AmortizationComputation`. Raises
       `AmortizationLedgerCapExceededError` only if input requests
       a year already at the cap with non-zero
       `dias_alquilados` AND the caller asked for the strict
       variant; default behaviour is to return zero (graceful).
     - `recompute_ledger(finca, contracts, incomes,
        repository) -> tuple[AmortizationComputation, ...]` — full
        per-finca recompute over years.
  2. Create `src/aeat/domain/rental/_expense_rollup.py`:
     - `GastosForYear` record: `total`, `por_categoria`,
       `cap_excedido` (Decimal — financiación + reparación
       overflow), `carry_forward_years_remaining`.
     - `compute_gastos_for_year(finca, expenses, ingresos,
        prior_year_carry) -> GastosForYear`. Applies LIRPF
        art. 23.1.a) cap on financiación + reparación at ingresos;
        carry-forward 4 years (so each year tracks 4 generations
        of carry).
  3. Tests:
     - Amortización single-finca single-year + cumulative ledger.
     - Cap reached mid-year → year-N amortización = remaining cap.
     - Multi-finca isolation.
     - Expense rollup per-category sum.
     - `art. 23.1.a)` cap: financiación 8 000 + reparación 5 000,
        ingresos 10 000 → cap excess 3 000 carries forward.
     - 4-year carry-forward expiration: year-N+5 carry from year-N
        is dropped.

- **Phase 5 — Anexo C aggregator + M100 wiring**
  1. Create `src/aeat/domain/rental/_anexo_c_aggregator.py`:
     - `AnexoCAggregates` Pydantic record: `casilla_0061`,
       `casilla_0066`, `casilla_0072`, `casilla_0078`,
       `casilla_0085`, plus `per_finca_attribution: Mapping[
        str, FincaAttribution]` and `per_contract_tier: Mapping[
        str, TierResolution]` for audit traceability.
     - `compute_anexo_c_aggregates(period_year, store)`.
     - Casilla 0078 attribution: `Σ_per_contract tier_pct ×
        qualifying_share × clamp_pos(per_contract_rendimiento_neto)`.
  2. Create `src/aeat/domain/rental/anexo_c_provider.py`:
     - `compute_or_passthrough(period_year, provided_casillas,
        store=None)` — empty / unconfigured store passes through.
  3. Tests:
     - Empty store + caller-supplied aggregates → passthrough.
     - Populated store → derived 0061/0066/0072/0078/0085 +
       attribution.
     - Tier 70-b-1 multi-contract: per-contract reducción attributes
        proportionally; 0078 sum = Σ per-contract reducción amounts.
     - Mixed: store has finca f1 only; supplied 0061 lists both f1
        + f2 → derived path covers f1, supplied path contributes
        f2; merged 0061 = f1.derived + (supplied - f1.estimated_
        from_register). Document the merge semantics in the
        aggregator docstring; surface a discrepancy when
        register-derived f1 ≠ supplied f1.

- **Phase 6 — CLI commands**
  1. Create `src/aeat/entrypoints/cli/rental/__init__.py` exposing the
     `app: typer.Typer` root.
  2. Create `src/aeat/entrypoints/cli/rental/finca.py`, `contract.py`,
     `expense.py`, `amortization.py`, `anexo_c.py` sub-apps.
  3. Register the sub-app in `src/aeat/entrypoints/cli/__init__.py` via
     `app.add_typer(rental_module.app, name="rental", help=...)`.
  4. Per-command `--json` schema registrations via
     `@register_schema("rental.finca.list")` etc.
  5. Tests:
     - `aeat rental finca add` persists + returns JSON shape.
     - `aeat rental finca list --json` round-trips schema.
     - `aeat rental contract add` persists + returns JSON shape.
     - `aeat rental anexo-c compute --year 2025 --json`
        aggregates + returns AnexoCAggregates shape.
     - `aeat rental anexo-c verify --year 2025` cross-checks
        register vs supplied aggregates and surfaces discrepancies.
     - Trilingual ES + EN explicit on `--help` and on error
        messages.

- **Phase 7 — Documentation**
  1. Author `docs/concepts/rental-income.md` covering tier
     auto-resolver, BOE primary sources, the amortización ledger
     cap, the procedural cap, the LAU 17.6 forfeit, and the
     backwards-compat shim. References every BOE consult date
     used.
  2. Append row to `docs/coverage/kent-capabilities.md`:
     "Auto-derive rental income tier per Ley 12/2023" → ✅ via
     #454.

## Parallelization

Phases 1-2 must land first (storage substrate). Once on main inside
this branch, phases 3 (tier resolver) + 4 (ledger + expense rollup)
have no source overlap and could be split across two agents — but
since this delivery runs as a single agent end-to-end, the
parallelization opportunity is moot. Phase 5 depends on 3 + 4. Phase
6 depends on 5. Phase 7 depends on 5 + 6 (so the doc references the
final CLI shape). Each phase is self-contained as a commit; no
cross-phase atomic transaction is required.

## Verification

### Mission criteria

- [ ] Per-finca + per-contract register persists via SQLite under
  the merged `aeat.adapters.persistence.storage` substrate.
- [ ] Tier auto-resolver implements the BOE priority order
  (90 → 70 → 60 → 50) with verbatim trigger conditions and the
  `qualifying_share` split for 70-b-1.
- [ ] Pre-amendment + DT 38ª grandfathering routes correctly.
- [ ] LAU 17.6 forfeit yields `FORFEIT_LAU_17_6`.
- [ ] Amortización ledger enforces per-finca cumulative cap at
  `coste_adquisicion_construccion`.
- [ ] Expense rollup applies the art. 23.1.a) cap with 4-year
  carry-forward.
- [ ] Anexo C casillas 0061/0066/0072/0078/0085 derive correctly
  from the register; backwards-compat passthrough is preserved
  when the register is empty.
- [ ] `aeat rental` CLI surface ships with all 5 command groups +
  `--json` schemas + trilingual help.
- [ ] Every new error subclass registers an `ErrorCode` per #398.
- [ ] Coverage floor 60 % preserved on `src/aeat`.
- [ ] `just lint && just typecheck && just test && just hooks` pass
  on Windows.

### Self-review checklist (against ADR + research + project
mandates)

- **Pydantic v2 strict** — every record uses
  `ConfigDict(strict=True, frozen=True, extra="forbid")`. ✅ ADR
  Constraints §1.
- **`AeatError` discipline** — every new exception subclasses
  `aeat.core.errors.AeatError`; every subclass has a registry entry. ✅
  ADR Constraints §2 + research §1.
- **Logging via `aeat.core.logging.get_logger`** — no other logger
  factory used. ✅ ADR Constraints §3.
- **Public API discipline** — only `aeat.domain.rental` package root
  exposed; underscore-prefixed modules are private. ✅ ADR
  Implementation §Subpackage layout.
- **Trilingual** — every Translatable surface ships ES + EN + HU;
  tests cover ES + EN. ✅ ADR Constraints §5.
- **No mocks** — every test uses real Pydantic instances + real
  Repositories + real CliRunner. Storage tests bind
  `create_engine_from_settings` to `tmp_path` SQLite URLs. ✅ ADR
  Constraints §6.
- **Module-level pytest markers** —
  `pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]`
  on every unit test module under `aeat.domain.rental`; `pytest.mark.
  domain_submission` on M100 wiring tests. ✅ ADR Constraints §7.
- **No wave/phase numbering in code** — phase markers exist only
  in this plan + commit messages, never in source code or
  docstrings. ✅ ADR Constraints §9.
- **No live AEAT submission surfaces** — work is local-state +
  M100 calc only; charter #116 / #432 unaffected. ✅ ADR
  Constraints §10.
- **Path B (SQLite) chosen with backwards-compat shim** — empty
  register returns passthrough; this preserves Kent's existing
  M100 flow with no migration cliff. ✅ ADR Rationale §1.
- **CLI namespace `aeat rental`** matches issue body §1. ✅ ADR
  Rationale §2.
- **Tier 60 audit traceability** — distinct
  `TIER_60_GRANDFATHERED_DT38` vs `TIER_60_REHAB`. ✅ ADR
  Rationale §3.
- **70-b-1 qualifying-share split** modelled at resolver. ✅ ADR
  Rationale §4.
- **LAU 17.6 forfeit as sentinel tier**, not exception. ✅ ADR
  Rationale §5.
- **BOE primary sources cited verbatim** — research §2 reproduces
  the disposición final segunda apartado uno of Ley 12/2023; the
  resolver's `boe_citation_id` field carries the article+letter
  identifier. ✅ research §2 + research §3 + research §5.

### Beyond unit testing

- The 13-case tier-resolver test grid covers every BOE trigger
  condition + every priority-order edge + every effective-date
  branch. Boundary cases (5.00 % rebaja exact; rehab 730 vs 731
  days) are explicit. Multi-tenant share split is tested.

- The amortización ledger test grid covers single-year, multi-year
  accumulation, cap-mid-year clamping, multi-finca isolation. The
  expense-rollup test grid covers per-category aggregation, cap
  application, carry-forward inflow / outflow / expiration.

- The Anexo C aggregator integration test populates the register
  with two fincas + three contracts, computes 0061-0085 + per-
  contract attribution, and asserts cent-exact equality against
  hand-computed expected values.

- The CLI surface tests use Typer `CliRunner` against a
  `tmp_path`-bound config; there are no mocks. The trilingual
  surface is tested via `--help` invocations under
  `AEAT_OUTPUT_LANGUAGE=es` and `AEAT_OUTPUT_LANGUAGE=en` and
  via direct `Language` resolution on error messages.

- A backwards-compat regression test re-runs every existing
  `test_anexo_c_2025.py` case with the rental register
  unconfigured; the M100 audit reports remain clean (proves the
  passthrough shim doesn't regress callers).

- An integration test against the existing
  `tests/integration/test_kent_workflows.py::TestKentImports
  Modelo100Declaracion` populates a register with realistic Kent-
  shape fincas (one zona tensionada vivienda, one rehab vivienda,
  one non-let inmueble for art. 85) and asserts the imported
  borrador's casillas match the register-derived aggregates.

### Honest limitations

- The CLI surface is exercised through Typer's `CliRunner` —
  there is no manual smoke step on a real terminal. Rich /
  trilingual rendering is verified by output-string assertions,
  not visually.

- Per-CCAA stressed-area auto-detection is OUT of scope; tests
  feed `is_stressed_area` explicitly. The "real-world" workflow
  where Kent has to look up the Ministerio resolution by hand
  remains a step the user takes.

- The synthetic-borrador integration test exercises the
  register-derived path against a synthetic PDF generator, not
  against a real AEAT borrador export. AEAT borrador shape
  drifts year-to-year and is covered by EPIC #455 sub-tasks 1-3.

- The schema-version field is wired but not exercised against
  schema-version-mismatched data; that requires a future
  migration scenario which this PR does not introduce.
