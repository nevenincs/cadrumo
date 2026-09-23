# Modelo 193 later-year export: evidence record (2026-09-23)

Measured on 2026-09-23. Re-check these sources at the end of each session. A later order or design would change the answer.

## What the official sources say

| Source | Date | What it establishes |
|---|---|---|
| AEAT record-design catalogue, modelos 100–199, entry 193: <https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/modelos-100-199.html> | page updated 2026-08-25 | One design only: `DR_Modelo_193_2025.pdf`, "Orden EHA/3377/2011 (actualizado por Orden HAC/1430/2025)". No XLS, and no file labelled 2026. |
| Design PDF: <https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_100_199/DR_Modelo_193_2025.pdf> | 2025 design | The current record layout. The PDF itself was not opened in this pass. |
| Orden HAC/1430/2025, BOE-A-2025-25389: <https://www.boe.es/buscar/doc.php?id=BOE-A-2025-25389> | BOE 2025-12-12, in force 2025-12-13 | Applies to Modelo 193 "por primera vez, a las declaraciones informativas correspondientes al ejercicio 2025". It adds the type-2 CÓDIGO ISIN field (positions 193–204) and changes CLAVE CÓDIGO (79), CÓDIGO EMISOR (80–91) and NATURALEZA DEL DECLARANTE (208). No end year. |
| Orden HAC/1504/2024, BOE-A-2024-27528: <https://www.boe.es/buscar/doc.php?id=BOE-A-2024-27528> | BOE 2024-12-31 | First applies to ejercicio 2024. Superseded for 2025 by HAC/1430/2025. |
| Orden EHA/3377/2011, consolidated, BOE-A-2011-19396: <https://www.boe.es/buscar/act.php?id=BOE-A-2011-19396> | latest version 2025-12-12 | No amendment from 2026 is referenced. |
| AEAT GI12 procedure page: <https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GI12.shtml> | updated 2026-09-08 | Its regulations end at HAC/1430/2025. There is no ejercicio-2026 notice. |
| AEAT notice of 2025-12-12: <https://sede.agenciatributaria.gob.es/Sede/todas-noticias/2025/diciembre/12/modificacion-determinadas-declaraciones-informativas.html> | 2025-12-12 | 193's first year is 2025. In that order, only Modelo 195 starts in 2026. |
| AEAT campaign pages (informativas 2025): <https://sede.agenciatributaria.gob.es/Sede/declaraciones-informativas/campana-declaraciones-informativas.html> | updated 2026-07-13 | No ejercicio-2026 campaign page exists yet. |
| Hacienda draft orders: <https://www.hacienda.gob.es/SGT/NormativaDoctrina/Proyectos/16092025-proyecto-OM-informativas-2025.pdf> (2025 draft) and <https://www.hacienda.gob.es/sgt/normativadoctrina/proyectos/09032026-main-proyecto-om-dac8.pdf> (the 2026 DAC8 draft, which does not cover 193) | 2025-09-16 and 2026-03-10 | No 2026 draft covering 193 was found. The full list of 2026 drafts was not exhausted. |

## Conclusion

No design dated after ejercicio 2025 exists. The 2025 design has no end year, so on the order's own wording it governs ejercicio 2026 until amended. That is a reading of the order text; no AEAT statement confirms it. A new amendment would most likely appear in November or December 2026 (the last two were published on 12 Dec 2025 and 31 Dec 2024).

## What this means for Cadrumo

- The registry already reflects this. Modelo 193 revision `2025-y-siguientes` declares `year_from = 2025` with no `year_to`, so ejercicio 2026 resolves to the 2025 design. No authoring is needed or possible until a new order appears.
- The real gap is implementation. `src/cadrumo/application/aggregation/m193_phase_materialization.py` builds the PENDING (accrual-year) and SETTLED_PRIOR_ACCRUAL (payment-year) disclosure rows, but no export path consumes it. Its only other references are its error registration and locale keys. It also needs capital-income evidence, whose public capture is currently refused together with Modelo 123 (`_modelo_aggregate_cli.py`: "Modelo 123 public capture is incomplete…").
- Whether capital evidence capture may open while Modelo 123 filing stays refused on the unresolved count authority (see `2026-09-22-retenciones-m123-count-evidence.md`) is a scope decision recorded for the coordinator. Until it is taken, Modelo 193 export stays unsupported, with that typed reason.