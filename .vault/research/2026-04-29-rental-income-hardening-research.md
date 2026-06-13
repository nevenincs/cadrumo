---
tags:
  - '#research'
  - '#rental-income-hardening'
date: '2026-04-29'
modified: '2026-04-29'
related: []
---



# `rental-income-hardening` research: per-finca register, Ley 12/2023 tier auto-detection, art. 23.1 amortización 3% ledger

Researches what is needed to upgrade the post-PR-#448 Modelo 100 Anexo
C surface from caller-supplied aggregates (casillas 0061/0066/0072/0078/0085)
to a per-finca / per-contract register that auto-derives the LIRPF
art. 23.2 reducción tier (50/60/70/90 % post Ley 12/2023), the
art. 23.1.f 3 % amortización (with multi-year accumulation against the
asset cost basis), the art. 23.1 deductible-expense rollup, and the
art. 85 imputación 1,1 % / 2 % per non-let inmueble. The existing
ruleset cites the right BOE primary sources but pushes every numeric
input on the consumer; this hardening decouples Kent's
per-finca / per-contract truth from the M100 audit surface.

## Findings

### 1. Existing M100 Anexo C surface (post-PR-#448)

The Anexo C surface lives in `src/aeat/domain/formulas/_rulesets/modelo_100/`
across three per-año modules: `anexo_c_2024.py`, `anexo_c_2025.py`,
`anexo_c_2026.py`. The 2024 + 2026 modules import `CASILLAS` and
`CITATIONS` from 2025; the FORMULAS are declared per-año with
year-scoped `formula_id`s. EFFECTIVE_FROM / EFFECTIVE_TO bracket the
calendar year.

The casilla inventory:

- `0061` (caller-supplied) — ingresos íntegros arrendamiento, sumados
  caller-side across fincas.
- `0066` (caller-supplied) — gastos deducibles, suma de financiación,
  IBI, comunidad, reparación y conservación, seguros, suministros,
  gestión y otros gastos deducibles per LIRPF art. 23.1.
- `0072` (caller-supplied) — amortización 3 % construcción, "3 %
  sobre el mayor del coste de adquisición o del valor catastral de
  la construcción" per LIRPF art. 23.1, párrafo f.
- `0078` (caller-supplied) — reducción art. 23.2 importe, caller
  selects the tier amount manually based on contract metadata.
- `0085` (caller-supplied) — imputación rentas inmobiliarias, caller
  computes 1,1 % o 2 % del valor catastral por inmueble no afecto.
  Parallel income line — does NOT enter the 0106 / 0107 chain.
- `0106` (computed) — `clamp_pos(0061 - 0066 - 0072)`.
- `0107` (computed) — `clamp_pos(0106 - 0078)`.

The CITATIONS tuple in 2025 cites LIRPF arts. 22, 23 (with explicit
Ley 12/2023 BOE-A-2023-12203 cross-reference for art. 23.2), 24, and
85. The wording of art. 23.2 inside the citation correctly enumerates
the four tiers. The BOE consult-date suffix `&p=20260228&tn=1` is
applied across the whole ruleset family per `_common.py`.

The unit-test surface in `test_anexo_c_2025.py` exercises the
50/60/70/90 % tiers as parametrized cases plus a clamp-to-zero edge,
an art. 85 isolation case, and an explicit drift case on 0107. Every
case feeds the tier amount as a pre-computed Decimal — confirming the
caller-burden today.

### 2. LIRPF art. 23.2 four-tier reducción (post Ley 12/2023)

Authoritative primary source: Ley 12/2023, de 24 de mayo, por el
derecho a la vivienda, **disposición final segunda**, page 71525-
71526 of BOE núm. 124 (25 de mayo de 2023), CVE BOE-A-2023-12203.

The disposición rewrites the apartado 2 of artículo 23 LIRPF
(Ley 35/2006) verbatim. The four tiers, in BOE order (the BOE order
is also the priority order — every tier text after the first reads
"no cumpliéndose los requisitos de las letras anteriores", so the
highest applicable tier wins):

- **Tier a — 90 %**: "cuando se hubiera formalizado por el mismo
  arrendador un nuevo contrato de arrendamiento sobre una vivienda
  situada en una zona de mercado residencial tensionado, en el que
  la renta inicial se hubiera rebajado en más de un 5 por ciento en
  relación con la última renta del anterior contrato de
  arrendamiento de la misma vivienda, una vez aplicada, en su caso,
  la cláusula de actualización anual del contrato anterior."

  Trigger conjunction: same landlord + new contract + property in
  declared zona tensionada at contract date + initial rent reduced
  by more than 5 % vs the prior contract's last rent (after applying
  the prior contract's annual indexation). Per-finca metadata
  needed: `is_stressed_area` (at contract celebration date), prior
  contract's `last_rent`, prior contract's `indexation_clause`,
  current contract's `initial_rent`.

