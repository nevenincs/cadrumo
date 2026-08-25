---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:40ca4f420b959d5b7de5a8e5f879e93eaf0a24646cf70309b0a7cb21404f22e3'
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

The current two discovery probes are stable at 464 capabilities, with equal capability sets and digest `sha256:0be7d9fae88abef85b83af8eddd87a1cc4a030c8e6e751587c6f6ae42975cf64`. Neither canonical assignment comparison completed: both refused because the census locator for `inventory.stock-valuation`, `src/cadrumo/entrypoints/cli/_app_ledger_command_specs.py:4866`, no longer exists after the concurrent CLI command-spec relocation.

`S116` remains unchecked. Its required zero-unclassified-or-unactioned and stable-assignment proof is not available. No source candidate was added, removed, connected, or reclassified; no expiration was waived; and no census, plan, or index authority was mutated.

## Notes

The earlier related-party locator drift was repaired and is no longer the refusal. The 15 static census rows retain their authored dispositions; all seven dated deferrals are current through 2026-12-31. Those facts cannot stand in for the refused canonical assignment set. A separately owned mechanical locator-maintenance step must either prove the relocated live inventory capability and update its locator or retire the stale census candidate from evidence; it may not change the candidate disposition merely to make comparison pass.
