---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-06-30'
modified: '2026-06-30'
related:
  - "[[2026-06-30-agent-harness-plan]]"
---

# `agent-harness` `W01.P02` summary

Phase P02 bound the manifest command to the conformance gates and the
documentation reference. All four steps closed; landed in commit `25534b6aa`.

- Created: `src/aeat/entrypoints/cli/tests/test_app_contract.py`
- Created: `docs/api/aeat.application.operator_surface._manifest.rst`
- Modified: `src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py`
- Modified: `docs/api/aeat.application.operator_surface.rst`

## Description

- S06: Enrolled `contract` as a group-callback emit key in the JSON-schema
  conformance gate (the command registers no leaf subcommand, so the leaf walker
  cannot reach it). The gate passes (94 tests).
- S07: Added `test_app_contract.py` (7 tests): the manifest envelope is a success
  document; both pinned roots present; lifecycle is calculate/verify/file; every
  command family is covered with a valid mutability matching the authoritative
  contract; the command-schema index includes the command's own key; and the
  payload-discovery loader catches all three payload-module naming shapes.
- S08: Regenerated the `_manifest` API reference stub and its parent toctree via
  the apidocs scaffold CLI (never hand-authored).
- S09: Confirmed the documented-command conformance gate (49 tests) and the
  docstring core-struct-links gate stay green with the new command; added the
  required `:class:` cross-link for the `OutputSchema` import.

## Outcome

JSON-schema conformance (94), manifest behaviour (7), documented-command
conformance (49), and docstring core-struct-links (3) all pass. Ruff check and
format are clean on every touched file.

## Notes

A loader-completeness defect was found and fixed during S07: the first loader
matched only the `_payloads` suffix and missed `_payloads_modelo_reconcile` and
`_modelo_payloads_m036` (7 commands); the loader now matches the `payload`
substring and a regression test pins all three naming shapes.

Two pre-existing failures in `test_root_help_shape.py` (active-profile id
redaction, `operator` vs `<profile-id>`) are unrelated to this work: the change
touches no profile, redaction, or bare-invocation code (the `__init__.py` diff is
two additive lazy-registration lines), no peer WIP exists in those files, and the
CLI-surface subset gate accommodates the new command. Recorded as a pre-existing
peer-surface red per the full-tree-gate owner-distinction discipline.
