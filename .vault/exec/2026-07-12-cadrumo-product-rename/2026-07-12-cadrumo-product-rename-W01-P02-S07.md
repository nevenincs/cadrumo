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
- Replace enumerated former-product alias guesses with an exact `product_identity.__all__` contract, object-identical facade projection, a closed facade `AEAT*` surface, and rejection of module fallback lookup.
- Preserve `aeat` as the sole human CLI and `AEAT` only as the explicit external-authority short name and referent.
- Exercise frozen-field rejection through a runtime `setattr` call so static analysis and runtime behavior are both honest.

## Outcome

The nine collected direct, real-behavior cases pin `CADRUMO` for identity contexts,
`Cadrumo` for sentence prose, lowercase `cadrumo` machine identifiers, `aeat`
as the sole human CLI, `cadrumo-mcp` as the MCP executable, and `AEAT` as the
external authority. They also prove runtime mutation refusal, the closed
two-member `IdentityReferent` vocabulary, the exact four-name identity-module
public API, object-identical facade exports, the single allowed `AEAT*` facade
export, and the absence of a fallback lookup hook. Any new identity export or
former-product facade alias such as `AEAT_REPOSITORY` now fails the closed
contract without depending on a guessed blacklist. The tests import only
production Cadrumo objects and contain no fake, mock, stub, patch, monkeypatch,
skip, or expected-failure mechanism.

## Notes

- `setattr(PRODUCT_IDENTITY, field_name, "Changed")` reaches the real frozen runtime path and raises `AttributeError`; it replaces a statically invalid assignment and needs no type-ignore suppression.
- Focused identity tests, Ruff lint, Ruff formatting, and Ty all pass on the S07 surface.
- The current production module and facade already satisfy the closed contract, so remediation changes only the durable test and S07 execution evidence; no runtime code change is needed.
- The test intentionally does not treat `aeat` as a former alias: the binding ADR reserves it as the human executable. Installed-package rejection is owned by later artifact acceptance steps.
