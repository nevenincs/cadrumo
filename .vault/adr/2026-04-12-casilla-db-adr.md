---
tags:
  - "#adr"
  - "#casilla-db"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-casilla-db-research]]"
  - "[[2026-04-12-data-storage-adr]]"
  - "[[2026-04-12-trilingual-i18n-adr]]"
---

# Architecture Decision Record: Casilla DB

## Status
Accepted

## Context
Issue #23 needs a real, trilingual, diff-friendly casilla catalogue with strict validation, CLI support, and a human-review workflow. The original issue text targeted `src/aeat/domain/schema/casillas.py`, but that directory is owned by issue #9 and is still in flight. The solution must also avoid hard imports from in-flight siblings while still stabilizing a usable public API on this branch.

## Decisions

### 1. Package location
We will implement the feature in a new public subpackage: `aeat.domain.casillas`.

Rationale:
- avoids a direct collision with issue #9 ownership of `aeat.domain.schema`,
- matches the project precedent for additive subpackages,
- keeps the public import surface stable now (`from aeat.domain.casillas import ...`) and easy to preserve after rebases.

### 2. Persisted storage layout
Canonical casilla files live under `corpus/casillas/<modelo>/<period>.json`.

Rationale:
- aligns with issue #23 acceptance criteria,
- keeps the review surface git-friendly,
- preserves hand-curated data outside the operational SQL store from issue #10.

### 3. Boundary model strategy
Every persisted or loaded casilla structure is a strict pydantic v2 model.

Rationale:
- follows the project-wide pydantic mandate,
- gives schema validation at file, CLI, and loader boundaries,
- keeps the public API free of bare dictionaries and ad hoc tuples except where explicitly modeled.

### 4. Upstream dependency strategy
Until sibling issues land, the package will use local Protocol stubs for external dependencies:
- schema/formula/validation types from issue #9,
- LLM extraction and translation interfaces from issue #21,
- manual/rule references from issue #25.

Rationale:
- stabilizes the call sites without violating branch ownership,
- keeps the rebase path mechanical: replace Protocol imports with real imports once upstream branches merge.

### 5. Initial dataset scope
The initial corpus will target the most recent fully completed periods as of 2026-04-12:
- `MODELO_130` -> `2025Q4`
- `MODELO_303` -> `2025Q4`
- `MODELO_390` -> `2025`

Rationale:
- avoids in-progress filing periods,
- matches the issue request for the most recent complete period,
- aligns the initial corpus with the quarterly/annual nature of the three modelos.

### 6. LLM workflow rule
LLM output is draft-only. The canonical corpus is never written directly by an extraction or translation run.

Implementation rule:
- `aeat casillas extract` writes a temp draft file.
- `aeat casillas translate` writes a temp draft file.
- canonical files under `corpus/casillas/` must be explicitly reviewed and saved by the operator.
- `aeat casillas verify` rejects records missing `reviewed_by` or `reviewed_at`.

### 7. Translation and completeness rule
`label` and `help` use the shared trilingual `Translatable` shape, but Spanish remains the authoritative required language for every committed record.

Rationale:
- preserves issue #20’s trilingual primitives,
- enforces the authoritative-language rule that matters most for legal/source fidelity.

## Consequences
- The package will carry a small amount of temporary Protocol scaffolding that must be replaced on rebase after issues #6, #9, #21, and #25 merge.
- The initial corpus is manually curated and therefore intentionally conservative rather than exhaustive automation.
- Verification logic becomes a first-class gate, not an optional helper.
- Callers outside the package must import only from `aeat.domain.casillas`, never from internal implementation modules.
