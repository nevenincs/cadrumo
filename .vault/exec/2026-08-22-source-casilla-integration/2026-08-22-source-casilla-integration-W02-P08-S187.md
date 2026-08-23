---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:09c6ba99478fc2c7de826b66f29216e7f18be166e17582a0b297abf9e48f0e0e'
step_id: 'S187'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# persist row-indexed casilla values and direct-materialization provenance through encrypted CalculationRevision state

## Scope

- `src/cadrumo/domain/modelos/_calculation_revision.py`
- `src/cadrumo/application/modelo`
- `src/cadrumo/adapters/persistence/storage/_namespace_registry.py`
- `src/cadrumo/adapters/persistence/profile/tests/test_source_mesh_revision_roundtrip.py`
- `src/cadrumo/core/tests/test_persisted_format_enrolment_binding.py`

## Description

- Extend the sole calculation-revision identity spine with canonical row-casilla values and complete direct-materialization provenance.
- Persist both maps through application calculation and revision construction without projecting them into scalar, observation, formula, or replay-input channels.
- Cut the encrypted calculation-revision catalogue from schema v3 to v4 without a compatibility shim or upgrader.
- Require explicit canonical list wire forms under secure validation, redact both row-casilla maps from ordinary serialization, and reject duplicate or incomplete custody state.
- Enforce exact target/source coordinate, identity, Decimal value, rule, and work-unit revision agreement.
- Prove encrypted round-trip, redaction, deletion/duplicate refusal, hash participation, namespace version, durability classification, and reordered-row refusal.

## Outcome

Encrypted `CalculationRevision` v4 now preserves typed row-casilla values and their full direct-materialization route. Both axes participate in the content-addressed revision identity; any coordinate, amount, source identity/fingerprint, rule identity, or rule version change produces a different revision. Secure loads require both fields explicitly even when empty, while ordinary dumps expose neither financial row values nor opaque activity identities.

The application carries the original source-mesh maps into persistence and binds every materialization rule version to the parent work-unit revision. The persisted-format census now classifies v3/v4 namespace tokens and the two build-generated registry artefact formats it previously left unbound. Independent Sol review returned PASS with no findings.

## Notes

Most production changes landed in shared commit `619a274431` while the step was under review; the final target/source row-index regression and durability-census remediation remain in this lifecycle close. Targeted gates passed: 48 domain tests, 6 application threading tests, 13 remediation/persistence tests, Ruff, and diff integrity. Six unchanged legacy tests expecting raw Pydantic errors instead of the repository's existing `CalculationRevisionPersistenceError` were reproduced at parent HEAD and are not caused by S187.
