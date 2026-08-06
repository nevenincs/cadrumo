---
tags:
  - '#exec'
  - '#post-release-distribution'
date: '2026-07-19'
modified: '2026-07-19'
body_hash: 'sha256:50d08aaa8cbefd45441db943d26b61abc509b5c9b5edee2e608d8f9f6f2fb646'
step_id: 'S09'
related:
  - "[[2026-07-17-post-release-distribution-plan]]"
---

# DONE via local subscription-authed Claude Code 2.1.214 per operator ruling (no CI API key), evidence var/distribution-install-readiness/s27-plugin-68a8433c/run-20260718T164855Z/plugin-evidence.json against cohort 68a8433c at commit 02b3656095, marketplace install with byte-verified three-wheel cohort, real client session connected and called cadrumo_harness_load (status passed), protocol oracle on the same install returned DP200014:00562 = 23000.00 via modelo-200-cuota-integra with the sole permitted plazo-vencido notice

## Scope

- `.github/workflows/packaging-claude.yml`

## Description

- Install the cohort plugin in a real Claude Code client and execute the real tax-work tool call, per the operator ruling accepting local subscription-authed evidence in place of a CI API key.

## Outcome

Done via locally subscription-authed Claude Code `2.1.214` (operator ruling: no CI API key). Evidence at `var/distribution-install-readiness/s27-plugin-68a8433c/run-20260718T164855Z/plugin-evidence.json` against cohort `68a8433c` at commit `02b3656095` (in HEAD): marketplace install with a byte-verified three-wheel cohort, a real client session that connected and called `cadrumo_harness_load` (status passed), and a protocol oracle on the same install returning `DP200014:00562 = 23000.00` via `modelo-200-cuota-integra` with the sole permitted plazo-vencido notice. Closed against retained real-client evidence.

## Notes

Retroactive execution record; step already checked. The local-evidence substitution is an explicit operator ruling, not a bypassed gate. Vault-only bookkeeping.
