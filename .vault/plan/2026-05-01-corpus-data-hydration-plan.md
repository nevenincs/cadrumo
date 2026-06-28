---
tags:
  - '#plan'
  - '#corpus-data-hydration'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - "[[2026-05-01-corpus-data-hydration-research]]"
  - "[[2026-05-01-corpus-data-hydration-adr]]"
---

# `corpus-data-hydration` exhaustive execution plan

This plan provides a step-by-step, modelo-by-modelo tracker for the manual, semantic extraction of AEAT domain knowledge. Every single casilla in the corpus will be updated with authentic Spanish text and trilingual translations (EN, HU) sourced directly from official manuals and BOE Diseño de Registro documents.

## Proposed Changes
We are moving from placeholder skeleton data to a legally grounded repository. This is a manual task. I will process each tax form group, identifying the official documentation, extracting the semantic meaning for every casilla, and updating the JSON definitions.

## Task Tracker

- **Phase 1: IRPF (Direct Estimation & Annual)**
  1. **Modelo 130** (IRPF Pago Fraccionado)
     - Sourced from: Manual de Renta 2025, Orden HAC/262/2025.
     - Casillas 01 to 19.
  2. **Modelo 131** (IRPF Módulos)
     - Sourced from: Manual de Renta 2025, Orden HAC/1347/2024.
  3. **Modelo 100** (IRPF Anual)
     - Full annual schema extraction.

- **Phase 2: IVA (Monthly/Quarterly & Annual)**
  1. **Modelo 303** (IVA Autoliquidación)
     - Sourced from: Manual de IVA 2025, Orden HAC/819/2024.
     - Casillas 01 to 110.
  2. **Modelo 390** (IVA Resumen Anual)
     - Annual consolidation schema.
  3. **Modelo 347, 349, 369** (Informativas & Ventanilla Única)
     - VIES and Intra-community rules.

- **Phase 3: Retenciones (Withholdings)**
  1. **Modelo 111** (Trabajo y Profesionales)
  2. **Modelo 115** (Arrendamientos)
  3. **Modelo 123** (Rendimientos Capital Mobiliario)
  4. **Modelo 180, 190, 193** (Annual summaries for the above)

- **Phase 4: Sociedades & Otros (Corporate & Special)**
  1. **Modelo 200** (IS Anual)
  2. **Modelo 202** (IS Pagos a cuenta)
  3. **Modelo 232** (Operaciones Vinculadas)
  4. **Modelo 036, 037** (Declaración Censal)
  5. **Modelo 720, 840** (Bienes Extranjero & IAE)

## Verification
- **Success Criteria:** Zero casillas in the `corpus/casillas` directory contain "Etiqueta", "Casilla XX", or "Ayuda genérica".
- **Grounded Verification:** Every JSON file for years 2023, 2024, 2025, and 2026 (draft) has the correct official Spanish labels and instructions.
- **CI Status:** `uv run pytest src/aeat/domain/casillas/test_corpus_coverage.py` passes.
- **Manual Audit:** CLI `aeat casillas list` reflects the real legal domain knowledge.
