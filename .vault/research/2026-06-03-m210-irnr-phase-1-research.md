---
tags:
  - '#research'
  - '#m210-irnr-phase-1'
date: '2026-06-03'
modified: '2026-06-29'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# `m210-irnr-phase-1` research: `M210 IRNR Phase 1 corpus discovery for S393-S396`

Subagent corpus-discovery pass for #627 W09.P41.S393-S396
(Olivia round-16 + Felipe round-26 M210 IRNR Phase 1 work).

> 2026-06-29 verification update: several M210 Phase 1 grounding
> blockers in this 2026-06-03 snapshot are closed in the current registry.
> `m210-convenio-rates` now cites concrete treaty legal entries:
> `convenio-es-gb-2013:art-6`, `convenio-es-ma-1978:art-11`, and
> `convenio-es-ar-1992:art-19`. The old Morocco
> `boe-a-1985-13340` / art-14 anchor was corrected to the bundled BOE
> excerpt `BOE-A-1985-9280`, article 11, whose text caps source-state
> interest taxation at 10 percent of the gross interest amount. The
> AR/pension `NOT_YET_AUTHORED` sentinel is also gone: the row now uses
> `DOMESTIC_TARIFF` with `convenio-es-ar-1992:art-19` plus
> `trlirnr-rdleg-5-2004:art-25.1.b`, and the pension tariff is authored as
> a bracket table. The old `interest` 0.24 row is also superseded:
> current `interest` is 0.19, grounded in unconditional TRLIRNR art. 25.1.f
> text rather than the art. 25.1.a EU/EEE branch. The S396 art. 13.1.h
> legal/corpus gap and imputed-real-estate base primitives are now present
> in the 2025 M210 registry. Focused verification on 2026-06-29 passed:
> `test_modelo_210_convenio_rate_resolution.py` (17 passed),
> `test_modelo_210_registry.py` (10 passed), and the shared catalogue gate
> `test_committed_registry_tree_has_coherent_shared_catalogues` (1 passed).
> The remaining live gap from this note is the S394 183-day advisory
> placement unless later feature records supersede it.

## What exists today

### Registry tree (`src/aeat/_data/registry/aeat/modelos/210/revisions/2025/`)

- `casillas/0001-casillas.toml` — 8 Phase 1 casillas: `tipo_renta`,
  `rendimientos_integros`, `gastos_deducibles`,
  `retencion_practicada`, `base_imponible`, `tipo_gravamen`,
  `cuota_integra`, `cuota_diferencial`.
- `formulas/000{1..4}-m210-*.toml` — base imponible,
  tipo-gravamen-resolve (dispatches `m210_resolve_rate` op),
  cuota integra, cuota diferencial.
- `parameters/0001-m210-tipo-gravamen-2025.toml` — keyed bracket
  table with rows: `general` (0.24), `ue_residente` (0.19),
  `ganancia_patrimonial` (0.19), `inmobiliaria` (0.24), `interest`
  (0.19). Pension is intentionally absent from this flat table because
  the current registry uses the separate bracket-table parameter
  `m210-pension-tarifa-2025`.
- `parameters/0002-m210-convenio-rates.toml` — convenio rate table
  with rows: `GB/general` (0.24), `MA/interest` (0.10),
  `AR/pension` (`DOMESTIC_TARIFF`, anchored to
  `convenio-es-ar-1992:art-19` plus TRLIRNR art 25.1.b).
- `bindings/0001-bindings.toml` —
  `m210-2025-profile-country-of-fiscal-residence` binding.
- `verification_expectations/`, `application_links/`,
  `constructs/`, `workbook_parity_refs/` directories exist.

### Legal catalogue (`src/aeat/_data/registry/aeat/legal/irnr.toml`)

- Articles 2, 10, 13.1.h, 24, 25.1.a, 25.1.b, and 25.1.f authored
  with `reviewed` status.
- Current treaty entries include `convenio-es-gb-2013:art-6`,
  `convenio-es-ma-1978:art-11`, and `convenio-es-ar-1992:art-19`.

### User profile schema

`src/aeat/_data/registry/aeat/user_profile/schema.toml` lines
360-386 already carry `country_of_fiscal_residence`,
`representante_fiscal_nif`, `representante_fiscal_nombre` on the
`taxpayer` section with selectors `taxpayer.representante_fiscal_nif`
etc. The TaxpayerProfile dataclass already exposes these (covered today
by `test_modelo_210_convenio_rate_resolution.py`). **S393 harmonisation
work appears largely done at the schema layer**; verification only
needed at the M210 engine wiring side.

### M210 engine code

- `src/aeat/application/modelo/_m210_rate.py` — current
  `resolve_m210_rate` implementation.