- **Tier b — 70 %**: "cuando, no cumpliéndose los requisitos
  señalados en la letra a) anterior, se produzca alguna de las
  circunstancias siguientes: 1.º Que el contribuyente hubiera
  alquilado por primera vez la vivienda, siempre que ésta se
  encuentre situada en una zona de mercado residencial tensionado y
  el arrendatario tenga una edad comprendida entre 18 y 35 años. ...
  2.º Cuando el arrendatario sea una Administración Pública o
  entidad sin fines lucrativos a las que sea de aplicación el
  régimen especial regulado en el título II de la Ley 49/2002, ...
  que destine la vivienda al alquiler social ... o al alojamiento
  de personas en situación de vulnerabilidad económica a que se
  refiere la Ley 19/2021 ... o cuando la vivienda esté acogida a
  algún programa público de vivienda o calificación en virtud del
  cual la Administración competente establezca una limitación en la
  renta del alquiler."

  Two independent triggers under tier b (any one suffices):

  - 70-b-1: first-time rental of this dwelling + zona tensionada +
    tenant aged 18-35 (both inclusive at contract celebration).
    BOE refines: when the dwelling has multiple co-tenants on the
    same contract, the 70 % reducción applies proportionally only
    to the share of rendimiento neto attributable to qualifying
    co-tenants. This is a non-trivial split — the per-contract
    register must carry the qualifying-share fraction.

  - 70-b-2: tenant is a Public Administration or a non-profit
    (Ley 49/2002 régimen especial) that uses the dwelling for
    social housing (rent below the program rent), or for
    vulnerability accommodation (Ley 19/2021 IMV beneficiaries),
    or the dwelling is enrolled in a public-housing program with a
    rent cap.

- **Tier c — 60 %**: "cuando, no cumpliéndose los requisitos de las
  letras anteriores, la vivienda hubiera sido objeto de una
  actuación de rehabilitación en los términos previstos en el
  apartado 1 del artículo 41 del Reglamento del Impuesto sobre la
  Renta de las Personas Físicas que hubiera finalizado en los dos
  años anteriores a la fecha de la celebración del contrato de
  arrendamiento."

  Trigger: rehabilitation finished within the 2 years preceding the
  contract celebration date. The Reglamento del IRPF (RD 439/2007),
  art. 41.1, defines the qualifying scope of "actuación de
  rehabilitación".

- **Tier d — 50 %**: "en cualquier otro caso." Default tier — fires
  when none of the above apply.

Closing paragraphs of the rewritten apartado 2 also encode three
non-tier conditions every applicable filing must satisfy:

- "Los requisitos señalados deberán cumplirse en el momento de
  celebrar el contrato de arrendamiento, siendo la reducción
  aplicable mientras se sigan cumpliendo los mismos." — once the
  qualifying conditions are met at contract celebration, the
  reducción persists across the contract life provided the
  conditions remain satisfied.

- "Estas reducciones sólo resultarán aplicables sobre los
  rendimientos netos positivos que hayan sido calculados por el
  contribuyente en una autoliquidación presentada antes de que se
  haya iniciado un procedimiento de verificación de datos, de
  comprobación limitada o de inspección que incluya en su objeto la
  comprobación de tales rendimientos." — the reducción is forfeit
  on amounts surfaced for the first time during AEAT verification.
  This is a procedural cap, not a per-finca cap.

- "Tampoco resultarán de aplicación las reducciones en relación con
  aquellos contratos de arrendamiento que incumplan lo dispuesto en
  el apartado 6 del artículo 17 de la Ley de Arrendamientos
  Urbanos." — non-compliance with LAU art. 17.6 (the rent-cap rule
  for new contracts in declared zonas tensionadas where the
  landlord is a gran tenedor) forfeits the reducción on that
  contract.

The closing paragraph anchors the zonas-tensionadas registry: "Las
zonas de mercado residencial tensionado a las que podrá resultar de
aplicación lo previsto en este apartado serán las recogidas en la
resolución que ... apruebe el Ministerio de Transportes, Movilidad y
Agenda urbana."

### 3. Pre-26/05/2023 grandfathering (DT 38ª LIRPF)

