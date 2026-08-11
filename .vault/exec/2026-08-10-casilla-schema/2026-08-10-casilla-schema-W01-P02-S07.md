---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:513c6021c9792f4f3bef762bd34884ba7f5610e11877156e250cade3b1385206'
step_id: 'S07'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# Reconcile internal-only completeness manifest rows

## Scope

- `src/cadrumo/domain/calculations/registry/_record_design_coverage.py`
- `src/cadrumo/domain/calculations/registry/_validate_completeness.py`
- The bundled Modelo 200 completeness manifest and direct registry tests.

## Description

- Exclude every `internal_only` casilla before single- or multi-segment completeness derivation.
- Remove the leaked Modelo 200 internal ceiling row from the checked-in manifest.
- Reject any future completeness-manifest row whose canonical casilla is application-internal.
- Prove the invariant with real bundled registry objects and a mutation bite test.

## Outcome

Completeness manifests now represent the official calculation closure only. The loaded registry has zero internal-only manifest overlap, the exact focused tests pass, the real registry verifier remains green at 73 modelos and 94 revisions, and Ruff, formatting, focused BasedPyright, and scoped diff checks are clean. Formal independent review passed with no findings.

## Notes

Temporarily disabling the exclusion made the real drift test fail on an internal Modelo 100 ceiling node, then restoring it returned the focused lane to green. The broader owning lane has one unrelated concurrent Modelo 303 legal-reference drift failure; it does not exercise this change.
