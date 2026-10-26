---
tags:
  - '#research'
  - '#retenciones-workflow'
date: '2026-09-24'
modified: '2026-09-24'
body_schema: 'body-v2'
body_hash: 'sha256:9ccf5ce4996ed4cb67e9007b29e9d389049d0c21f03eca19de4f08ccdd356ae8'
related: []
---

# `retenciones-workflow` research: `Modelo 123 count authority`

Question: how does Modelo 123 revision `2024-y-siguientes` count "Número de rentas" (casillas 01, 02 and 03) when one income entitlement is paid in instalments, or recognized before it is settled? Conclusion as of 2026-09-23: no official AEAT, BOE or DGT text defines the unit, so no filing-grade count can be derived. Filing-grade Modelo 123 stays refused and the capability stays advisory.

## Findings

### The 2024 revision relabelled the field without defining it

The AEAT record-design catalogue lists the 2024-and-later Modelo 123 design as Orden EHA/3435/2007, as revised by Orden HAC/56/2024. The 2024 form has separate "Número de rentas" boxes for participation in equity and for other rents, plus a total. These replace the older "N.º de perceptores" field. Orden HAC/56/2024 states that its new annex I exists only to add a breakdown of dividends and other participation income. It defines no count unit and has no instructions annex. The consolidated Orden EHA/3435/2007 (article 1, annex II) carries the change but adds nothing on counting.

### Older and neighbouring definitions do not transfer

- AEAT's printed instructions for the pre-2024 form (M-123E-80/0.30, citing RD 439/2007 and RD 1777/2004) define casilla 01 as the total number of taxpayers who obtained movable-capital income. That defines the old field only. The copy read was on a third-party host (caisistemas.es/enlaces/instr_123.PDF), so it is AEAT text without an official locator.
- The Modelo 111 instructions (AEAT sede, updated 2026-06-09) count persons for "Nº de perceptores". They are silent on repeated payments and cover a different modelo.
- DGT V1151-14 repeats the "contribuyentes" reading only as the consultant's own statement, not as a ruling on counting.

### Timing is grounded; the count is not

RIRPF art. 94.1 (RD 439/2007) and RIS art. 65.1 (RD 634/2015) place the withholding when the income becomes exigible, or when it is paid if payment comes first. RIRPF art. 108.1 declares it in that quarter, and DGT V3165-21 applies the same rule to dividends. None of these define how many "rentas" an instalment or a later settlement represents.

### What would settle it

Any one of these would: the casilla help inside the AEAT 2024 online form (OVME-COMN/123/E2024, which needs a login), an AEAT instruction or FAQ page for the 2024 revision, or a DGT consulta vinculante on how "número de rentas" is counted. The question to put is whether each instalment of one identifiable entitlement counts as a separate renta in its withholding period or the entitlement counts once, and whether that changes when the income is exigible before it is settled.

### Product state when measured

The capture-time refusal in `src/cadrumo/entrypoints/cli/_modelo_aggregate_cli.py` was a hard-coded English `typer.BadParameter`: not localized, not typed, and not naming this missing authority. Which boundary refuses, and how, is settled by the evidence-capture scope ADR.

## Sources

- https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/modelos-100-199.html
- https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_100_199/archivos_24/DR123e24.xls
- https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-1772
- https://www.boe.es/buscar/act.php?id=BOE-A-2007-20485
- https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GH04.shtml
- RIRPF arts. 94.1 and 108.1 (RD 439/2007); RIS art. 65.1 (RD 634/2015); DGT V3165-21; DGT V1151-14 (cited from the 2026-09-23 pass, not re-fetched)
- `src/cadrumo/entrypoints/cli/_modelo_aggregate_cli.py`
