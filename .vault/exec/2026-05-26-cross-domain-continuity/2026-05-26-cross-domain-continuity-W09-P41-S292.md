---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-01'
modified: '2026-07-01'
step_id: 'S292'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R8-MARC-A surface legal_refs and source_refs in verify and revision CLI outputs

## Scope

- `Marc round-8 round-8 confirmed observations carry provenance in the persisted CalculationRevision but no CLI surface emits them (verification-report view revision casillas formulas describe all lack the columns)`
- `add --json flag or sibling subcommand that projects typed observations including legal_refs source_refs formula_id to operator output`
- `src/aeat/entrypoints/cli/_modelo.py`

## Description

- Ground S292 with RAG and a read-only CLI provenance-surface audit.
- Verify that `work calculate`, `work revision`, `work revisions`, and `work observations` JSON payloads already expose typed calculation observations with `formula_id`, `legal_refs`, and `source_refs`.
- Verify that the dedicated `work observations` text surface also emits `formula_id`, `legal_refs`, `source_refs`, and operand trace columns.
- Verify that verification-report JSON/text surfaces expose finding-level `legal_refs` and `source_refs`.
- Correct one existing verification-report test fixture that used a legal-ref-shaped token as a `source_ref`, so the evidence test validates the current source-ref contract.
- Run focused integration evidence tests and ruff for the touched test file.

## Outcome

- Closed S292 as already satisfied by the dedicated sibling command `aeat app modelo work observations` and the existing revision JSON payloads.
- No CLI production code change was needed.
- Added only a test-fixture hygiene correction in `src/aeat/entrypoints/cli/tests/test_modelo_verification_report_view.py`, replacing an invalid `source_refs` token with a valid source id while preserving the assertion that persisted source refs surface in text and JSON.
- Validation passed with `34` focused CLI provenance integration tests.

## Notes

Default text summaries for `work calculate`, `work revision`, and `work revisions` remain intentionally compact and do not duplicate every observation provenance field. Operators who need the full typed observation provenance use `work observations` or JSON output from the revision commands.
