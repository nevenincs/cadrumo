---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-04'
modified: '2026-05-04'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-04-calculation-authority-evidence-tiering-adr]]'
  - '[[2026-05-04-calculation-authority-evidence-tiering-research]]'
---



# `calculation-truth-registry` `phase0b` `step34`

Grounded Modelo 130 formula and parameter definitions in local AEAT instruction
source text and corrected signed intermediate calculations surfaced by that
grounding.

- Modified: `registry/aeat/modelos/130.toml`
- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Modified: `src/aeat/domain/calculations/registry/_validate.py`
- Modified: `src/aeat/domain/calculations/registry/test_registry_schema.py`
- Modified: `src/aeat/domain/calculations/registry/test_formula_runtime.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

Added strict source citations to registry formula and parameter schema objects.
The validator now requires formula and parameter citations to be listed in
`source_refs`, to cite official-source guidance evidence, and to resolve to
text present in the reviewed local source corpus when a source root is supplied.

Modelo 130 formula and parameter definitions now cite AEAT instruction text for
the fractional payment rates and casilla-level calculations. The same source
grounding exposed signed intermediate behaviour in casillas 07 and 11, which
has been corrected so negative values remain signed before casilla 12 applies
its zero floor.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_formula_runtime.py -q`
- `uv run ruff check src/aeat/domain/calculations/registry registry/aeat/modelos/130.toml registry/aeat/legal/irpf.toml`
- `uv run ty check src/aeat/domain/calculations/registry`
- `uv run pytest src/aeat/domain/calculations/registry src/aeat/application/filing/test_schema_completeness.py src/aeat/application/filing/test_filing.py src/aeat/application/filing/test_import.py src/aeat/application/filing/test_export.py -q`
- `git diff --check registry/aeat/legal/irpf.toml registry/aeat/modelos/130.toml src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_formula_runtime.py corpus/aeat_official/instructions/modelo_130/files/modelo-130-instrucciones.html`

Focused registry tests passed, the wider registry and filing slice passed with
119 tests, and static checks passed.
