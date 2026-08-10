---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:6583e04a592176960751048fa9770c8a2f9e8eeab598d957143042a162c1db4a'
step_id: 'S43'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Generalize parser-owned variable-envelope recognition from the exact official body, closing-marker, and Variable-total shape, remove the DP200000 name selector, and prove real Modelo 200 plus all five Modelo 303 binaries while retaining malformed and ambiguous refusal with no extent inference

## Scope

- `src/cadrumo/domain/calculations/registry/`
- `dev/registry/`

## Description

- Replace the `DP200000`-specific parser branch with recognition led by the exact official Variable body marker.
- Treat a row that mixes a positive fixed total with `Variable` as a decisive conflict even when no body or closer is present.
- Require complete body, relative-closing, and Variable-total composition, exact source order, contiguous prefix geometry, and no fixed-total inference once a body is present.
- Keep relative closers and Variable-total facts without a body outside envelope recognition because the registered corpus proves they are not unique envelope markers.
- Add source-level regression coverage for Modelo 200, all five pinned Modelo 303 binaries, and the registered M131, M232, and M390 partial-marker sources.

## Outcome

The production parser recognizes the official variable-envelope shape without a modelo or tab-name selector. A raw Variable body marker always enters strict composition validation, and a mixed positive fixed plus Variable total always refuses. Once recognition is active, missing, malformed, duplicate, discontinuous, misordered, or fixed-total-conflicting composition facts raise `RegistryValidationError`.

The final real-source review corrected an earlier broader trigger. A relative `***` closer or Variable-total fact without a body is not independently decisive: ten registered M131, M232, and M390 binaries contain those partial facts as legitimate non-envelope source material. Those binaries remain in the ordinary registered-source parseability gate. The real Modelo 200 source and each 2023, 2024-early, 2024-late, 2025, and 2026 Modelo 303 binary produce the expected typed envelope; fixed-width generation refuses every retained envelope without truncation or inferred total.

Final reproduced verification passed 53 selected parser, intermediate-representation, and generation-boundary tests, then 191 tests across the full `dev/registry/tests` lane. Scoped Ruff passed, and scoped BasedPyright reported zero errors, warnings, and notes.

## Notes

The independent review first recommended treating every raw closer or Variable-total marker as decisive. Real registered-source evidence then disproved that generalization because it reclassified ten legitimate M131, M232, and M390 designs. The accepted final remediation is body-led recognition plus isolated mixed-total refusal. This record was reconciled during S53 after the stale interim wording was detected; no S43 production behavior changed during that documentation correction.
