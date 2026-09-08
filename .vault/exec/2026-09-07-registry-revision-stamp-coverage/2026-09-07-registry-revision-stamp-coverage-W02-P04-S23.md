---
tags:
  - '#exec'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:9575e01402c29a432b072b4b933b5d508348abacd6c1e0bde6fcb4f0ba1282fd'
step_id: 'S23'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-plan]]"
---

# Validate the review package stamp during package load, signature, counter-signature, and feedback flows

## Scope

- `src/cadrumo/application/modelo/review_package_signing.py`
- `src/cadrumo/application/modelo/review_package_counter_sign.py`
- `src/cadrumo/application/modelo/review_package_feedback.py`

## Changes

- `M` `src/cadrumo/application/modelo/review_package.py`
- `M` `src/cadrumo/application/modelo/tests/test_review_package_signing.py`
- `M` `src/cadrumo/application/modelo/tests/test_review_package_counter_sign.py`
- `M` `src/cadrumo/application/modelo/tests/test_review_package_feedback.py`
