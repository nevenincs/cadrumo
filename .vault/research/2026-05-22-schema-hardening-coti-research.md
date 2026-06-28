---
tags:
  - '#research'
  - '#schema-hardening-coti'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-22-schema-hardening-research]]'
  - '[[2026-05-22-schema-hardening-audit]]'
---



# `schema-hardening-coti` research: `quoted-fund-coti-source-slice`

This research scopes the next optional/numeric burn-down slice after the
2026-05-22 `sin` implementation. The target is the Modelo 100 2025
`gp_fondos_coti` family currently hidden by broad optional-token stripping.

## Findings

### Source basis

Local BOE corpus for `orden-hac-277-2026.html` states that Modelo 100 2025
creates a new specific section to facilitate reporting operations involving
participations or shares of quoted funds and quoted index SICAVs.

Local BOE corpus for `ley-35-2006.html` distinguishes quoted investment funds
and quoted index SICAVs in the collective-investment and capital-gains rules.

The committed Modelo 100 2025 registry places casillas `2225` through `2236`
under `gp_fondos_coti`, separate from the general `gp_fondos` rows such as
`0312`, `0313`, `0315`, and related result rows.

Prior audits record `gp_fondos_coti` as a 2025-only new section and mark its
role names as coherent source-visible singletons rather than typos.

### Current warning exposure

Disabling broad optional/numeric stripping exposes six `coti` warning pairs:

- `irpf_ganancia_fondos_coti_valor_transmision_global`
- `irpf_ganancia_fondos_coti_valor_transmision_renta_vitalicia`
- `irpf_ganancia_fondos_coti_valor_adquisicion_global`
- `irpf_ganancia_fondos_coti_ganancia`
- `irpf_ganancia_fondos_coti_exenta_renta_vitalicia`
- `irpf_perdida_fondos_coti_importe_computable`

Each near role is the same field name without `coti` in the general
`gp_fondos` family.

### Interpretation

`coti` is a source-family marker for a specific Modelo 100 section, not an
optional spelling fragment. Treating it as globally optional would hide the
distinction between quoted-fund rows and general investment-fund rows.

The safe mechanical burn-down is the same pattern used for `sin`:

- remove `coti` from broad optional-token stripping;
- mark the exposed 2025 quoted-fund rows as explicit `intentional_singleton`
  entries with source-grounded reasons;
- add tests proving unmarked `coti` roles are not axis siblings while the
  committed reviewed rows remain warning-clean.

### Blocked scope

This research does not approve global removal of all remaining optional tokens.
It does not approve normalization for `agr`, `aav`, `b`, `anio`, `precio`, or
numeric tokens.

The row `irpf_perdida_fondos_coti_importe_obtenido` is related but not part of
the six current warning exposures in this slice. Prior audit flagged its name
as potentially inaccurate. That role should not be changed here without a
separate rename policy.

### Recommendation

Proceed with a narrow `coti` burn-down plan. Keep the implementation limited to
the current six warning-exposed roles and source-backed tests. Re-run the
committed Modelo 100 and Modelo 200 warning probe after the edit to confirm the
warning surface remains at zero.