- `src/aeat/application/modelo/_verification_actions.py` —
  `_rewrite_m210_sentinels` integration.
- `src/aeat/domain/calculations/registry/__init__.py` — exports
  `M210_CONVENIO_MISSING_SENTINEL`, `M210_DEFERRED_TIPO_SENTINEL`,
  `M210_NOT_YET_AUTHORED_SENTINEL`.
- `src/aeat/application/modelo/tests/test_modelo_210_convenio_rate_resolution.py`
  — Olivia (GB/general), Khadija (MA/interest), Felipe (AR/pension),
  ZW non-Convenio, resident pension, sentinel rewrite, and representante
  predicate personas.
- `src/aeat/domain/calculations/registry/tests/test_modelo_210_registry.py`
  — committed registry, art. 25.1.f interest, art. 13.1.h
  imputed-real-estate, and pension tariff grounding.

### 183-day advisory site

NO `_advisories.py` exists under `src/aeat/application/user_profile/`.
The only "183" hits in the source tree are in
`src/aeat/domain/deadlines/_models.py` and `_profiles.py`. There is
no advisory module at the referenced path — this is a corpus-blocker
for S394's advisory cross-reference unless we treat the deadlines
surface as the canonical site.

## Per-Step assessment

### S393 — Convenio + representante_fiscal_nif harmonisation

Schema field already exists; TaxpayerProfile dataclass already
carries it (test fixture lines 72-73). Files to touch: verify M210
engine reads `representante_fiscal_nif` when emitting representante
advisories; possibly add a verification predicate to
`verification_expectations/0001-verification_predicates.toml`
cross-referencing the profile field.

**Status: ready-to-implement** (no corpus block).

### S394 — Convenio MA rate rows (intereses 10%, rendimientos personales 24% / fuente exenta)

`MA/interest = 0.10` is authored and now cites the current
`convenio-es-ma-1978:art-11` legal entry. The older
`boe-a-1985-13340` anchor in this research snapshot was superseded by
the bundled `BOE-A-1985-9280` article-11 corpus excerpt.

New rows needed: `MA/general` at 0.24 (Art 15 rendimientos
personales) and decision on "fuente exenta" — either omitted row
(absence-as-signal) or explicit sentinel/zero. Risk: duplicating
semantics with the baseline `general=0.24` row; the
convenio-replacement-not-stacking doctrine (ADR §D2.4) means an
explicit MA row that equals baseline is the documented Olivia/GB
pattern.

The MA/interest legal-catalogue work is closed; do not add the old
`convenio-espana-marruecos-1985:art-14` anchor for that row. Any future
MA/general row still needs its own treaty article and corpus check.

183-day advisory site is missing — needs design decision on where
it lands.

**Status:** MA/interest treaty grounding closed; MA/general remains
unbuilt if still in scope. The 183-day advisory module location remains
schema-blocked.

### S395 — Art 25.1.b state-pension special tarifa (8% / 30% / 40%)

Closed in the current registry. `m210-convenio-rates.toml` now uses
`DOMESTIC_TARIFF` for `AR/pension` and cites
`convenio-es-ar-1992:art-19` plus `trlirnr-rdleg-5-2004:art-25.1.b`.
The baseline pension shape is represented by
`m210-pension-tarifa-2025`, not by a flat row in
`m210-tipo-gravamen-2025.toml`.

**Resolved schema shape:** existing `m210-tipo-gravamen-2025` is a
`keyed_bracket_table` (flat key→rate). Art 25.1.b is a progressive
three-tranche tariff (8% up to 12,000 EUR; 30% above 12,000 up to
18,700 EUR; 40% above 18,700 EUR). Current code uses
`m210-pension-tarifa-2025` with `data_type = "bracket_table"` and the
resolve op dispatches to it when `tipo_renta == "pension"`.

Legal-catalogue entry `trlirnr-rdleg-5-2004:art-25.1.b` is authored
in the current legal catalogue and grounds the pension tariff branch.

Current tests assert the authored `DOMESTIC_TARIFF` AR/pension row and
the pension tariff branch instead of the old `NOT_YET_AUTHORED`
sentinel path.

**Status:** closed in current registry and covered by
`test_modelo_210_registry.py`.

### S396 — Imputación rentas inmobiliarias no-residente (Art 13.1.h, 1.1% / 2% valor catastral × occupancy)

Closed for the current 2025 registry baseline. Casilla `inmobiliaria`
still carries the 0.24 taxed-rate row under TRLIRNR art. 25.1.a, while
the imputed-real-estate base is now a separate branch:

- `legal."trlirnr-rdleg-5-2004:art-13.1.h"` is authored with corpus
  ref `corpus/normatives/html/trlirnr-rdleg-5-2004.html#a13-1-h`.
