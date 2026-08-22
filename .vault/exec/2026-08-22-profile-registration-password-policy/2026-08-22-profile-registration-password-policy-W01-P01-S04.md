---
tags:
  - '#exec'
  - '#profile-registration-password-policy'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:43e12adb6a3bf385bfc7e26198186242716691639f6ac62b2f50b1f6d8941b2d'
step_id: 'S04'
related:
  - "[[2026-08-22-profile-registration-password-policy-plan]]"
---




# Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then prove scalar and byte boundaries, surrogate refusal, safe reasons, advisory independence, and composed/decomposed exact preservation

## Scope

- `src/cadrumo/core/tests/test_credentials.py`

## Description

- Ground the live core implementation and governing decision with semantic discovery, then confirm the exact contract symbols and current Step state.
- Add a focused unit matrix for the scalar, strict UTF-8 byte, surrogate, exact-sequence, result-shape, immutability, slots, and advisory-strength guarantees.
- Pin byte-first refusal precedence where the 1,025-byte case necessarily also exceeds 256 valid Unicode scalars.
- Validate the owned test surface with Ruff and focused pytest.

## Outcome

The canonical profile-password assessment now has executable coverage at 14, 15, 256,
and 257 scalars; at 1,024 and 1,025 strict UTF-8 bytes; and for unencodable surrogate
input. The tests demonstrate that composed and decomposed sequences are measured as
submitted, the assessment contains only typed non-secret facts, and its advisory strength
cannot determine acceptance.

## Notes

The repository's default parallel pytest invocation suffered an xdist worker crash before
running the focused module. Re-running the same module serially exposed the required marker
gate; after assigning the established core unit markers, the serial focused run passed all
11 cases. No production defect was found and no production file was changed.
