---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:bb8073052c81d9baf5f9033cec30360ba7a9b8a03c56a677a490b67fab3004e7'
step_id: 'S12'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Re-adjudicate Modelo 303 deadlines, remove every non-owner copy, preserve the 2024 cutover, and materialise every supported monthly and quarterly row

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/303/`

## Description

- Search the code and decision corpora with Vaultspec RAG before editing.
- Reuse `select_revision`, its shared period-token matcher, and the registry ownership validator as the only ownership authorities.
- Remove every already-authored Modelo 303 deadline copy whose containing revision is not the canonical owner.
- Preserve the period-sensitive 2024 boundary: `1T`, `2T`, `01`, and `06` remain early; `3T`, `4T`, and `12` remain late.
- Keep the plan Step open because the shared supported-year catalogue required to prove complete materialisation is not available yet.

## Outcome

The owner-normalisation portion is complete. Existing grounded rows now have exactly one containing revision, selected solely by filing year and canonical period token. No new selector, cadence map, horizon, deadline resolver, or inferred row was introduced.

The Step is deliberately incomplete. Removing future-year copies from revision `2023` exposes its empty deadline family, and the independently known Modelo 322 gap also prevents full-registry construction. The exact-four 2025 engine regression is therefore not currently reachable through the default validated authority.

## Notes

- Focused canonical-ownership unit tests passed: 4 tests.
- The engine regression fails closed during registry construction, before scheduling, because Modelo 303 revision `2023` and Modelo 322 revision `2008-2022` still lack deadline-family completion.
- Complete periodic materialisation remains deferred to the canonical temporal-coverage catalogue owned by `W02.P05.S24`; no filing-year horizon was inferred locally.
