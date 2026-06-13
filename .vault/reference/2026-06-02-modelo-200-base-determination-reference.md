---
tags:
  - '#reference'
  - '#modelo-200-base-determination'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-modelo-200-base-determination-adr]]"
---



# `modelo-200-base-determination` reference: `Modelo 200 IS base-determination formula spec + registry-structure prerequisite (grounded)`

Grounded against the AEAT Manual práctico de Sociedades 2024 (Cap. 5) and
Ley 27/2014 (LIS) Arts. 10, 25, 26. Produced to feed Phase 2 of the
`modelo-200-base-determination` ADR — the durable derivation that makes the
silent zero-base under-declaration impossible. Verdict: **NEEDS-MORE-GROUNDING**
— the canonical formula is known, but it cannot be authored against the current
registry until missing casilla records are created and an export number-collision
is disambiguated. This document records the spec and the prerequisite so a
deliberate, coordinated implementation can proceed without guessing.

## Grounded formula (AEAT Manual de Sociedades 2024, Cap. 5)

- **Base imponible previa** — casilla `00550` = `00501` (resultado de la cuenta
  de PyG antes de IS) + `00417` (total correcciones de AUMENTO) − `00418` (total
  correcciones de DISMINUCIÓN).
- **Base imponible** — casilla `00552` = `00550` − `01032` (reserva de
  capitalización, Art. 25 LIS, sign minus) − `00547` (compensación de bases
  imponibles negativas, Art. 26 LIS, sign minus), with a **non-negative clamp**:
  the `00547` term cannot drive `00552` below zero (it is capped at the value of
  `00550`); «si el resultado es cero, consignar cero».
- **Order:** resultado contable → correcciones (aumentos/disminuciones) → base
  imponible previa (`00550`) → reserva de capitalización → compensación BIN →
  base imponible (`00552`).

## Subtotals — must NOT be double-summed with their leaves

`00550` is a subtotal (of `00501 + 00417 − 00418`); `00417`/`00418` are the
aumentos/disminuciones column subtotals (sums of the individual correction rows);
`00501` is itself the resultado-contable subtotal. When deriving `00550`, sum
ONLY the three subtotals `00501 + 00417 − 00418` — never `00501` plus the
individual `00355..00414` correction leaves (double-count). The registry already
classifies the leaf correcciones by semantic_role (`is_correcciones_aumentos`
~42, `is_correcciones_disminuciones...` ~38, plus ~18 specific-role) — these feed
`00417`/`00418`, not `00550` directly.

## REGISTRY-STRUCTURE PREREQUISITE (hard blocker)

The formula CANNOT be authored against today's registry:

- Only `DP200014:00552` and `01032` (reserva) exist as addressable
  liquidación-segmento records. `DP200014:00550`, `DP200014:00547`,
  `DP200014:00501`, `DP200014:00417`, `DP200014:00418` do **not** exist.
- The bare numbers `00550`/`00547`/`00417`/`00418` currently resolve to UNRELATED
  Estado-de-Cambios-en-el-Patrimonio-Neto (ECPN) records: `00550` = «Prima de
  emisión», `00547` = «Reducciones de capital», `00417`/`00418` = «Ajustes por
  errores». Referencing the bare numbers in a formula would silently aggregate
  the wrong ECPN values → wrong tax.
- The page-014 export layout references `00550`/`00547` as **bare numbers** while
  `00552` is segmento-qualified. The loader's mapping of page-014 bare
  `00550`/`00547` to liquidación-vs-ECPN must be settled so the formula and the
  export round-trip agree.

Implementation order: (1) create the segmento-qualified `DP200014` liquidación
records (`00501`, `00417`, `00418`, `00550`, `00547`) with legal/source grounding;
(2) disambiguate the page-014 export fields; (3) author `00550 = 00501 + 00417 −
00418` and `00552 = clamp(00550 − 01032 − 00547, ≥0)`; (4) add roundtrip tests
(this changes a persisted casilla's `input_kind` manual→computed and the revision
content address). Coordinate with the active M200 campaign (C65 jurisdiction /
tributacion bindings touch the same surface).

## Unresolved items to ground before coding (do NOT guess)

- Exact leaf membership of `00417` (aumentos `00355..00413`) and `00418`
  (disminuciones `00356..00414`) — transcribe from the manual IF `00417`/`00418`
  are derived from leaves rather than entered/stored subtotals. Recommended:
  derive `00550` from the stored `00417`/`00418` subtotals once they exist, to
  sidestep leaf-enumeration risk.
- The BIN clamp engine semantics (`max(00550 − 01032 − 00547, 0)` vs raw
  subtract) — transcribe the manual's exact sign/cap sentence before coding.
- `00547` minoración by `00545`/`01509` (per the manual) — confirm whether the
  `00552` step consumes a pre-minorado `00547` or applies the minoración here.
- If `01032` (reserva) is ever auto-derived: use the 2024 rate (10% / 15% uplift),
  NOT the Ley 7/2024 2025 rate.

## Source

AEAT Manual práctico de Sociedades 2024, Cap. 5 (cálculo de la base imponible);
Ley 27/2014 Arts. 10, 25, 26. Grounding run: workflow `wf_652f0f40-34c`. Drives
ADR `2026-06-02-modelo-200-base-determination` Phase 2.
