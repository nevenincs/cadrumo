---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:af2867b550f28ad3e1d53732d4bc723a1dcbf12883910efdbe131adc5a858455'
step_id: 'S84'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Move and rename the core i18n default-language test to its owner

## Scope

- `src/cadrumo/tests/test_cli.py`
- `src/cadrumo/core/i18n/tests`

## Description

- Remove the misplaced central default-language behavior module instead of moving a duplicate.
- Extend the existing core i18n owner test to prove the public facade import and export contract.
- Retain value, renderer-authority identity, and real fallback-routing coverage at the narrowest owner.

## Outcome

The default output language now has one canonical behavior surface under core i18n. The owner test proves public importability, facade `__all__`, the Spanish value, identity with renderer authority, and fallback behavior; the vague central `test_cli.py` catch-all no longer exists.

## Notes

The exact three owner tests pass, owner collection is non-vacuous, and Ruff, topology, marker validity, diff integrity, and independent review passed. The wider owner module retains one unrelated locale-catalogue failure, and the tree-wide architecture-marker gate reports unrelated peer marker mismatches; neither was suppressed or attributed to this ownership move. Semantic RAG was unavailable, so exact source and Vault fallback discovery was used.
