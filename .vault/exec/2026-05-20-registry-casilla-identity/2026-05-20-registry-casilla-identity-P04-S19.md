---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S19'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` `P04.S19`

Re-pointed the Modelo 200 page-014 export field binding for casilla
`00562` from the ECPN occurrence to the new Liquidación `DP200014`
cuota íntegra casilla.

- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0017-modelo-200-page-014.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/0156-estado-de-cambios-patrimonio-neto-ii-operaciones-con-socios-o-propietarios.toml`

## Description

PDF page 14 of the Modelo 200 declaration is the Liquidación page; its
fichero-BOE record segment is `DP200014`. The export field
`modelo-200-page-014-casilla-00562` (offset 646) therefore belongs to
the Liquidación cuota íntegra casilla, not the
Estado-de-cambios-patrimonio-neto distribución-de-dividendos casilla.
Before this Step the field carried `casilla = "00562"`, which resolved
through the ECPN casilla's bare-number `id` — the mis-binding the ADR
identifies.

Two coordinated edits re-point the binding:

- In `0017-modelo-200-page-014.toml`, the export field's `casilla` is
  changed from `"00562"` to the segment-qualified
  `"DP200014:00562"`, the `id` of the Liquidación cuota íntegra casilla
  registered in S15.
- In the ECPN fragment `0156-...operaciones-con-socios-o-propietarios.toml`,
  `modelo-200-page-014-casilla-00562` is removed from the ECPN `00562`
  casilla's `export_refs`. The ECPN casilla no longer claims a
  Liquidación-page export field; its remaining refs (page-010, page-032,
  page-042, did) — the ECPN-segment pages — are untouched.

The bidirectional export-ref symmetry holds: the field's `casilla`
resolves to `DP200014:00562`, whose `export_refs` (declared in S15)
lists `modelo-200-page-014-casilla-00562`; the validator's
`casilla_by_id[field.casilla].export_refs` membership check passes.

## Tests

`pytest` on `test_modelo_200_registry.py`, `test_referential_integrity.py`,
and `test_modelo_parity_coverage.py` — 48 passed. A direct inspection
confirms the page-014 `00562` field binds to `DP200014:00562`
(label "Liquidación III - Base imponible - Cuota íntegra", segmento
`DP200014`) and that the ECPN `00562` casilla no longer lists the
page-014 export field. A `RegistryValidator` sweep over all 26 modelos
confirms every modelo still loads valid (`fail=0`).

## Review-fix note

The P04 code review (commits S13–S19) found that the export re-point
landed in S19 covered only the page-014 `00562` field. Three sibling
Liquidación export fields still resolved to their ECPN occurrences. The
review-fix completes the re-point and normalises the DP200014B id
scheme:

- page-014 `00552` and `00558`, and page-014b `00611`, are re-pointed to
  the segment-qualified Liquidación casillas (`DP200014:00552`,
  `DP200014:00558`, `DP200014B:00611`), mirroring the S15/S19 pattern.
  The three export-ref ids are added to the new Liquidación casilla
  fragments and removed from the ECPN casillas, which retain their
  genuinely-ECPN export fields (page-010/043/did for `00552`,
  page-011/032/042 for `00558`, page-011/042 for `00611`).
- The pre-existing Liquidación IV casillas `00592` and `00599` carried
  bare `id`s within segmento `DP200014B`, inconsistent with the
  segment-qualified ids the six S13–S18 casillas use. Their ids are
  normalised to `DP200014B:00592` and `DP200014B:00599`; all five of
  their export-field `casilla` bindings, the
  `modelo-200-cuota-ejercicio-a-ingresar-devolver` formula `target` and
  `00592` expression arg, the foundation construct `casillas` list, and
  the cuota-chain verification-expectation `computed_casillas` are
  updated to the qualified ids so the strict `casilla.formula` ↔
  `formula.target` equality check and the construct-closure id lookup
  resolve. Their labels are updated to the full AEAT 2024 Diseño
  descripción form (sheet `DP200014B`).

Verification: all 48 tests across `test_modelo_200_registry.py`,
`test_referential_integrity.py`, and `test_modelo_parity_coverage.py`
pass; a `RegistryValidator` sweep confirms all 26 modelos load valid
(`fail=0`); M200 has no dangling export field and bidirectional
export-ref symmetry holds across the whole revision.
