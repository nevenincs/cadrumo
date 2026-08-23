---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:9d86e0430581574835cbe70b8e5015453809c0e0787d7c00452518f36a4031fb'
step_id: 'S55'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# Add dynamic CommandSpec exact-set, uniqueness, parent-edge, target, locale-key, schema, policy, side-effect, performance-class, and write-route gates for every current and future root, group, and leaf, forbid every former structural authority and runtime artifact edge, and prove each detector with independently constructed missing, duplicate, orphan, malformed, forbidden-import, and undeclared-node negatives

## Scope

- `src/cadrumo/entrypoints/cli/tests/ and dev/ci/tests/`

## Description

- Traverse the complete immutable command graph and fail closed on missing, duplicate, undeclared, orphaned, malformed, or incompletely classified nodes.
- Discover distributed production specification modules independently from the aggregate and require transitive enrollment without creating a runtime mirror.
- Resolve every authored public handler and result-schema target, validate target kinds, and verify every recursively discovered translation key in all supported catalogues.
- Reject former Typer structural declarations, registrar shapes, command path mirrors, generated command artifacts, development imports, and retired authority modules with planted negatives.
- Replace stale registrar/Typer test introspection with public `CommandSpec` traversal and remove one dormant handler-owned Typer option declaration.
- Correct the eight locale-authority defects exposed by the new universal traversal.

## Outcome

The 361-node production graph now passes exact-set, uniqueness, edge, target, schema, locale, capability, side-effect, performance-class, and write-route gates. Independent detector controls prove missing, duplicate, orphan, malformed, forbidden-import, forbidden-artifact, wrong-target, and undeclared-module failures. Repeated independent adversarial review drove every reported critical, high, medium, and low finding to zero; the accumulated bypass corpus remains executable regression evidence.

## Notes

The initial two test files landed concurrently in commit `378c5f342a`; the effective S55 review and verification include that commit plus this closure remainder. A broad CLI-directory collection remains externally red on unrelated stale tests that import deleted private behavior symbols; the exact S55 suite avoids treating those collection failures as S55 evidence. No registry data or unrelated concurrent locale work was staged.
