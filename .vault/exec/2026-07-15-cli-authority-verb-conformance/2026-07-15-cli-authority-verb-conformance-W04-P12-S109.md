---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S109'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Replace obsolete bootstrap exemptions with the exact accepted passphrase and recovery paths

## Scope

- `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`

## Description

The bootstrap-exempt inventory had to drop obsolete passphrase/recovery entry spellings
and carry exactly the accepted paths: `config passphrase change`, `config recover`, and
`config recovery`.

## Outcome

`BOOTSTRAP_EXEMPT_VERB_PATHS` in `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py:36-87`
lists, among the custody entries, exactly `"config reset"`, `"config passphrase change"`
(line 73), `"config recover"` (line 74), and `"config recovery"` (line 75) — the exact
three accepted passphrase/recovery paths named in the step. No obsolete spelling
(`config rekey`, `config show-recovery`, `config verify-recovery`) appears anywhere in the
tuple. Matching in `is_bootstrap_exempt` (lines 90-119) is prefix-based, so `"config
recovery"` covers all four recovery leaves (`status`/`create`/`rotate`/`verify`) and
`"config passphrase change"` covers the one passphrase leaf.

## Notes

Verified by direct file read of `_bootstrap_exempt.py`; the entries match the coordinator's
brief verbatim. Cited the coordinator's gate results rather than re-running; this file has
no dedicated behavioural test beyond the policy-coverage gate exercised in S114.