Disposición final segunda apartado dos of Ley 12/2023 introduces the
new disposición transitoria trigésima octava in LIRPF: "A los
rendimientos netos positivos de capital inmobiliario derivados de
contratos de arrendamiento de vivienda que se hubieran celebrado con
anterioridad a la entrada en vigor de la Ley 12/2023, de 24 de mayo,
por el derecho a la vivienda, les resultará de aplicación la
reducción prevista en el apartado 2 del artículo 23 de esta ley en su
redacción vigente a 31 de diciembre de 2021."

That is — pre-26/05/2023 contracts continue under the prior flat 60 %
reducción for as long as the contract is in force. The per-contract
register MUST therefore carry the contract celebration date and
route grandfathered contracts to a fifth resolution path
(GRANDFATHERED_60) that is distinct from new-regime tier c (60 % via
rehabilitation). Tax-engine semantics for the two are identical
today, but the citation is different — DT 38ª vs art. 23.2.c — and
audit traceability requires distinguishing them.

### 4. Effective dates

Two dates are in play and are NOT the same:

- **2023-05-26**: Ley 12/2023 entered into force the day after BOE
  publication (BOE núm. 124 of 25/05/2023, disposición final novena
  apartado 1). From this date forward, NEW contracts of arrendamiento
  de vivienda are subject to the new-regime tier framework (a/b/c/d).

- **2024-01-01**: disposición final novena segundo párrafo states
  "excepto la disposición final segunda, que entrará en vigor el 1
  de enero del año siguiente al de su publicación en el «Boletín
  Oficial del Estado»." The IRPF amendment (apartado 2 of art. 23 +
  DT 38ª) takes legal effect for the 2024 tax year. Filings of
  ejercicio 2023 use the prior-regime flat 60 % even for contracts
  signed after 26/05/2023; filings of 2024 + onwards use the new
  tier framework on contracts signed since 26/05/2023, with DT 38ª
  grandfathering on older contracts.

Implication: the resolver dispatch is `(contract_celebration_date,
ejercicio)`. For 2023 ejercicio, ALL contracts use the flat 60 %
(pre-amendment art. 23.2). For 2024+ ejercicio, contracts signed
since 26/05/2023 use the new four-tier resolver, contracts signed
before 26/05/2023 use DT 38ª (= flat 60 %).

### 5. LIRPF art. 23.1.f amortización 3 %

Ley 12/2023 does NOT modify art. 23.1; only art. 23.2 changes. The
art. 23.1.f rule remains as currently cited in the Anexo C ruleset:

"3 por ciento sobre el mayor del coste de adquisición o del valor
catastral de la construcción".

Two separable components must be tracked per finca to enable the
ledger:

- **Coste de adquisición de la construcción** = (acquisition cost,
  excluding taxes that did not enrich the seller) × (valor catastral
  construcción / valor catastral total). The split between
  construcción (depreciable) and suelo (not depreciable) is taken
  from the catastral valuation ratio at acquisition (or at the most
  recent revisión catastral if the contribuyente cannot substantiate
  the original ratio).

- **Valor catastral de la construcción** at the year of accrual. This
  is the catastral construction value as published by Catastro for
  the relevant fiscal year.

Per-year depreciable basis per finca = `max(coste_construccion,
valor_catastral_construccion_year)` × 3 % × (días_alquilados / 365).

The accumulated amortización across all years (since acquisition or
since first arrendamiento, whichever is later) is **capped at the
coste de adquisición de la construcción** — once cumulative
amortización equals the acquisition cost basis, the per-year
amortización becomes zero. This is the ledger requirement.

Multi-finca implication: the cap is per-finca, not per-portfolio. The
ledger is keyed by `(finca_id, year)` and the cap check reads the
cumulative-up-to-year-N-1 sum.

### 6. LIRPF art. 23.1 gastos deducibles (other categories)

Stable across the ruleset's BOE consult date (2026-02-28):

- a) intereses de los capitales ajenos invertidos + gastos de
  conservación y reparación, jointly capped per finca per year at
  ingresos íntegros del arrendamiento (LIRPF art. 23.1.a, párrafo
  segundo). The excess can be carried forward 4 years.
- b) tributos no estatales (IBI, basura, vado, etc.).
- c) cantidades devengadas por terceros como contraprestación
  directa o indirecta como consecuencia de servicios personales
  (administrador, portería, vigilancia, etc.).
- d) gastos por formalización del contrato (notario, registro) +
  defensa jurídica.
- e) saldos de dudoso cobro tras 6 meses morosidad.
- f) [amortización 3 % — see §5 above]
- g) primas de seguros.
- h) suministros (cuando los pague el arrendador).

