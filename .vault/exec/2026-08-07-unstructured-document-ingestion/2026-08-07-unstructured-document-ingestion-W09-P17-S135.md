---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:31622104b4270cd2c8b3e54b37d95e8e70987ff115082495d6a7c3b56bf32f91'
step_id: 'S135'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Make the structural status-blindness sweep prove it exercised its own assertion, since the counter increments before the skip so the count assertion equals the loop bounds unconditionally and cannot fail, while the inner assertion runs only on shapes matching a non-fallthrough rule and nothing requires any shape to. Proven vacuous by emptying the rule table so every shape fell through, after which the gate still passed. Latent rather than live today because forty-seven of the hundred swept shapes reach a real rule, but it sits on the test described as the stronger structural guarantee and a future narrowing of the table would degrade it silently into an assertion-free loop. Count the shapes that actually exercise the assertion and gate on that, dropping the tautological line rather than replacing it with another

## Scope

- `src/cadrumo/application/ledger`

## Description

## Outcome

## Verification

## Notes
