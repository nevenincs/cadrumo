# Rental income hardening — per-finca register, Ley 12/2023 tier auto-resolver, art. 23.1.f amortización ledger

Kent's M100 Anexo C (rendimientos del capital inmobiliario) used to require him to compute every casilla by hand: sum gross rents across his fincas, sum deductible expenses, compute the 3 % amortización per finca, look up the right Ley 12/2023 reducción tier, and total the imputación for non-let inmuebles. This page documents the per-finca register that replaces those manual lookups.

The vocabulary is locked by ADR [`rental-income-hardening`](../../.vault/adr/2026-04-29-rental-income-hardening-adr.md) (issue [#454](https://github.com/wgergely/aeat/issues/454)).

## What the register tracks

The register persists five record types under `~/.config/aeat/`-style local SQLite (configured via `AEAT_DATABASE_URL`; default `var/aeat.db`):

- **Finca** (`rental_fincas`): one row per urban property Kent owns. Carries the address (encrypted at rest), the Catastro split (valor catastral total / construcción), the acquisition cost split (coste / coste construcción), the most recent revisión catastral year, the use type (vivienda arrendada / habitual / otro inmueble no afecto / local comercial / vivienda desocupada), and the **`is_stressed_area`** flag declaring whether the finca sits in a Ministerio-published zona de mercado residencial tensionado.

- **Contract** (`rental_contracts`): one row per arrendamiento contract. Carries the contract celebration date (drives DT 38ª grandfathering), tenant counts + the qualifying co-tenant share for tier 70-b-1 splits, Public-Admin / Ley 49/2002 / IMV flags for tier 70-b-2, the prior-contract last rent (drives tier 90-a's >5 % rebaja check), the rehabilitation-finished date for tier 60-c, and the **`lau_17_6_compliant`** flag.

- **Income** (`rental_income_records`): one row per (contract, ejercicio). Carries gross rent received and días alquilados.

- **Expense** (`rental_expenses`): one row per categorised gasto, keyed by (finca, ejercicio, category). Categories follow LIRPF art. 23.1: financiación + intereses, conservación + reparación, IBI, comunidad, seguros, suministros, administración, formalización del contrato, defensa jurídica, saldos de dudoso cobro, otros.

- **Amortization ledger** (`rental_amortization_ledger`): one row per (finca, ejercicio). Persists the per-year accrual and the cumulative-through-year so the cost-basis cap is enforced across years.

## The tier auto-resolver — Ley 12/2023 BOE priority order

Authoritative primary source: **Ley 12/2023, de 24 de mayo, disposición final segunda**, BOE-A-2023-12203 (BOE núm. 124 of 25/05/2023, pp. 71525-71526). Verbatim trigger conditions are reproduced in `.vault/research/2026-04-29-rental-income-hardening-research.md` §2.

The resolver dispatches in this order — every tier reads "no cumpliéndose los requisitos de las letras anteriores" so the highest applicable tier wins:

1. **Effective-date dispatch** (before any tier check):
   - `period_year < 2024` → flat 60 % (pre-amendment art. 23.2). Filings of ejercicio 2023 ignore the new tier framework.
   - `2024+` ejercicio AND contract celebrated before **2023-05-26** (Ley 12/2023 entry into force) → flat 60 % under disposición transitoria 38ª.

2. **LAU art. 17.6 compliance check**: if the contract violates LAU art. 17.6 (rent cap for new contracts in declared zonas tensionadas where the landlord is a gran tenedor), **the reducción is forfeit**. The resolver returns the `FORFEIT_LAU_17_6` sentinel with `reduccion_pct = 0`.

3. **Tier 90-a — landlord-initiated rebaja in zona tensionada**: applies when (a) the property sits in a declared zona tensionada AND (b) the new contract's initial rent is **more than 5 %** below the prior contract's last rent (after applying the prior contract's annual indexation). BOE wording is "más de un 5 por ciento", so exactly 5 % does NOT qualify.

4. **Tier 70-b-1 — joven inquilino in zona tensionada**: applies when (a) the contract is the dwelling's first ever rental contract, (b) the property sits in a declared zona tensionada, AND (c) at least one co-tenant is aged 18-35 (inclusive). When multiple co-tenants are on the same contract and only some qualify, the 70 % reducción applies proportionally — the resolver returns `qualifying_share = qualifying_co_tenant_count / tenant_count`.

5. **Tier 70-b-2 — Public Admin / Ley 49/2002 / IMV**: applies when the tenant is (a) a Public Administration destining the dwelling to alquiler social, (b) a Ley 49/2002 régimen-especial entity destining it to alquiler social or vulnerability accommodation, (c) an IMV beneficiary, OR (d) the dwelling is enrolled in a public housing program with a rent cap.

6. **Tier 60-c — rehabilitation in the 2 preceding years**: applies when an actuación de rehabilitación per RIRPF art. 41.1 finished within 730 days before the contract celebration date.

7. **Tier 50-d — default**: applies when none of the above match.

## The art. 23.1.f amortización 3 % ledger

LIRPF art. 23.1, párrafo f: 3 % sobre el mayor del coste de adquisición o del valor catastral de la construcción. Per-year accrual:

```
basis = max(coste_adquisicion_construccion, valor_catastral_construccion)
gross_amortization = basis * 0.03 * dias_alquilados / 365
```

Half-up rounded to euro-cent precision. The cumulative sum across years is **capped at the coste de adquisición de la construcción** — once cumulative reaches the cap, future accruals clamp to 0. The cap is per-finca (no portfolio aggregation).

The persistent ledger threads `cumulative_amortization_through_year` across years so a year-N+1 recompute starts from year-N's persisted cumulative. Strict callers (preflight verifiers that want to flag the cap surface) opt in via `strict=True` and receive `AmortizationLedgerCapExceededError` instead of silent clamping.

## The art. 23.1.a) deductible-expense cap with 4-year carry-forward

LIRPF art. 23.1, letra a) párrafo segundo: **financiación intereses + conservación/reparación, jointly capped at the ingresos íntegros del periodo**. The excess **carries forward up to 4 years** ("El exceso ... se podrá deducir en los cuatro años siguientes").

The expense rollup tracks a per-finca FIFO carry-forward queue keyed by origination year. Each rollup:

1. Sums the capped categories (FINANCIACION_INTERESES + CONSERVACION_REPARACION).
2. Applies the cap at ingresos.
3. Consumes prior-year carry against any remaining cap capacity (FIFO by origination year).
4. Emits any new excess as a fresh carry-forward entry anchored to the period year.
5. Drops carry entries older than 4 years (silently — those are statutorily expired).

## LIRPF art. 85 imputación rentas inmobiliarias

For non-let, non-vivienda-habitual fincas, the aggregator applies LIRPF art. 85:

- **2 %** of valor catastral total (default).
- **1,1 %** of valor catastral total when the catastral revision happened within the **10 ejercicios** preceding the period (`period_year - valor_catastral_revision_year <= 10`).

Imputación applies per-finca whose `use_type` is `OTRO_INMUEBLE_NO_AFECTO` or `VIVIENDA_DESOCUPADA`. The rate is selected by the catastral revision year on the finca record.

## How the M100 Anexo C wiring works

The pre-#454 M100 Anexo C ruleset (`anexo_c_2024.py / 2025.py / 2026.py`) treated casillas 0061/0066/0072/0078/0085 as caller-supplied. With #454 the wiring is:

- The `compute_or_passthrough` provider in `aeat.domain.rental.anexo_c_provider` is the only entry point M100 callers consult.
- When the rental register has fincas registered for the period, derived aggregates take precedence. Caller-supplied values that differ from derived surface as discrepancies via `AnexoCMergeReport.overridden`.
- When the register is empty (Kent hasn't onboarded a finca yet), the provider passes the caller-supplied casillas through unchanged. **No regression on existing callers.**

The 7 pre-existing M100 Anexo C tests still pass unchanged.

## CLI surface

```text
aeat rental finca   add | list | show
aeat rental contract add | list | show
aeat rental income   record | list
aeat rental expense  add | list
aeat rental anexo-c  compute | verify
```

Every command supports `--json` per the project schema registry (#399). `aeat rental anexo-c verify --supplied <file>` cross-checks a JSON file of caller-supplied casillas against register-derived values for a given ejercicio.

## What's out of scope for #454

- **Foral regimes** (País Vasco, Navarra) — separate ruleset variant, EPIC #424.
- **Subarrendamiento** — capital mobiliario (LIRPF art. 25.4.c), not capital inmobiliario.
- **Arrendamiento de actividades económicas** — Anexo D, separate flow.
- **CCAA-driven stressed-area auto-detection** — for now, per-finca explicit `is_stressed_area` flag at registration. A follow-up post-#452 will source the active Ministerio resolution list automatically.
- **Multi-tenant mid-year tier transitions** — current scope evaluates the tier at contract celebration only, per BOE "Los requisitos señalados deberán cumplirse en el momento de celebrar el contrato".
- **Partial-year imputación pro-rate** — current scope assumes full-year non-let occupancy on art. 85 fincas; partial-year pro-rate is a follow-up.

## Provenance

Last updated **2026-04-29** (#454 shipped — per-finca register + Ley 12/2023 tier auto-resolver + art. 23.1.f amortización ledger). BOE primary sources cited verbatim in the research artefact and the resolver's `boe_citation_id` field.
