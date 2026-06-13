---
tags: ["#exec", "#declaracion-extraction-architecture"]
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'W05.P18.S111'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-26-declaracion-extraction-architecture-W05-P18-S104]]'
---

# declaracion-extraction-architecture W05.P18.S111

Imported the official AEAT Modelo 840 static printed-form PDF into the
bundled official corpus and re-grounded the declaration-PDF label patterns
against the printed form text.

- Modified: `src/aeat/_data/registry/aeat/legal/iae.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/840.toml`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_840_registry.py`
- Created: `src/aeat/_data/corpus/aeat_official/forms/modelo_840/files/01-840-modelo-declaracion-iae-alta-variacion-baja-pdf.pdf`

## Description

Added `aeat-modelo-840-printed-form` as a reviewed AEAT `manual_pdf`
source with checksum, byte count, retrieval date, official URL, and local
corpus path. Updated Modelo 840 model/revision/construct source references
to include the printed form.

Replaced the provisional descriptive `named_label` patterns with printed-form
labels from the official PDF:

- `decl.ejercicio` now anchors on `14 Ejercicio`.
- `decl.tipo-declaracion` now anchors on `15 Declaración de`.

The value-bearing parser round-trip remains open under `W05.P18.S110`
because the static AEAT form is blank. A generated/submitted declaration PDF
or an approved filled-form fixture is still required before asserting parsed
values for Modelo 840.

## Tests

- `uv run --no-sync ruff check src\aeat\domain\calculations\registry\test_modelo_840_registry.py`
- `uv run --no-sync pytest -x src\aeat\domain\calculations\registry\test_modelo_840_registry.py -q`
