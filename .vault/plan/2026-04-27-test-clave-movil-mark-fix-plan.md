---
tags:
  - '#plan'
  - '#test-clave-movil-mark-fix'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - '[[2026-04-27-test-clave-movil-mark-fix-research]]'
  - '[[2026-04-27-test-clave-movil-mark-fix-adr]]'
---

# `test-clave-movil-mark-fix` implementation plan

This plan implements the corrected decision: keep the Cl@ve Movil test module protocol-level, document that it does not prove live AEAT authentication, and remove automatic provider-side form submission.

## Proposed Changes

Update `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_clave_movil.py` so the whole module is marked `unit` and `domain_aeat_remote`.

Document at the top of the file that these tests use browser-session stand-ins and do not prove real AEAT authentication or operator Cl@ve approval.

Remove provider code that auto-submits AEAT's representation dispatcher after Cl@ve approval.

Confirm that the searched workaround surfaces contain no remaining `--ignore=src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_clave_movil.py` references.

## Tasks

- Update the module marker and docstring.
- Delete the representation dispatcher auto-submit helper and refuse that state explicitly.
- Search the repository workaround surfaces for stale ignore references.
- Verify default unit selection and the focused Cl@ve provider tests.
- Run lint, typecheck, unit tests, coverage, hooks, and code review.

## Parallelization

This is a narrow source change plus vault records. Parallel execution is useful only for independent searches and verification commands.

## Verification

Success means the module is plainly protocol-level, default unit selection can run it without touching AEAT, no automatic representation form submit remains in `_clave_movil.py`, and no AEAT submission surface is reintroduced.
