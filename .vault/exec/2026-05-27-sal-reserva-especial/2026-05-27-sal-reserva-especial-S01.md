---
tags:
  - "#exec"
  - "#sal-reserva-especial"
step_id: "S01"
date: "2026-05-27"
modified: '2026-05-27'
commit: "9aeb99765"
related: []
---

# sal-reserva-especial S01 — SAL/SLL LegalEntityForm + reserva especial régimen (Ley 44/2015)

## What was done

### Domain model

`LegalEntityForm` (in `_models.py`) extended with `SAL = "sal"` and
`SLL = "sll"`. Both sub-forms carry the same IS régimen general rate (25%)
per Ley 44/2015 Art. 13.

Three new `TaxpayerProfile` fields:

- `sal_socios_trabajadores_count: int | None` — number of worker-shareholders
- `sal_reserva_especial_dotada: Decimal | None` — accumulated prior-period reserva
- `sal_capital_social: Decimal | None` — capital social for the 50% cap test

### Schema TOML

`user_profile/schema.toml` updated: `legal_entity_form` enum_values now
includes `"sal"` and `"sll"`. Three new field declarations added for the
SAL-specific fields.

### Legal authority

`legal/is.toml` appended with Ley 44/2015 Art. 1, 2, 13, 14 entries
(BOE-A-2015-11071).

### Registry: M200 casilla

New file `liquidacion-sal-reserva-especial-dotacion.toml` declares
`DP200014:SAL_RESERVA_DOTACION` with
`semantic_role = "is_sal_reserva_especial_dotacion"`, `input_kind = "manual"`.

### Registry: M200 bindings

Two new profile bindings added to `bindings.toml`:
- `modelo-200-2024-profile-sal-reserva-especial-dotada`
- `modelo-200-2024-profile-sal-capital-social`

### Registry: M200 formulas

All five `dispatch_table_entries` lists in `formulas.toml` updated to
include `{ key = "sal", ... }` and `{ key = "sll", ... }` pointing to the
same parameters as `sl`/`sa` (general rate / general bracket).

### CLI surface

Three new flags on `work calculate`:
- `--sal-beneficio-neto` — beneficio neto del ejercicio
- `--sal-reserva-dotada` — reserva acumulada
- `--sal-capital-social` — capital social

All-or-nothing guard raises BadParameter on partial supply.

### Pure computation helper

`_compute_sal_reserva_especial_dotacion(*, beneficio_neto, reserva_dotada,
capital_social) -> Decimal`:

    cap = capital_social * 0.50
    headroom = max(0, cap - reserva_dotada)
    dotacion = min(beneficio_neto * 0.10, headroom)
    → rounded ROUND_HALF_UP, money-2

Guards: capital_social > 0, beneficio_neto >= 0, reserva_dotada >= 0.

## Oracle tests

Spec examples (Aitor G1+G2+G6):

- Year 1: 120k beneficio, 100k capital, 30k reserva
  → dotacion = min(12k, 20k) = `Decimal("12000.00")`
- Year 2: 42k reserva → dotacion = min(12k, 8k) = `Decimal("8000.00")` (capped)
- Cap reached: 50k reserva → `Decimal("0.00")`
- Above cap: 55k reserva → `Decimal("0.00")`
- Guards: zero capital → ValueError, negative beneficio → ValueError

## Files changed

- `src/aeat/domain/deadlines/_models.py` — SAL/SLL enum + 3 profile fields
- `src/aeat/_data/registry/aeat/user_profile/schema.toml` — enum + field declarations
- `src/aeat/_data/registry/aeat/legal/is.toml` — Ley 44/2015 art 1/2/13/14
- `src/aeat/_data/registry/aeat/modelos/200/revisions/.../casillas/liquidacion-sal-reserva-especial-dotacion.toml` — new casilla
- `src/aeat/_data/registry/aeat/modelos/200/revisions/.../records/bindings.toml` — 2 SAL bindings
- `src/aeat/_data/registry/aeat/modelos/200/revisions/.../records/formulas.toml` — 5 dispatch tables updated
- `src/aeat/entrypoints/cli/_modelo.py` — CLI flags + helpers + injection
- `src/aeat/entrypoints/cli/test_modelo.py` — 6 oracle + anti-tautology tests
- `src/aeat/domain/user_profile/test_taxpayer_type_schema_fields.py` — enum set updated

## Verification

6/6 `TestSalReservaEspecialDotacion` tests pass. 37/37 domain + schema
tests pass. ruff: only pre-existing issues.
