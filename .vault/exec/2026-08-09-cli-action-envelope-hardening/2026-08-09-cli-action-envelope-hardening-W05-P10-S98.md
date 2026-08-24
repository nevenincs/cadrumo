---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:0d8d125c0ff1f75c070ab29b76c3c1f3396309c615705b471b870f46a2b15656'
step_id: 'S98'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Classify all application-registry refusals with canonical terminal outcomes

## Scope

- `src/cadrumo/application/registry/_errors.py`
- `src/cadrumo/application/registry/_diff.py`
- `src/cadrumo/application/registry/__init__.py`
- `src/cadrumo/application/registry/_conformance.py`
- `src/cadrumo/application/registry/_corpus.py`
- `src/cadrumo/application/registry/_corpus_manual_helpers.py`
- `src/cadrumo/application/registry/tests`

## Description

- Add standard terminal transport and one registry helper delegating to canonical no-action authority.
- Preserve distinct ambiguous and unavailable revision-selection causes through the application boundary.
- Type filed-state input, conformance, corpus, and manual-rule refusal families with explicit outcomes.
- Remove positional English from filed-state and conformance errors.
- Add exact twelve-carrier fact-expression totality and full runtime contracts.

## Outcome

All twelve application-registry carriers are typed: two distinct diff selections, two filed-state inputs, two conformance omissions, five corpus carriers, and one manual-rule input. Operator selections resolve to `OPERATOR_DECISION`; missing/inconsistent authoritative structure resolves to `SAFETY`. Domain causes remain chained where present.

`RegistryApplicationError` uses the standard mixin, all producers delegate through `registry_terminal_refusal`, and `_errors.py` owns the sole canonical helper call. Direct verdict/evidence construction and the four authored messages are absent. The focused suite passes 74 tests; Ruff and diff checks pass. Independent review found no residue and confirmed no registry data was touched.
