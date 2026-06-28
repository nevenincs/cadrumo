---
tags:
  - '#exec'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S02'
related:
  - "[[2026-06-15-service-capabilities-plan]]"
---




# Add a capabilities `[[sections]]` with boolean fields to the user_profile schema TOML

## Scope

- `add a roundtrip test`
- `src/aeat/_data/registry/aeat/user_profile/schema.toml`

## Description

- Add a `capabilities` `[[sections]]` (3 boolean fields) to the user_profile schema TOML; add enum<->schema parity tests.

## Outcome

Capabilities persist as encrypted profile facts via the existing schema machinery; 4 parity tests green.

## Notes

None.

