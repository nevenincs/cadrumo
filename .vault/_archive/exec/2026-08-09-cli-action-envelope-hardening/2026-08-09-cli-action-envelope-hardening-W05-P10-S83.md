---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:a44c82969f86113a07d8029df6cac644c9bd1dd40b0123a4f0fe21a1a528c9f2'
step_id: 'S83'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate authorization-domain recovery producers to typed conditions and canonical actions

## Scope

- `src/cadrumo/domain/auth`

## Description

- Migrate the three apoderamiento scope refusals to the registered unknown-scope key.
- Drop the prose parameter from the test that distinguished them by sentence.

## Outcome

- One refusal had written a CLI instruction into its message, telling the operator to pass the scope flag repeatedly instead. That is a rendered recovery, and it is gone.
- All three now render from the registered key. Each already carried a validation-rule fact naming which check failed, so the distinction the sentences drew survives as machine data.
- The parametrized test previously carried an expected-message column beside its expected context. The column was redundant with the validation-rule fact it asserted two lines later, so it was removed rather than updated.
- The package suite passes ten tests serially and is lint clean.

## Notes

- The test also asserts the refusal carries no suggestion attribute, which this migration leaves true.
- No carry-forward.