The per-finca expense register tracks each gasto with a category enum
and per-year totals; the carry-forward of the a) cap excess is a
multi-year rule that requires its own per-finca ledger entry.

### 7. LIRPF art. 85 imputación rentas inmobiliarias

Stable text per the existing CITATIONS[3] in `anexo_c_2025.py`:

"2 % del valor catastral; 1,1 % si el valor catastral fue revisado en
los 10 períodos impositivos anteriores; 1,1 % sobre el 50 % del mayor
de valor administrativo o de adquisición si el inmueble carece de
valor catastral."

Per-finca metadata required: catastral revision date (to determine
the 1,1 % vs 2 % rate applicable for a given ejercicio), occupancy
period within the year (imputación pro-rates by días no afectos),
and the catastral total value at the year of accrual.

Imputación applies per non-let, non-vivienda-habitual inmueble. The
casilla 0085 aggregates across all such fincas. The per-finca
register thus needs a `use_type` enum to discriminate between
arrendada (feeds 0061-0072), vivienda habitual (no income line),
and otro inmueble no afecto (feeds 0085).

### 8. Persistence-strategy options

Two strategies present:

- **Path A — JSON file under `~/.config/aeat/`**, mirroring the
  pattern proposed for #452 (CCAA-in-profile). Concrete: the
  per-finca registry as a JSON envelope (using the existing
  `aeat.adapters.persistence.storage.save_encrypted_envelope` API at the FINANCIAL
  classification, since per-finca metadata includes contract terms
  that map to GDPR personal data). Pro: rebase-resilient; trivial to
  bootstrap on a fresh workstation; no migration to write. Con:
  cross-table foreign keys (finca → contracts → expenses → ledger
  rows) become hand-rolled identity management.

- **Path B — SQLite via `aeat.adapters.persistence.storage`**, with new tables
  `rental_fincas`, `rental_contracts`, `rental_expenses`,
  `rental_amortization_ledger`. Pro: foreign keys, deterministic
  schema, alembic migrations, encrypted-column columns for
  PII-bearing fields (tenant NIE, tenant address). Con: requires a
  migration `0003_*.py`; more lines of code than Path A.

The merge of `feature/216-bank-import-persistence` into this branch
makes Path B viable: SQLAlchemy + alembic + `EncryptedString` /
`EncryptedJSON` columns + the `Repository[RecordT]` pattern are all
on the branch and well-exercised by `_test_repository.py` etc. The
project already has three exemplar Repositories (Modelo, Portal,
CorpusArtifact). The issue body's own §2 explicitly proposes "SQLite
via existing `aeat.adapters.persistence.storage`" — the issue is the source of truth and
authoritatively prefers Path B.

Cross-cutting argument: this hardening is the first M100 surface to
move from caller-supplied to engine-derived aggregates. It is
foundational for #453 (inventario) and the per-anexo expense
registers that ADR D2 / EPIC #455 anticipate. A SQLite schema
captures the relational structure that these subsequent issues will
need, so Path B reduces re-work risk.

