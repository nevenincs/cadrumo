---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
body_hash: 'sha256:c4cc68bbaf9c17acbba0f92084d595a38c543db77f20dc134852cf2e17fa9f52'
step_id: 'S23'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Add real-filesystem tests for fresh Cadrumo state and explicit old-state refusal

## Scope

- `src/cadrumo/adapters/persistence/storage/tests/test_cadrumo_state_identity_acceptance.py`

## Description

- Compose the production installed-root, database, encrypted session, namespace, and sealed-archive boundaries in one fresh-state acceptance proof.
- Exercise recognizable former root, database, session, namespace, and bundle states through their production refusal gates.
- Preserve former sentinel bytes and assert that no corresponding canonical state is created.

## Outcome

Fresh state resolves beneath the Cadrumo application root, creates only `cadrumo.db`, derives the `.cadrumo` authentication-session key, writes under the Cadrumo namespace, and round-trips a Cadrumo-marked sealed bundle. Former-state probes are refused without mutation, adoption, fallback, or canonical successor creation.

The clean-filesystem focused run passed ten tests: both new integration scenarios plus the nearest root, database, session, namespace, and bundle boundary tests. Ruff, formatting, and scoped diff checks passed.

## Notes

The integration module deliberately relies on existing production helpers and the established real encrypted runtime harness. It does not repeat exhaustive field-level assertions already owned by S18-S22 tests.

Formal review initially found that canonical session persistence and post-namespace-refusal absence needed stronger proof. The test now round-trips the session through real encrypted storage, inspects raw persisted namespaces, and proves no former or canonical counterpart row was created; re-review closed both findings with no new issues. The final isolated rerun passed both integration scenarios.
