---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:c1edc13df827e9d958cd6776023220c93c7294bf561ec1a934d4a60b27ae54f2'
step_id: 'S20'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
## Scope

- Canonicalize the verification discrepancy cause vocabulary at the registry schema authority.
- Delete the application-owned duplicate declaration and public forwarding export.
- Sweep application, registry, and direct tests to the single canonical type.

## Description

- Rename `VerificationDiscrepancyCause` to registry-owned `DiscrepancyCause`.
- Remove application `DiscrepancyCause` and its package-facade export without an alias, bridge, or tolerant reader.
- Preserve the authored lowercase registry tokens as the sole wire vocabulary and reject retired uppercase application tokens.
- Add structural proof for one declaration, direct owner identity, application-facade absence, and the canonical lowercase token.
- Run focused application and registry behavior, Ruff, strict BasedPyright, fixed-point searches, and diff hygiene.
- Obtain a formal VaultSpec code review.

## Outcome

- One `DiscrepancyCause` declaration remains at the registry schema owner.
- The obsolete type name has zero references across `src` and `dev`; the application facade has no forwarding symbol.
- Application verdict JSON now uses the canonical lowercase tokens, and uppercase legacy tokens remain invalid.
- Focused registry/helper validation passed 71 tests; the full application verification owner suite passed 37 tests.
- Independent review passed 83 tests, retried one transient fingerprint refusal successfully, and returned PASS with no findings.
- Ruff, strict BasedPyright, prohibited-construct scans, and scoped diff checks passed.

## Notes

- Unrelated indentation work in `application/verification/tests/test_verify.py` was present in the shared worktree and is excluded from this Step.
- No compatibility alias, facade, tolerant reader, fake, stub, patch, skip, or mirrored business logic was introduced.