ADR will adopt Path B with a documented opt-out fallback: if the
SQLite store is empty / unconfigured, the M100 Anexo C ruleset
defaults to the existing caller-supplied behaviour (backwards-compat
shim per the issue's Definition of Done item §6).

### 9. CLI namespace decision

The issue body specifies `aeat rental finca` and `aeat rental
contract` as the top-level command groups. The existing CLI registry
in `src/aeat/entrypoints/cli/__init__.py` does not yet export an `aeat profile`
sub-app (#452 is in flight, separate worktree, no source collision
with #454). The handover prompt suggested `aeat profile rental` to
coordinate with #452, but the issue explicitly chooses `aeat rental`
— issue text wins as the authoritative scope.

Concrete sub-app shape:

- `aeat rental finca {add, list, show, update, dispose}`
- `aeat rental contract {add, list, show, update, terminate}`
- `aeat rental expense {add, list, show}`
- `aeat rental amortization {recompute, show, ledger}`
- `aeat rental anexo-c {compute, verify}`

The verify subcommand cross-checks Anexo C casillas 0061/0066/0072/
0078/0085 against the per-finca register and surfaces any
discrepancy with classified severity (consistent with the existing
`aeat filing import --from-borrador` pattern).

### 10. Mapping to M100 Anexo C casillas (engine-derived path)

For ejercicio N + arrendamiento set { f1, f2, ..., fk }:

- `0061` = Σ f.contract.gross_rent_received(N) for f arrendada in N.
- `0066` = Σ f.expenses(N) by category, excluding amortización; the
  art. 23.1.a) 4-year carry-forward cap is applied per-finca with
  ledger persistence.
- `0072` = Σ f.amortization(N) per the cap-enforcing ledger of §5.
- `0078` = Σ f.contract.tier_reduction_amount(N), where the per-
  contract reducción is `tier_pct × clamp_pos(rent - expenses -
  amortization)` — i.e. the reducción is per-contract, not per-
  finca aggregate, because tier resolution depends on contract
  metadata.
- `0085` = Σ f.imputacion(N) for f non-arrendada non-habitual in N.

The per-contract reducción attribution to casilla 0078 has a subtle
edge case: tier 70-b-1 (joven inquilino) splits the rendimiento neto
proportionally to qualifying co-tenants on the same contract. The
resolver must therefore return both the tier and the qualifying
share fraction; the reducción amount is `tier_pct × qualifying_share
× clamp_pos(per_contract_rendimiento_neto)`.

### 11. Test strategy

Module-level marker: `pytestmark = [pytest.mark.unit,
pytest.mark.domain_local_state]` for all unit tests in
`src/aeat/domain/rental/`. The existing M100 tests under
`src/aeat/domain/formulas/_rulesets/modelo_100/test_anexo_c_*.py` use
`pytest.mark.domain_submission` — that marker stays appropriate for
the M100 Anexo C wiring tests (since those exercise the filing
ruleset surface), and the new aeat-rental unit tests use
`domain_local_state` (since they exercise on-disk catalogues and the
local SQLite mirror).

Required cases (no mocks; real Pydantic instances; real Repositories
against tmp_path-bound engines):

- Tier resolution per (contract_celebration_date, ejercicio):
  - 2023 ejercicio + any contract → flat 60 % (pre-amendment).
  - 2024 ejercicio + pre-26/05/2023 contract → DT 38ª (flat 60 %).
  - 2024+ ejercicio + post-26/05/2023 contract → four-tier resolver:
    - 90-a happy path.
    - 90-a near-miss (only 4.99 % rebaja → falls to next applicable).
    - 70-b-1 single co-tenant happy path.
    - 70-b-1 multi co-tenant: 50 % qualifying share → reducción = 70 %
      × 0.5 × per_contract_rendimiento.
    - 70-b-1 stressed-area + tenant age 36 → falls to next applicable.
    - 70-b-2 Public Admin tenant + alquiler social → 70 %.
    - 70-b-2 Ley 49/2002 entity + IMV beneficiary → 70 %.
    - 60-c rehab finished 365 days before contract → 60 %.
    - 60-c rehab finished 730 days + 1 day before contract → 50 %.
    - 50-d default.
  - Rent-cap LAU art. 17.6 violation → reducción = 0 (no tier).
  - Procedural cap: rendimiento not declared in the autoliquidación
    → reducción = 0 on that share.

- Amortización ledger:
  - Single-finca single-year: basis = max(coste, valor catastral)
    × 3 % × días_alquilados / 365.
  - Multi-year accumulation reaching cap → next-year amortización
    = 0.
  - Multi-year accumulation crossing cap mid-year → final-year
    amortización = remaining cap.
  - Multi-finca isolation: cap on f1 does not affect f2.

- Expense rollup:
  - Per-finca expense aggregation per category.
  - art. 23.1.a) cap: financiación + reparación capped at ingresos.
  - Carry-forward of cap excess across 4 years per-finca.

- Anexo C wiring:
  - Engine-derived path: ledger populated → 0061/0066/0072/0078/0085
    computed from register; M100 audit clean.
  - Caller-supplied fallback: ledger empty → caller-supplied
    aggregates accepted as before; M100 audit clean.
  - Cross-check verify: register populated AND aggregates supplied,
    drift detected → discrepancy report classifies the offending
    casilla.

- Trilingual CLI: ES default + EN explicit verify against
  `aeat rental finca list --json` and `aeat rental anexo-c verify`.

### 12. Out-of-scope confirmations

- Foral regimes (País Vasco, Navarra) — separate ruleset variant,
  EPIC #424.
- Subarrendamiento → LIRPF art. 25.4.c capital mobiliario, not
  capital inmobiliario.
- Arrendamiento de actividades económicas → Anexo D, separate
  flow.
- CCAA-driven stressed-area auto-detection — for now, per-finca
  explicit `is_stressed_area` flag set at finca registration. A
  follow-up issue will source the active zonas-tensionadas resolution
  list automatically once #452 (CCAA-in-profile) lands.
- Inventory management for autónomos → #453.
- Mutation harness fix → #457.
- Per-año test parity → #456.
- Other M100 anexos — out of scope.
- Live AEAT submission — permanently forbidden (charter #116, #432).
