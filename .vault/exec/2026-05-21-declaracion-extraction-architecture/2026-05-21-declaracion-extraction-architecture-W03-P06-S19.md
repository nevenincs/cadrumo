---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
step_id: 'S19'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
---

# `declaracion-extraction-architecture` `W03.P06.S19`

COMPLETED on 2026-05-22 — M303 now has a source-grounded `declaracion_pdf` profile for registered, extractable result-chain casillas.

## 2026-05-22 superseding execution

The earlier blocker below was true for the semantic-only M303 registry, but the current split registry now carries numeric printed casilla IDs in `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/casillas/0001-casillas.toml`. I added `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/extraction_profiles/0001-modelo-303-declaracion-pdf.toml` and wired `modelo-303-declaracion-pdf` into the `modelo-303-iva-autoliquidacion` construct.

The profile is deliberately limited to casillas that are both registered and visible in the sanitized real 2024-1T declaration fixture: `27`, `45`, `64`, `66`, and `71`. Printed boxes `46`, `69`, `87`, and `110` appear in the fixture text, but they are not registered as numeric casilla IDs in the current `casillas/0001-casillas.toml`, so they remain out of the profile rather than bypassing referential integrity.

Legal/source grounding:
- `legal_refs`: LIVA IVA/result articles plus RIVA and Orden EHA/3786/2008 references already used by the registered M303 result casillas.
- `source_refs`: `aeat-dr-303-2025`, `boe-modelo-303-2008-form`.

Verification:
- `uv run --no-sync pytest -x src\aeat\adapters\inbound\declaracion\test_parser_boundary.py` -> 8 passed.
- `uv run --no-sync pytest -x src\aeat\domain\calculations\registry\test_committed_registry.py` -> 41 passed.
- `uv run --no-sync ruff check src\aeat\adapters\inbound\declaracion\_parser.py src\aeat\adapters\inbound\declaracion\test_parser_boundary.py` -> passed.

## Prior 2026-05-21 blocker record

## Description

Execution halted per plan mandate: "If a modelo's real casilla set cannot be confidently sourced from the corpus, STOP and report."

**Blocker:** The M303 registry exclusively uses semantic slug casilla IDs (`iva.repercutido.general`, `iva.cuota-devengada-total`, etc.). The `numeric_casilla` match strategy requires that the `casilla_id` in the extraction profile target matches text printed literally on the PDF form (the regex anchors `re.escape(casilla_id)` at line start). No M303 casilla ID in the registry equals a printed form number. The printed form uses boxes `01`–`110`; the registry has no casilla with those IDs.

A minimal approach of targeting only the 4 compensation/result casillas whose `number` fields are numeric (`iva.resultado` with `number = "69"`, etc.) would not work either — the extraction would anchor on `iva.resultado` not `69`.

**Required prerequisite:** The M303 registry must be extended to add casilla entries with numeric IDs matching the printed form boxes (as M111 does with `id = "01"` .. `id = "30"`). This is a registry restructure step outside the scope of W03's "author extraction profiles" mandate.

**Recommendation:** Add a follow-up task to extend M303 with numeric printed-form casilla IDs (covering at minimum the result chain: 27=total devengada, 45=total deducible, 46=régimen general, 69=resultado, 78=compensación aplicada, 87=compensación pendiente, 110=compensación anterior periods). Once those IDs exist in the registry the `numeric_casilla` profile becomes straightforward.

## Tests

No files modified. Baseline test suite (41/41 committed registry, 7/7 parser boundary) confirmed passing before halt.
