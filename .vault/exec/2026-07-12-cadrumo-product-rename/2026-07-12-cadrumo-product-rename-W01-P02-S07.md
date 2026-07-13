---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-13'
step_id: 'S07'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Add contract tests proving the canonical tuple and rejecting former product aliases

## Scope

- `src/cadrumo/core/tests/test_product_identity.py`

## Description

- Ground the contract suite in the binding executable ADR's contextual identity tuple and the live public facade.
- Import the identity API directly and exercise its immutable runtime behavior.
- Pin the closed referent vocabulary and exact facade re-export identity.
- Reject former-product aliases while preserving `aeat` as the sole human CLI and `AEAT` as the external authority.
- Exercise frozen-field rejection through a runtime `setattr` call so static analysis and runtime behavior are both honest.

## Outcome

The six direct, real-behavior tests pin `CADRUMO` for identity contexts,
`Cadrumo` for sentence prose, lowercase `cadrumo` machine identifiers, `aeat`
as the sole human CLI, `cadrumo-mcp` as the MCP executable, and `AEAT` as the
external authority. They also prove runtime mutation refusal, the closed
two-member `IdentityReferent` vocabulary, object-identical facade exports, and
the absence of former-product aliases from the identity API. The tests import
only production Cadrumo objects and contain no fake, mock, stub, patch,
monkeypatch, skip, or expected-failure mechanism.

## Notes

- `setattr(PRODUCT_IDENTITY, field_name, "Changed")` reaches the real frozen runtime path and raises `AttributeError`; it replaces a statically invalid assignment and needs no type-ignore suppression.
- Focused identity tests, Ruff lint, Ruff formatting, and Ty all pass on the S07 surface.
- The test intentionally does not treat `aeat` as a former alias: the binding ADR reserves it as the human executable. It rejects only obsolete product-identity exports; installed-package rejection is owned by later artifact acceptance steps.
