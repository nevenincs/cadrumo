---
tags:
  - '#exec'
  - '#issue-620-external-pdf-signal'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:ea5214a5715cd180dfcac1eff7b292560351292562b52cc9df59e55700911167'
step_id: 'S11'
related:
  - "[[2026-08-23-issue-620-external-pdf-signal-plan]]"
---




# Define the three-axis authority-adjudication contract and offline official-source evidence schema

## Scope

- `src/cadrumo/tests/fixtures/external_layout_candidates/__init__.py`
- `src/cadrumo/tests/fixtures/external_layout_candidates/tests/test_candidate_contract.py`

## Description

- Define independent typed verdicts for third-party artifact authenticity,
  verified official-base derivation, and registry applicability.
- Require official authority, document identity, HTTPS URL, SHA-256 digest,
  one-based page mapping, comparison method, and reproducible summary.
- Bind each candidate to the opposite pair member by digest and distinguish
  exact from measured-similarity 96-dpi render comparisons.
- Enforce authored-revision identifiers only for current or historical
  authored applicability verdicts.
- Preserve an exclusive migration boundary so legacy sidecars remain readable
  until S12 replaces `authority_status` with `authority_adjudication`.
- Add synthetic contract mutations that exercise the new schema without
  editing S12-owned sidecars.

## Outcome

- The candidate loader now exposes a strict, frozen, offline three-axis
  adjudication contract without treating third-party bytes as AEAT or BOE
  publication artifacts.
- Ruff passed for both S11 Python files.
- The focused candidate-contract unit module passed: 33 tests.

## Notes

- The first focused run found only a sorted-export lint issue and strict Python
  tuple construction in synthetic payloads; both were corrected before the
  clean verification run.
- No candidate JSON sidecar was edited; S12 owns the ten data migrations.
