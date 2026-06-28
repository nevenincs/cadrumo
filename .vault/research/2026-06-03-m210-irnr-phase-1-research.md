---
tags:
  - '#research'
  - '#m210-irnr-phase-1'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# `m210-irnr-phase-1` research: `M210 IRNR Phase 1 corpus discovery for S393-S396`

Subagent corpus-discovery pass for #627 W09.P41.S393-S396
(Olivia round-16 + Felipe round-26 M210 IRNR Phase 1 work).

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
  (0.24). NO `pension` row (deferred to task #229 → S395).
- `parameters/0002-m210-convenio-rates.toml` — convenio rate table
  with rows: `GB/general` (0.24), `MA/interest` (0.10),
  `AR/pension` (`NOT_YET_AUTHORED` sentinel, anchor
  `BOE-CONVENIO-AR-NOT-FOUND`).
- `bindings/0001-bindings.toml` —
  `m210-2025-profile-country-of-fiscal-residence` binding.
- `verification_expectations/`, `application_links/`,
  `constructs/`, `workbook_parity_refs/` directories exist.

### Legal catalogue (`src/aeat/_data/registry/aeat/legal/irnr.toml`)

- Articles 2, 10, 24, 25.1.a, 25.1.f authored with `reviewed`
  status.
- Missing: `art-25.1.b` (pension special tarifa) — explicitly
  reserved for task #229.
- Missing: `art-13.1.h` (imputación rentas inmobiliarias).
- Missing: BOE-A-1985 Convenio MA legal entry (referenced as
  `boe-a-1985-13340` anchor in convenio-rates but not authored in
  legal catalogue).

### User profile schema

`src/aeat/_data/registry/aeat/user_profile/schema.toml` lines
360-386 already carry `country_of_fiscal_residence`,
`representante_fiscal_nif`, `representante_fiscal_nombre` on the
`taxpayer` section with selectors `taxpayer.representante_fiscal_nif`
etc. The TaxpayerProfile dataclass already exposes these (used in
`test_modelo_210_phase1.py`). **S393 harmonisation work appears
largely done at the schema layer**; verification only needed at
the M210 engine wiring side.

### M210 engine code

- `src/aeat/application/modelo/_actions.py` — `_resolve_m210_rate`,
  `_rewrite_m210_sentinels`.
- `src/aeat/domain/calculations/registry/__init__.py` — exports
  `M210_CONVENIO_MISSING_SENTINEL`, `M210_DEFERRED_TIPO_SENTINEL`,
  `M210_NOT_YET_AUTHORED_SENTINEL`.
- `src/aeat/application/modelo/test_modelo_210_phase1.py` — Olivia
  (GB/general), Khadija (MA/interest), Felipe (AR/pension), ZW
  non-Convenio, resident-deferred personas already wired.

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

`MA/interest = 0.10` already authored (line 37-43 of
convenio-rates.toml). Anchor `boe-a-1985-13340` cited but
legal-catalogue entry is missing.

New rows needed: `MA/general` at 0.24 (Art 15 rendimientos
personales) and decision on "fuente exenta" — either omitted row
(absence-as-signal) or explicit sentinel/zero. Risk: duplicating
semantics with the baseline `general=0.24` row; the
convenio-replacement-not-stacking doctrine (ADR §D2.4) means an
explicit MA row that equals baseline is the documented Olivia/GB
pattern.

Must add `legal."convenio-espana-marruecos-1985:art-14"` and
`:art-15` legal-catalogue entries pointing at `BOE-A-1985-13340`,
with `corpus_ref` to real BOE HTML.

183-day advisory site is missing — needs design decision on where
it lands.

**Status: corpus-blocked** (need BOE-A-1985 Convenio MA HTML in
corpus + legal-catalogue authoring) + schema-blocked (advisory
module location).

### S395 — Art 25.1.b state-pension special tarifa (8% up to €12k, 30% above)

Replaces `NOT_YET_AUTHORED` marker in `m210-convenio-rates.toml`
for `AR/pension` and addresses the baseline `pension` row absence
in `m210-tipo-gravamen-2025.toml`.

**Schema shape mismatch**: existing `m210-tipo-gravamen-2025` is a
`keyed_bracket_table` (flat key→rate). Art 25.1.b is a progressive
two-tranche bracket (8% / 30% at €12k threshold). Either a new
parameter table (`m210-pension-bracket-2025`) with `data_type =
"bracket_table"` is needed, or the resolve op must learn to
dispatch to a different parameter when `tipo_renta == "pension"`.
Touches `_formula_runtime.py` evaluator.

Legal-catalogue entry `trlirnr-rdleg-5-2004:art-25.1.b` must be
authored (currently absent by design per header note).

Felipe testimonial (AR/pension) currently asserts the
`NOT_YET_AUTHORED` sentinel branch — that test needs updating once
the row lands.

**Status: schema-blocked** (bracket-table shape decision) +
corpus-blocked (BOE consolidated text for Art 25.1.b + need to
verify €12k threshold + 8/30 figures).

### S396 — Imputación rentas inmobiliarias no-residente (Art 13.1.h, 1.1% / 2% valor catastral × occupancy)

Casilla `inmobiliaria` exists at baseline rate 0.24 — that's the
*taxed* rate. The imputación calculation produces the *base*
(deemed income), distinct from the rate. So S396 introduces
base-derivation primitives, not another rate row.

Files needed: new casillas (e.g., `valor_catastral`,
`catastral_revisado_flag`, `fraccion_ocupacion`,
`imputacion_inmobiliaria`), a new formula authoring the 1.1%/2% ×
occupancy × valor formula, parameter table
`m210-imputacion-coeficientes-2025`.

Legal-catalogue entry `trlirnr-rdleg-5-2004:art-13.1.h` is missing.
The IRPF parallel (`irpf.toml`) may already have the analogous
Art 85 imputación entry to reuse-by-reference but cannot substitute
the IRNR citation.

The header note in `m210-tipo-gravamen-2025.toml` says "deduction
routing via Art 24.5 deferred to Phase 2" — S396 may overstep
that boundary; needs ADR clarification.

**Status: corpus-blocked** (Art 13.1.h BOE text) + schema-blocked
(new casilla + parameter shape + Phase 1/2 scope decision).

## Duplication / shadowing risks

- **MA/general row (S394) vs Convenio-replacement doctrine**: an
  MA row equal to baseline 0.24 is the documented pattern (GB/general
  precedent at line 30-35) — not a true duplication but reviewers
  may flag it. The convenio-rates.toml header explicitly endorses
  this.
- **Pension shape mismatch (S395)**: trying to fit a progressive
  bracket into the existing `keyed_bracket_table` would shadow the
  schema's semantic intent. A separate `bracket_table` parameter +
  dispatch in `_resolve_m210_rate` is the clean path.
- **AR/pension NOT_YET_AUTHORED row (S395)**: the row at
  convenio-rates line 45-51 must be either authored with a real
  treaty rate (preferred) or deleted to fall back through baseline.
  If S395 only lands the TRLIRNR baseline without resolving the
  AR-specific treaty row, the Felipe testimonial still surfaces
  `NOT_YET_AUTHORED` and the Step is structurally incomplete.
- **`_advisories.py` referenced by S394 does not exist** — caller
  assumed a module that has never been authored. Either it lands
  as a new module (design decision) or the 183-day advisory
  belongs in `domain/deadlines/_profiles.py` where the `183`
  literal already lives.
- **Legal-catalogue gap**: `convenio-rates.toml` cites
  `boe-a-1985-13340` as `legal_ref_anchor` but no `legal."convenio-..."`
  entry exists. This is already a latent grounding gap under
  `registry-calculation-legal-grounding`.

## Summary of readiness

| Step | Verdict |
|------|---------|
| S393 | ready-to-implement (schema already authored; needs M210 verification-predicate wiring) |
| S394 | corpus-blocked (BOE-A-1985 + legal entries) + schema-blocked (advisory module location) |
| S395 | corpus-blocked (Art 25.1.b BOE text + figures) + schema-blocked (progressive-bracket shape + dispatch) |
| S396 | corpus-blocked (Art 13.1.h BOE text) + schema-blocked (new casillas + Phase 1/2 scope) |

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
- `src/aeat/application/modelo/_actions.py` (`_resolve_m210_rate`, `_rewrite_m210_sentinels`)
- `src/aeat/application/modelo/test_modelo_210_phase1.py`
- `src/aeat/domain/deadlines/_profiles.py` (only existing 183-day site)
- `src/aeat/application/user_profile/` — no `_advisories.py` exists
