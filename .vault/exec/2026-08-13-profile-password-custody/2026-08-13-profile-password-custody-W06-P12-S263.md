---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:0779efe1625e8436c3b6e4175f881c9b167631506d3ff94a73f80d8b355404dd'
step_id: 'S263'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# Remove the five newly introduced em dashes from environment-override prose and prove the documentation dash ratchet without widening its baseline

## Scope

- `docs/reference/environment-overrides.md and dev/docs/emdash_baseline.json`

## Description

Replace the five newly introduced em dashes in the generator header and live settings-field descriptions, regenerate the environment reference from those source owners, and keep the existing ratchet baseline unchanged. Run generation freshness, the exact documentation em-dash gate, the generated-reference contract suite, and scoped Ruff.

## Outcome

The source-owned environment prose and regenerated reference contain none of the five newly introduced em dashes. Generation followed by `--check` is fresh. The exact documentation ratchet passes with one test passed, the generated environment-reference suite passes with four tests passed, and scoped Ruff passes. `dev/docs/emdash_baseline.json` remains untouched.

## Notes

The initial draft edited the generated page directly and introduced an ungrammatical clause. Formal review rejected it at HIGH and MEDIUM. The corrected implementation changes `dev/docs/env_reference.py` and the relevant `Settings` descriptions, regenerates the page, and preserves the source meaning. The five characters occurred across four generated lines because the wallet diagnostic row contained two.
