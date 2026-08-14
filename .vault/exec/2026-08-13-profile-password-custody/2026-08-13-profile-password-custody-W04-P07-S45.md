---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:d99f8f36c6aa2ce8ccd925dd3c0208cb59ac79b8104329b4c7857f35ffc0c2e7'
step_id: 'S45'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---




# Have Terra XHigh make the module coverage gate judge a property rather than static reachability, since one import from any surviving test currently keeps every module in a package reported as covered, which is how fifteen deleted test modules left twenty-two live modules unproven without the gate noticing

## Scope

- `src/cadrumo/tests/test_every_module_has_test_coverage.py`

## Description


## Outcome

## Notes

