---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:c1b108a3fc581b8abea01edb0d88d8f2f32d97aa2d1857569ada134e4af03ee0'
step_id: 'S116'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - '[[2026-08-25-source-casilla-integration-s116-connectivity-fixed-point-audit]]'
---
# rerun discovery until two consecutive runs produce no unclassified or unactioned candidate

## Scope

`W06.P20.S116` reruns the canonical source-connectivity discovery and assignment gate. This execution record records an open result only: it does not edit the census, runtime, source plan, or generated source index.

## Description

- Ran two separate fresh-process structural discovery probes through `dev.source_connectivity.cli generate`.
- Ran the canonical census assignment comparison in a fresh process after each discovery probe.
- Compared the two discovered capability-ID sets and their deterministic digest.
- Read the manifest solely to report the existing candidate/disposition and expiry posture after comparison refused.

## Outcome

The two discovery probes are stable at 476 capabilities, with equal capability sets and digest `sha256:b48f226826e09ff58aabe9b4eb2b3dae7af8544ef7f3995b62e4002cc8988e03`. Neither canonical assignment comparison completed: both refused the same locator drift for `rows.related-party-operation`, where `row_assembler:per_related_party_operation` now resolves at line 170 rather than the census's line 168.

`S116` remains unchecked. Its required zero-unclassified-or-unactioned and stable-assignment proof is not available. No source candidate was added, removed, connected, or reclassified; no expiration was waived; and no census, plan, or index authority was mutated.

## Notes

The 15 static census rows retain their authored dispositions; all seven dated deferrals are current through 2026-12-31. Those facts cannot stand in for the refused canonical assignment set. A separately owned mechanical locator-maintenance step must supply mutation-backed proof for the one live location before this step is rerun. The slow focused pytest invocation was interrupted after the two definitive canonical comparison failures and is not claimed as passing evidence.
