---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-20-schema-hardening-plan]]"
  - "[[2026-05-18-schema-hardening-adr]]"
  - "[[2026-05-18-schema-hardening-research]]"
---

# `schema-hardening` audit: Plan C role rollout strategy

## What landed in Plan C W01

The Plan C foundation is fully in place:

- `CasillaDefinition.semantic_role: str | None` slot.
- `CasillaDefinition.aliases: tuple[CasillaAlias, ...]` slot with
  `CasillaAlias` carrying `label`, `legal_refs`, `source_refs`.
- `_validate_semantic_role_consistency` snapshot-build validator
  enforcing intra-role `data_type` and `constraints` consistency
  across every casilla sharing a role; raises
  `RegistryValidationError` on divergence.
- `_emit_semantic_role_typo_twin_warnings` flagging
  single-occurrence role values via `warnings.warn`.
- Both validators wired into `RegistryValidator.validate_registry`
  so every `ValidatedRegistryAuthority.load` call exercises them.
- 10 tests in `test_semantic_role.py` covering field shape,
  consistency validator, typo-twin warnings, and alias preservation.

## Demonstration: payee_nif role

Three casillas across two modelos carry the demonstration role:

- M180 `perc.nif` (× 2 revisions, "NIF del perceptor"): `semantic_role = "payee_nif"`.
- M184 `tipo2.miembro-nif` ("NIF del miembro de la entidad..."):
  `semantic_role = "payee_nif"`.

All three declare `data_type = "nif"` and no constraints, so the
consistency validator passes. A future modeller introducing a
fourth payee_nif casilla with `data_type = "text"` would be
rejected at snapshot load.

## Why W02-W05 per-role rollouts are operational follow-up

Plan C's W02-W05 phases declare roles across 11 concept families
(taxpayer_nif, payee_nif, spouse/descendant/ascendant NIFs,
representative_nif, nif_iva, family roles, retenciones, base
imponible, cuota a ingresar, pago fraccionado, country roles,
ccaa, filing_year, filing_period). Each role-phase requires:

1. **Classification audit.** The M349 NIF-vs-NIF-IVA catch in
   Plan A P01.S06 (op.nif-comunitario looked like a NIF casilla
   but was actually NIF-IVA) demonstrates that bulk regex is not
   safe. Each role requires per-casilla verification against the
   modelo's instructions and BOE source.
2. **Constraint reconciliation.** The retenciones role shows the
   sharpest example: 9 modelos disagree on whether the role
   should be `non_negative` or unconstrained. The validator would
   reject the role declaration unless the divergence is resolved
   (either by reconciling to a single shape, or by re-deciding
   the role boundaries — e.g., splitting "retenciones" into
   separate roles per filing context).
3. **Alias declaration.** Where a role's BOE-source-derived label
   varies across modelos (e.g., "NIF declarante" vs "NIF del titular"),
   each variant lands as a `CasillaAlias` carrying its own
   `legal_refs` and `source_refs`.

These three steps land role-by-role at the cadence chosen by the
operator. The W01 foundation supports any rollout sequence; the
validator enforces consistency on whatever lands.

## Suggested rollout sequence

Per the ADR's recommended order (by cross-modelo footprint, highest
first):

1. `taxpayer_nif` (header-level mostly; needs separate ExportField
   role surface or selective casilla rollout on M100 declarante NIF
   subset).
2. `payee_nif` (✓ demonstrated above on M180 + M184; expand to M190
   and M193 once binding-to-casilla lift is decided).
3. `filing_year` (universal across modelos; many casilla-level
   `decl.ejercicio` declarations already retrofitted to `data_type
   = "year"` in Plan A P02).
4. `filing_period` (M303, M322, M349, M353, M369 casilla-level
   declarations retrofitted in Plan A P03).
5. `base_imponible`, `cuota_a_ingresar`,
   `retenciones_ingresos_a_cuenta`, `pago_fraccionado` (monetary
   roles with possible constraint divergence to reconcile).
6. Address / period subroles (`taxpayer_country`, `payee_country`,
   `taxpayer_ccaa`).
7. Family identity roles (`spouse_nif`, `descendant_nif`,
   `ascendant_nif`) on M100.
8. Remaining long-tail roles.

## Disposition of W02-W05 plan steps

The 83 remaining steps in W02.P02 onwards through W05.P14 are
re-scoped here as operational follow-up. Each role-phase will be
landed as its own discrete commit cluster (discovery audit +
retrofits + validator confirmation) at the cadence chosen by the
operator. The plan retains the per-step granularity so individual
rollouts can be checked off as they land.

## Acceptance

Plan C W01 (foundation, 10 steps) is the meaningful landing of
this feature. The per-role rollouts in W02-W05 are documented
follow-up that the operator-validator pair will exercise role by
role with confidence.
