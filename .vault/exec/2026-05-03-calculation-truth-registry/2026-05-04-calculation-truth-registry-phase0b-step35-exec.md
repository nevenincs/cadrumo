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



# `calculation-truth-registry` `phase0b` `step35`

Grounded legal references in local BOE corpus text so legal authority cannot be
only a reviewed catalogue label.

- Modified: `corpus/normatives/rd-439-2007.json`
- Modified: `registry/aeat/legal/irpf.toml`
- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Modified: `src/aeat/domain/calculations/registry/_legal.py`
- Created: `src/aeat/domain/calculations/registry/_text.py`
- Modified: `src/aeat/domain/calculations/registry/_validate.py`
- Modified: `src/aeat/domain/calculations/registry/test_catalogue_verification.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

Added required-text anchors to legal references and connected registry
validation to the local BOE corpus when a source root is available. Legal
catalogue checks now verify that required statutory anchors are present in the
referenced corpus file while preserving existing review-status and negative
citation checks.

The Modelo 130 IRPF legal catalogue entry now requires Article 110 anchors for
the direct-estimation rate, agricultural rate, Ceuta/Melilla reduction, previous
year net-income reduction, housing deduction cap, and higher voluntary
percentage rule. The local `rd-439-2007` corpus entry was expanded with Article
110 text from the BOE consolidated regulation.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_catalogue_verification.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_formula_runtime.py -q`
- `uv run ruff check src/aeat/domain/calculations/registry registry/aeat/modelos/130.toml registry/aeat/legal/irpf.toml`
- `uv run ty check src/aeat/domain/calculations/registry`
- `uv run pytest src/aeat/domain/calculations/registry src/aeat/application/filing/test_schema_completeness.py src/aeat/application/filing/test_filing.py src/aeat/application/filing/test_import.py src/aeat/application/filing/test_export.py -q`
- `git diff --check corpus/normatives/rd-439-2007.json registry/aeat/legal/irpf.toml src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/_legal.py src/aeat/domain/calculations/registry/_text.py src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/test_catalogue_verification.py`

Focused legal and registry tests passed, the wider registry and filing slice
passed with 121 tests, and static checks passed.
