---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:173b02a052b6d0fe355de0f53e6a0acec598070b7dfecd5acd53d7ef2dceac85'
step_id: 'S38'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# adjudicate the dormant enum members (profile_schedule, UNRESOLVED_BINDING, INVALID_WAIVER, and the two unused exemption reasons): wire each, pin it dormant with a stated reason, or delete it

## Scope

- `src/cadrumo/core/`

## Description

- Census every named member across Python AST references, registry TOML, compiled bundled authority, validators, configuration, tests, and application consumers.
- Delete the `profile_schedule` relation role because no registry revision or production consumer declares it; compare the closed relation-role `Literal` directly with all roles loaded from bundled authority.
- Delete `ModeloVerificationFindingKind.UNRESOLVED_BINDING` and `INVALID_WAIVER` because neither has a production constructor; compare every remaining enum member with qualified production AST consumers and keep encrypted report round-trip coverage on a real retained kind.
- Keep `ExportExemptionReason.PRE_POPULATED_BY_AEAT` as an explicit dormant pin for Modelo 100 casilla 0599 while Modelo 100 has no fixed-width layout.
- Keep and wire `ExportExemptionReason.FEEDS_ADDRESSED_CASILLA`: seventeen declarations hydrate across six Modelo 303 revisions, and reconciliation consumes export-exemption presence to exclude semantic aggregates that a printed declaration cannot expose.
- Replace the obsolete fixed-width-only FEEDS population assertion with a compiled-authority census covering those exact live revisions while preserving the adversarial false-claim validator test.

## Outcome

The unsupported relation role and two unsupported finding identities were destructively removed without aliases or compatibility shims in commit `9070c86e97`. The two exemption reasons remain for distinct evidenced reasons: PRE_POPULATED is deliberately dormant and guarded by its transport precondition; FEEDS is live registry data with an application reconciliation consumer. No member in the named set remains accidentally dormant.

Verification completed on the final tree:

- focused export-exemption module: 9 passed;
- combined finding, exemption, and reconciliation lane: 23 passed;
- Ruff format and lint over all S38 Python surfaces: clean;
- BasedPyright over all S38 Python surfaces: 0 errors, 0 warnings, 0 notes;
- real `aeat app registry verify`: verified 73 modelos, 94 revisions, and 16,800 casillas;
- `git diff --check`: clean.

## Notes

The initial raw-token census changed during concurrent registry work: seventeen FEEDS tokens appeared in Modelo 303 after S37. A fixed-width-only probe first misclassified them because all M303 fixed-width layouts had been retired. The full consumer census corrected that conclusion before delivery: compiled authority retains the declarations and the PDF reconciliation path consumes their exemption fact. The existing S37 note that calls FEEDS unused is therefore historical evidence from its earlier snapshot, not current authority.

The generic calculation diagnostic token `unresolved_binding` remains in a separate source-resolution vocabulary; it is not `ModeloVerificationFindingKind.UNRESOLVED_BINDING` and was not altered.
