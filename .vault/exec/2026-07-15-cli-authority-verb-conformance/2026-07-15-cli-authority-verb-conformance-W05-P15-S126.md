---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S126'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Define secret-free schemas for passphrase change, recovery status, create, rotate, verify, and flat recover

## Scope

- `src/cadrumo/entrypoints/cli/_config_payloads.py`

## Description

- Confirm the six accepted custody result schemas are registered in the named payload module.
- Read each schema field set and confirm no field carries passphrase, key material, or recovery words.
- Probe the whole registry for sensitive field names and classify every match.

## Outcome

All six accepted schemas are registered and secret-free: `config.passphrase.change`, `config.recovery.status`, `config.recovery.create`, `config.recovery.rotate`, `config.recovery.verify`, and the flat `config.recover`. Each declares only non-secret fields: a recovery path, a secure-store directory, a non-secret recovery fingerprint, and booleans.

A registry-wide probe found eleven fields matching a naive sensitive-substring pattern; every one proved to be metadata describing a secret rather than a secret value, such as a boolean `has_secret`, a secret-store directory path, an AEAT period code, and LLM token counts. The distinction matters: a substring rule would have red-lined all eleven and invited weakening the check.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
