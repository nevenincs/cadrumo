---
tags:
  - '#exec'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S10'
related:
  - "[[2026-06-15-service-capabilities-plan]]"
---




# Tests + locales + how-to onboarding doc across capabilities, probes, doctor, provisioning

## Scope

- `src/aeat tests`
- `src/aeat/locales`
- `docs/how-to`

## Description

- Add `src/aeat/application/tests/test_provisioning.py`: real-behavior tests for the three dependency probes — unreachable Ollama (unavailable + remediation, never raises), Playwright cache absent/present/missing-root, subprocess providers return typed statuses without raising.
- Add a doctor issue-path test to `test_config_capabilities.py`: `aeat config check` exits 2 and surfaces an `llm_vision is on` issue when the capability is opted in but Ollama is unreachable (the green path was covered by S08).
- Confirm the capability/doctor/provisioning locale keys are complete and parity/honesty green (capability CLI keys landed in S06–S08; wizard capability keys landed in S11).
- Deliver the onboarding how-to doc under S14 (`docs/how-to/onboarding.md`), cross-referenced here as the doc portion of this step.

## Outcome

The probe surface and the doctor issue path now carry real-behavior coverage (10 tests, no mocks); locale catalogues are parity- and honesty-clean. The how-to onboarding doc is delivered and conformance-checked under S14. Committed as `c9051fc88` (tests) and `6bf45d03e` (doc).

## Notes

The how-to doc deliverable is shared with S14; it is authored and committed there to keep the docs change atomic. This step's own commit covers the tests + the locale-completeness verification.
