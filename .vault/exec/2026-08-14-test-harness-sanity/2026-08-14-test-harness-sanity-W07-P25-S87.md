---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:f84eb3bbe774c03c66bc5434f0e039b4293d4bffea5d80471565b7ee86fe7339'
step_id: 'S87'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Add a central-harness ownership gate without a file allowlist

## Scope

- `src/cadrumo/tests/test_test_inventory.py`

## Description

- Build a fail-closed central-harness ownership analyzer without a filename allowlist.
- Classify production ownership per assertion across module, class, local-import,
  callable-map, context, binding, loop, mutation, and comprehension dataflow.
- Move every owner-specific central assertion to its narrow core, domain, application,
  inbound, outbound, persistence, entrypoint, or development owner.
- Retain only assertion-level proven structural and cross-owner invariants centrally.
- Restore shared-context cleanup and keychain teardown behavior at the persistence owner.

## Outcome

The live central harness has zero owner-specific behavior findings. The analyzer rejects
matching-marker, marker-mismatch, unknown-owner, class/local-import, same-assertion,
sibling-assertion, completed-context, bound-value, callable-map, Boolean-control, and
comprehension escape shapes while accepting genuine structural data derived from the
inventory subject and real cross-owner identity contracts.

Owner behavior was split from mixed central modules and moved to canonical package
tests. Tautological local tuple assertions were deleted instead of mirrored. Persistence
runtime-context cleanup now has dedicated owner tests, including a real keychain value
proved present inside the shared context and implicitly absent after exit. No filename
allowlist, compatibility bridge, behavioral suppression, or test double was introduced.

The final focused boundary passed 50 tests with one host-dependent `os_keychain` test
deselected. The exact keychain lane remains honestly red on this Windows host with
WinError 1312. Independent review reproduced every prior escape family and found the
final gate clean.

## Notes

Semantic RAG discovery was unavailable, so exact AST/source discovery supplied the
fallback evidence. The stricter gate exposed and actioned 84 node-level violations
across 22 central modules; it was not weakened to accommodate the corpus. Concurrent
peer commits incorporated portions of the owner relocation while this shared-tree step
was active. The final uncommitted delivery consists of the analyzer, central secure-SQL
cleanup removal, and the persistence lifecycle owner; history was not rewritten.
