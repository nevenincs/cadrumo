---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S07'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Add contract tests proving the canonical tuple and rejecting former product aliases

## Scope

- `src/cadrumo/core/tests/test_product_identity.py`

## Description

- Ground the contract suite in the accepted identity tuple and the live public facade.
- Import the identity API directly and exercise its immutable runtime behavior.
- Pin the closed referent vocabulary and exact facade re-export identity.
- Reject former-product aliases within the new API without asserting that the later package move has already removed `aeat`.

## Outcome

Added five direct, real-behavior tests covering the complete external tuple,
`NamedTuple` assignment refusal, the two-member `IdentityReferent` vocabulary
and invalid-value refusal, object-identical facade exports, and the exact public
API with no former-product aliases. The tests import only production Cadrumo
objects and contain no fake, mock, stub, patch, monkeypatch, skip, or expected
failure mechanism.

## Notes

- The first focused run inherited the repository's distributed pytest defaults and a worker exited before reporting a test result. The serial rerun initially exposed the required `hex_core` marker; adding the package-appropriate marker resolved collection.
- The test intentionally does not assert that `import aeat` fails. Package removal belongs to the later root-relocation Wave.
