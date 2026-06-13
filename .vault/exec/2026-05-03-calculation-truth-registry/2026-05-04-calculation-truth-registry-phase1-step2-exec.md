---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-04'
modified: '2026-05-04'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-04-calculation-truth-registry-phase-0c-review-audit]]'
---



# `calculation-truth-registry` `phase1` `step2`

Added explicit support/removal decision scaffolding to the central registry
schema and validator.

- Modified: `src/aeat/domain/calculations/registry/_ids.py`
- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Modified: `src/aeat/domain/calculations/registry/_snapshot.py`
- Modified: `src/aeat/domain/calculations/registry/_validate.py`
- Modified: `src/aeat/domain/calculations/registry/__init__.py`
- Modified: `src/aeat/domain/calculations/registry/test_registry_schema.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

Introduced `SupportRemovalDecisionDefinition` as an explicit registry object
for filing-grade removals. The schema only permits
`remove_from_filing_grade`, so it does not create disabled, compatibility, or
placeholder support states.

Registry validation resolves the decision's legal and source references and
fails if a removal decision names an active registry surface such as an export
layout, extraction profile, application link, workbook parity ref, verification
expectation, live cross-reference, or deadline window. This enforces deletion
from active filing-grade support rather than retaining a shadow surface.

Snapshots now expose support/removal decisions as a typed map for consumers.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_registry_schema.py -q`
- `uv run ruff check src/aeat/domain/calculations/registry/_ids.py src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/_snapshot.py src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/__init__.py`
- `uv run ty check src/aeat/domain/calculations/registry/_ids.py src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/_snapshot.py src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/__init__.py`

Registry schema tests passed with 26 tests. Static checks passed.
