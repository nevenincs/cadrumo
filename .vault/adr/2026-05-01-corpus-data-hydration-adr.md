---
tags:
  - '#adr'
  - '#corpus-data-hydration'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - "[[2026-05-01-corpus-data-hydration-research]]"
  - "[[2026-04-12-casilla-db-adr]]"
  - "[[2026-04-12-manual-practico-adr]]"
---

# `corpus-data-hydration` adr: Grounded AEAT Domain Knowledge Strategy | (**status:** `accepted`)

## Problem Statement
The project requires a strictly-typed, version-controlled repository of Spanish tax domain knowledge (the "corpus") to drive calculations, validations, and trilingual help systems. Previous attempts used unverified web search data, which fails the "vigorously grounded" requirement. This ADR formalizes the requirement to source all data exclusively from official AEAT Manuals and BOE Orders for the 2023-2026 period.

## Considerations
- **Legal Accuracy:** AEAT form instructions and BOE orders are the only authoritative sources.
- **Period Coverage:** Support for 2023-2025 is mandatory; 2026 requires future-proofing (placeholder schemas).
- **Trilingualism:** Every record must be available in Spanish (authoritative), English, and Hungarian.
- **Auditability:** Every casilla must be linked to its specific source manual section or BOE article.

## Constraints
- **Human Review Gate:** Autonomous extraction is draft-only. Every committed record must carry a `reviewed_by` and `reviewed_at` stamp.
- **Tooling:** Must use the `src/aeat/domain/casillas` models and loaders.

## Implementation
1. **Source Lock-in:** Map every supported model and year to its specific BOE Order and Manual URL (as identified in `[[2026-05-01-corpus-data-hydration-research]]`).
2. **Extraction Pipeline:**
   - Fetch official PDFs via `aeat manual fetch`.
   - Parse "Diseño de Registro" tables to lock casilla IDs and data types.
   - Extract trilingual descriptions using the Manual structure.
3. **Continuous Pattern:** Establish a standard directory layout `corpus/casillas/<modelo>/<year><period>.json` to be mirrored for every new tax year.

## Rationale
This strategy ensures the application's tax engine is 100% grounded in law. By moving from "fake" skeleton data to "real" citation-backed data, we eliminate the risk of calculation errors based on outdated or misremembered rules.

## Consequences
- **Red CI on Drift:** Any mismatch between extractor code and corpus JSON will fail the coverage test.
- **Review Overhead:** Adding a new year or model requires a one-time human review pass to approve the extracted records.
- **Robust Calcs:** Calculations can now safely use the `formula` field in the corpus, knowing it accurately reflects the official AEAT logic.
