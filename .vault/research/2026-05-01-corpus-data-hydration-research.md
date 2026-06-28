---
tags:
  - '#research'
  - '#corpus-data-hydration'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - "[[2026-04-12-casilla-db-adr]]"
  - "[[2026-04-12-manual-practico-adr]]"
  - "[[2026-04-12-normatives-adr]]"
---

# `corpus-data-hydration` research: Grounded AEAT Domain Knowledge (2023-2026)

Research into official Spanish Tax Agency (AEAT) sources to hydrate the `corpus/casillas` with legally grounded, citation-backed data for the supported 2023-2026 period.

## Findings

### 1. Authoritative Manuals (Manuales Prácticos)
AEAT publishes annual interactive manuals. For the supported period:
- **Renta (IRPF):**
  - [Renta 2025](https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2025.html)
  - [Renta 2024](https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2024.html)
  - [Renta 2023](https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2023.html)
- **IVA (VAT):**
  - [IVA 2025](https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/iva-2025.html)
  - [IVA 2024](https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/iva-2024.html)
  - [IVA 2023](https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/iva-2023.html)

*Note: 2026 manuals are typically published in late 2026 (IVA) and Spring 2027 (Renta).*

### 2. Legal Sources (Órdenes Ministeriales & BOE)
The definitive schemas and instructions are defined in BOE orders:
- **Modelo 303 (IVA):**
  - **2025:** `Orden HAC/1347/2024` (Modules/Simplified regime).
  - **2024:** `Orden HAC/819/2024` (Introduced "Autoliquidación Rectificativa" and 0%/2% rates).
  - **2023:** `Orden HFP/1124/2022` (Casillas 150-155 for energy/donations).
- **Modelo 390 (Annual IVA):**
  - **2024:** `Orden HAC/1167/2024` (Adaptive layout for new rates).
  - **2023:** `Orden HFP/1397/2023`.
- **Modelo 130 (IRPF Prepayments):**
  - **2025:** `Orden HAC/262/2025` (Updates for Libro Registro integration).

### 3. Record Layouts (Diseño de Registro)
The physical structure of the submission files is documented at:
- [IRPF Layouts (100-199)](https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/modelos-100-199.html)
- [IVA Layouts (300-399)](https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/modelos-300-399.html)

### 4. Critical Domain Shifts (2023-2026)
- **Rectificativa Consolidation:** 2024 marks the move away from separate refund requests towards integrated self-correction in the form itself.
- **Book-Entry Integration:** Progressive automation from "Libros Registro" to Models 130, 131, and 303.
- **VeriFactu (July 2025):** `Orden HAC/1177/2024` mandates standardized billing records, which will drive 2026 corpus requirements.

## Proposed Strategy
Continuous hydration must follow the "Draft -> Human Review -> Commit" cycle:
1. **Source Tracking:** One entry in `corpus/sources.json` per manual URL and BOE Order.
2. **Schema Extraction:** Automate extraction of casilla IDs and offsets from the "Diseño de registro" PDF/HTML tables.
3. **Citation Synthesis:** Map every record in `corpus/casillas` to a specific section in the `Manual Práctico` or BOE Article.
4. **Trilingual Pipeline:** Authoritative Spanish first, followed by manual-review-approved English and Hungarian translations.
