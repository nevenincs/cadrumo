---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:07056731ea09303de5c985b6d5347d3a6301c602f30d44cc494cddbe820af6e1'
step_id: 'S263'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# Remove the five newly introduced em dashes from environment-override prose and prove the documentation dash ratchet without widening its baseline

## Scope

- `docs/reference/environment-overrides.md and dev/docs/emdash_baseline.json`

## Description

Replace the five newly introduced em dashes with punctuation and sentence structures that preserve the generated environment-reference meaning. Keep the existing ratchet baseline unchanged, then run the exact documentation em-dash gate.

## Outcome

The environment-override reference contains none of the five newly introduced em dashes. The exact documentation ratchet test passes with one test passed, and `dev/docs/emdash_baseline.json` remains untouched.

## Notes

The five characters occurred across four lines because the wallet diagnostic row contained two. The repair changes prose only and does not widen or regenerate the baseline.
