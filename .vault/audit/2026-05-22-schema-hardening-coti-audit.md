---
tags:
  - '#audit'
  - '#schema-hardening-coti'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - "[[2026-05-22-schema-hardening-coti-plan]]"
  - "[[2026-05-22-schema-hardening-coti-adr]]"
  - "[[2026-05-22-schema-hardening-coti-research]]"
---



# `schema-hardening-coti` audit: `quoted-fund-coti-audit`

## Scope

This audit executes the quoted-fund `coti` optional-token burn-down plan. It
records the official and committed source basis, the exact warning exposure
when only `coti` is removed from broad optional-token stripping, and the
implementation boundary for the slice.

## Findings

### P01.S01 source context

The source context supports treating `coti` as a source-family marker, not as
an optional typo-warning token:

- Local BOE corpus for `orden-hac-277-2026.html` records that Modelo 100 2025
  creates a new specific section for operations involving quoted funds and
  quoted index SICAVs.
- Local BOE corpus for `ley-35-2006.html` distinguishes quoted investment
  funds and quoted index SICAVs in the capital-gains and collective-investment
  provisions.
- The committed Modelo 100 2025 registry places the quoted-fund data-entry
  rows under `gp_fondos_coti`, separate from the general `gp_fondos` rows.

Decision: `coti` must not remain a globally optional semantic-role token.

### P01.S02 exact warning exposure

The committed warning probe loaded Modelo 100 and Modelo 200 and removed only
`coti` from `_SEMANTIC_ROLE_OPTIONAL_AXIS_TOKENS`. It produced exactly six
warnings:

| casilla | role | source section |
|---|---|---|
| `2227` | `irpf_ganancia_fondos_coti_valor_transmision_global` | `gp_fondos_coti` |
| `2228` | `irpf_ganancia_fondos_coti_valor_transmision_renta_vitalicia` | `gp_fondos_coti` |
| `2229` | `irpf_ganancia_fondos_coti_valor_adquisicion_global` | `gp_fondos_coti` |
| `2230` | `irpf_ganancia_fondos_coti_ganancia` | `gp_fondos_coti` |
| `2231` | `irpf_ganancia_fondos_coti_exenta_renta_vitalicia` | `gp_fondos_coti` |
| `2234` | `irpf_perdida_fondos_coti_importe_computable` | `gp_fondos_coti` |

The related role `irpf_perdida_fondos_coti_importe_obtenido` is in the same
section but did not appear in the warning-exposure probe. It remains outside
this implementation slice because prior audit flagged it as a rename concern.

## Recommendations

Proceed with the narrow implementation approved by the ADR:

- remove `coti` from broad optional-token stripping;
- mark only the six warning-exposed rows above as `intentional_singleton`;
- add tests proving unmarked `coti` roles are not axis siblings;
- leave other optional tokens and numeric stripping unchanged.

## P02 implementation

Implemented the approved narrow burn-down:

- Removed `coti` from `_SEMANTIC_ROLE_OPTIONAL_AXIS_TOKENS`.
- Marked exactly six Modelo 100 2025 `gp_fondos_coti` rows as
  `intentional_singleton`: `2227`, `2228`, `2229`, `2230`, `2231`, and `2234`.
- Added source-grounded reasons referring to the separate Modelo 100 2025
  `gp_fondos_coti` section for quoted funds and quoted index SICAVs.
- Updated semantic-role tests so unmarked `coti` roles are not axis siblings
  and warn, while committed reviewed rows remain warning-clean by explicit
  singleton metadata.

Rows intentionally left unchanged:

- `2226` and `2232` were not warning-exposed.
- `2233` remains outside this slice because prior audit flagged a possible
  rename issue.
- `2235` and `2236` are result rows, not current warning-exposed data-entry
  rows.

## P03 verification

Verification run:

- `uv run pytest src/aeat/domain/calculations/registry/test_semantic_role.py -q`
  passed, 44 tests.
- `uv run ruff check src/aeat/domain/calculations/registry/_validate_semantic_roles.py src/aeat/domain/calculations/registry/test_semantic_role.py`
  passed.
- `uv run pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_singleton_semantic_role_warning_count_does_not_regress src/aeat/domain/calculations/registry/test_modelo_100_registry.py src/aeat/domain/calculations/registry/test_committed_registry.py -q`
  passed, 77 tests.
- Direct committed Modelo 100 and Modelo 200 warning probe returned 0 warnings.