- `casillas/0001-casillas.toml` declares the imputed-real-estate
  input facts (`valor_catastral`, `coeficiente_imputacion_inmobiliaria`,
  `dias_imputacion`, `valor_adquisicion`, and
  `valor_comprobado_administracion`) with legal refs to TRLIRNR
  art. 13.1.h/art. 24 and LIRPF art. 85.
- `parameters/0003-m210-imputacion-inmobiliaria-2025.toml` carries the
  1.1%, 2%, and 50% no-cadastral-base values.
- `formulas/0001-m210-base-imponible-2025.toml` dispatches
  `tipo_renta="inmobiliaria"` through `m210_resolve_base_imponible`.

**Status:** legal/corpus/base primitives closed in current registry and
covered by
`test_modelo_210_imputed_real_estate_art_13_1_h_is_catalogued_for_deferred_branch`
plus `test_modelo_210_imputed_real_estate_aeat_guidance_source_is_available`.

## Duplication / shadowing risks

- **MA/general row (S394) vs Convenio-replacement doctrine**: an
  MA row equal to baseline 0.24 is the documented pattern (GB/general
  precedent at line 30-35) — not a true duplication but reviewers
  may flag it. The convenio-rates.toml header explicitly endorses
  this.
- **Pension shape mismatch (S395; CLOSED 2026-06-29)**: the old risk
  was trying to fit a progressive bracket into the existing
  `keyed_bracket_table`. Current code uses separate bracket-table
  parameter `m210-pension-tarifa-2025` and dispatches to it for
  `tipo_renta == "pension"`.
- **AR/pension NOT_YET_AUTHORED row (S395; CLOSED 2026-06-29)**: the row at
  convenio-rates line 45-51 must be either authored with a real
  treaty rate (preferred) or deleted to fall back through baseline.
  If S395 only lands the TRLIRNR baseline without resolving the
  AR-specific treaty row, the Felipe testimonial still surfaces
  `NOT_YET_AUTHORED` and the Step is structurally incomplete.
  Current registry state supersedes this risk: AR/pension now uses
  `DOMESTIC_TARIFF` with `convenio-es-ar-1992:art-19` and
  `trlirnr-rdleg-5-2004:art-25.1.b`, and the pension tariff branch is
  covered by `test_modelo_210_registry.py`.
- **`_advisories.py` referenced by S394 does not exist** — caller
  assumed a module that has never been authored. Either it lands
  as a new module (design decision) or the 183-day advisory
  belongs in `domain/deadlines/_profiles.py` where the `183`
  literal already lives.
- **Legal-catalogue gap (CLOSED 2026-06-29)**: `convenio-rates.toml` cited
  `boe-a-1985-13340` as `legal_ref_anchor` but no `legal."convenio-..."`
  entry existed. Current registry state supersedes this gap: MA/interest
  cites `convenio-es-ma-1978:art-11`, defined in
  `src/aeat/_data/registry/aeat/legal/irnr.toml` with corpus ref
  `corpus/normatives/html/convenio-es-ma-1978-art-11.html#art-11`
  and required text for the 10 percent interest cap.

## Summary of readiness

| Step | Verdict |
|------|---------|
| S393 | ready-to-implement (schema already authored; needs M210 verification-predicate wiring) |
| S394 | treaty legal-entry blocker closed for MA/interest; 183-day advisory placement remains schema-blocked |
| S395 | closed in current registry: Art 25.1.b tariff + AR/pension `DOMESTIC_TARIFF` row are authored and tested |
| S396 | legal/corpus/base primitives closed in current registry; full product scope follows later M210 records |

## Source

Subagent ground-truth discovery 2026-06-03 against #627 W09.P41
S393-S396. Cited file:line evidence:

- `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/parameters/0001-m210-tipo-gravamen-2025.toml`
- `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/parameters/0002-m210-convenio-rates.toml`
- `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/casillas/0001-casillas.toml`
- `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/formulas/0002-m210-tipo-gravamen-2025-resolve.toml`
- `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/bindings/0001-bindings.toml`
- `src/aeat/_data/registry/aeat/legal/irnr.toml`
- `src/aeat/_data/registry/aeat/user_profile/schema.toml:360-386`
- `src/aeat/application/modelo/_m210_rate.py` (`resolve_m210_rate`)
- `src/aeat/application/modelo/_verification_actions.py` (`_rewrite_m210_sentinels`)
- `src/aeat/application/modelo/tests/test_modelo_210_convenio_rate_resolution.py`
- `src/aeat/domain/calculations/registry/tests/test_modelo_210_registry.py`
- `src/aeat/domain/deadlines/_profiles.py` (only existing 183-day site)
- `src/aeat/application/user_profile/` — no `_advisories.py` exists
