---
tags:
  - '#exec'
  - '#m200-internal-casilla-discipline'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S02'
related:
  - "[[2026-06-03-m200-internal-casilla-discipline-plan]]"
  - "[[2026-06-03-m200-internal-casilla-discipline-adr]]"
---

# Refuse internal_only=true with non-empty export_refs

## Scope

- `src/aeat/domain/calculations/registry/_schema.py`

## Description

Extended the existing `_validate_input_kind` model_validator chain on `CasillaDefinition` with a new clause: if `internal_only` is `True` and `export_refs` is non-empty, raise `RegistryValidationError` with a message naming the casilla id and the incoherence ("an app-internal casilla cannot also be exported to a fichero record").

## Outcome

The shape (internal_only=True, export_refs=(...)) is refused at load. Pydantic wraps the raise into `ValidationError`; the message substring "internal_only" is the matchable signal for downstream tests.
