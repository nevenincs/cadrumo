---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:a37f50289837a71b648ab338a48e5d0ef82922fb63514efce96afe7a71e3edfa'
step_id: 'S133'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Declare the apoderamiento and review-package note bounds once each and adopt them at their six sites, retiring the review-package payload module from the outstanding list

## Scope

- `src/cadrumo/application/auth/apoderado_text.py`
- `src/cadrumo/application/modelo/review_package_text.py`
- `src/cadrumo/entrypoints/cli/`

## Changes

- `A` `src/cadrumo/application/auth/apoderado_text.py`
- `A` `src/cadrumo/application/modelo/review_package_text.py`
- `M` `src/cadrumo/application/auth/apoderado_service.py`
- `M` `src/cadrumo/application/modelo/review_package.py`
- `M` `src/cadrumo/application/modelo/_review_package_counter_sign.py`
- `M` `src/cadrumo/application/modelo/_review_package_feedback.py`
- `M` `src/cadrumo/entrypoints/cli/_config_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_review_package_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_cli_payload_constraint_authority.py`
- `verify:` each alias probed: accepts empty and its bound, refuses bound + 1
- `verify:` `pytest src/cadrumo/application/modelo/tests -k review_package -n 0 -m ""` -> `pass` (115)
- `verify:` `pytest ... test_cli_payload_constraint_authority.py -n 0 -m ""` -> `pass` (7)
- `verify:` `pytest src/cadrumo/application/auth/tests + 2 config CLI modules -n 0 -m ""` -> `374 pass, 1 unrelated fail`

## Notes

These four bounds -- 500, 2000, 2000, 4000 -- had been held back through several
rounds as needing an operator ruling, on the reading that four different numbers
for operator commentary was a divergence someone had to adjudicate. Reading them
together showed that was wrong. They pair up: each CLI payload restates the
application-layer bound it projects, and each pair AGREES. There was no
disagreement to rule on, only four bounds each written twice.

Identical is the dangerous case rather than the safe one. Nothing fails while
the two copies agree, so the day one side is adjusted the other keeps its own
answer and the operator is refused, or not, depending on which surface they
reach first.

Two aliases cover three concepts. The package author's notes and the
counter-signer's note share `ReviewPackageNote` because they are the same kind
of writing at the same point in the exchange; giving them separate names would
put 2000 in two places again under a disguise. `ReviewFeedbackNote` stays its own
alias at 4000 -- that is the one leg where the writer reviews someone else's
return, so the note carries reasoning rather than a label.

`_modelo_review_package_payloads.py` declared nothing further afterwards and the
gate's staleness arm said so on its own, which is the arm working as intended:
outstanding is now 5 modules.

The import insertion landed inside a parenthesised multi-line import on the
first pass, because the anchor matched on line prefix. Re-placed using each
module's last complete top-level import via its AST end line.
