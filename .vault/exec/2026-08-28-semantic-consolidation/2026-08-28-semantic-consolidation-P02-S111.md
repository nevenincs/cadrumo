---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:2473e8cdc3a37130f968f17f165443e55ddf6ff0e4f2f92e490b87bf51b425cc'
step_id: 'S111'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Give the Spanish postcode format a domain-level home, since it is enforced only by the setup wizard and no other write path to address_postcode refuses a malformed value

## Scope

- `src/cadrumo/core/setup_answers.py`

## Changes

- `A` `src/cadrumo/core/spanish_postcode.py`
- `M` `src/cadrumo/core/setup_answers.py`
- `M` `src/cadrumo/application/wizard/widgets.py`
- `M` `src/cadrumo/application/wizard/tests/test_setup_answer_field_parity.py`
- `verify:` `pytest src/cadrumo/application/wizard/tests/test_setup_answer_field_parity.py -n 0 -m ""` -> `pass`

## Notes

The rule lived at one entrance only: the wizard checked it, and the profile
field it writes into carried no constraint, so any other route persisted a
malformed value silently. Probed at the model rather than restated: undeclared
and 28001 accept, 99999 and 1001 refuse.

The field-parity test filled every free-text answer with the token `sample`,
which a postcode question no longer accepts. Its helper now reads the postcode
question ids from the widget module rather than restating them, so a second
postcode question cannot pass the test while the profile refuses it.
