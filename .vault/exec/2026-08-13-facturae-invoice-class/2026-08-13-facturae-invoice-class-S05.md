---
tags:
  - '#exec'
  - '#facturae-invoice-class'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:882d4c451cb1ed965d5e6e88597dccfeb85d3e809a1bf6281c0caaeb3e541223'
step_id: 'S05'
related:
  - "[[2026-08-13-facturae-invoice-class-plan]]"
---




# Gate the whole path against the corpus fixtures that already carry OO and OR rather than synthetic XML, and prove the fallback still classifies a record declaring no code. Include the mutation proof that the declared code is what decides - a record whose corrective reference and declared class disagree must not silently take the inference's answer

## Scope

- `src/cadrumo/application/ledger/tests/`

## Description

- Confirm the committed OO corpus record through real encrypted evidence storage and the real catalogue.
- Confirm the committed OR corpus record as corrective with its corrected invoice reference.
- Remove the declared code and prove the corrective-reference fallback remains effective.
- Mutate the OR declaration to OO and prove the contradiction is surfaced and cannot silently mint the inference's answer.
- Mutate the committed anchors through CO and CR and prove the copy axis does not change the domain class.
- Drive OC and CC through real evidence storage and prove each raises the recapitulativa finding while preserving a discriminatory operator class.
- Remove the corrective reference under OR and CR and prove both reverse contradictions are reported.

## Outcome

- Ten real-behavior cases exhaust the six declared codes, the absent fallback, and both contradiction directions.
- The complete focused feature gate passed lint and forty-eight tests.

## Notes

- Semantic discovery remained temporarily unavailable; exact source discovery located the established real-storage test harness.
- The first mutation assertion expected the domain wrapper exception, while the candidate builder correctly raised Pydantic validation at its immediate boundary; the assertion now names that real exception and message.
- An independent review found the copy, recapitulativa, and reverse-contradiction branches supported only by inspection; S05 was reopened and the missing executable matrix was added before re-closing it.
- Focused verification does not establish repository-wide readiness.
