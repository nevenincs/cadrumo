---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:eb459b2fefccfda5496855febc91bfe977a0bb319067afa0049ebee0c1d79edf'
step_id: 'S59'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# Mutate filing-envelope and auxiliary-header catalogue source kinds away from record_design and prove snapshot refusal plus a weakened-guard mutation bite.

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_embedded_envelope_source_authority.py`

## Description

- Mutate the live M303 filing-envelope and M232 auxiliary-envelope-header catalogue entries from `record_design` to `manual_pdf`, then assert `build_snapshot` refuses each declaration.
- Exercise `_validate_embedded_envelope_source_authority` directly with the same two catalogue mutations so the embedded source-kind guard itself must report the refusal.
- Run a disposable in-memory copy that weakens only the `record_design` condition and confirm both guard-specific cases fail deliberately.

## Outcome

The registry build refuses both shipped envelope shapes when their declared catalogue source is no longer a record design. The focused module passes 14 tests and Ruff passes. The isolated weakened-guard run admits both mutations and exits non-zero, so the regression cannot remain green if the guard is removed or weakened.

## Notes

The broad snapshot alone also reaches the independent layout-coverage guard after the source-kind mutation. The guard-specific assertion therefore prevents that separate refusal from masking a weakened embedded-envelope condition. The mutation proof altered no tracked production file or persistent registry evidence.
