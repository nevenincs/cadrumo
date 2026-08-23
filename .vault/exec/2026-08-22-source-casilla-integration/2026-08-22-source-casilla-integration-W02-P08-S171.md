---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:7bd25051ad342449d6455d0823726e3792c3955be8fcf1bf17b2e8ab09114f90'
step_id: 'S171'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# persist typed row-source identity coordinates on encrypted CalculationRevision state

## Scope

- `src/cadrumo/domain/modelos/_calculation_revision.py`

## Description

- Move the generic row identity value object inward and reuse it from the source mesh and revision domain.
- Include row-source identities in canonical revision identity derivation while redacting ordinary serialization.
- Serialize the identity association explicitly only through encrypted calculation-revision persistence.
- Hard-cut the secure catalogue namespace to schema version 3 and refuse missing, orphaned, duplicate, or malformed identity state.
- Add encrypted roundtrip, mutation, at-rest, error-chain confidentiality, namespace, and S170 regression coverage.

## Outcome

Calculation revisions now retain the same typed row-source identity association as the source mesh and bind it into their content-addressed identity. Ordinary dumps and representations omit opaque row identities, while the secure calculation-revision repository explicitly writes the deterministically ordered association inside the encrypted schema-v3 envelope.

Persisted v3 records must explicitly carry the identity member, including an empty member for unidentified M720 rows. Older envelopes and malformed, missing, orphaned, or duplicate coordinates fail closed through a value-free persistence error with no retained exception cause or context.

Independent review reported zero findings. The combined focused review selection passed 19 tests, the namespace suite passed 29, the S170 mesh suite passed 46, and Ruff and the focused type checker were clean.

## Notes

The in-memory model retains a default empty map so existing constructors remain valid until S174 propagation, but secure serialization always writes the member and the v3 reader requires its presence. This is constructor continuity, not persisted reader compatibility.

A concurrent shared commit captured the production implementation while this step was active. The final scoped commit contains the reviewed encrypted mutation/confidentiality tests, namespace pin, plan closure, and lifecycle evidence.
