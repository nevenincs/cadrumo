---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
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
