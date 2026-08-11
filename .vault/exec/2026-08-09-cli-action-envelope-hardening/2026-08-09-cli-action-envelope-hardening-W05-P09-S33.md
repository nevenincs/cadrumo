---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:739b0efd658bd084db45afe0b71de36ad0f16bf9ea52e42117bcecc298a72d05'
step_id: 'S33'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# W05.P09.S33 - Replace provisioning optional-extra recovery prose with typed failed-condition facts and explicit no-recovery outcomes including the local-model stored-without-extra row and hand the changed dependency projection to S89 without retained remediation compatibility

## Scope

`src/cadrumo/application/provisioning.py`; directly owned provisioning application tests; retirement of stale provisioning rows from `dev/quality/cli_action_census_dispositions.toml`.

## Description

- The provisioning application boundary supplies locale-neutral machine facts and closed typed precondition verdicts, including explicit operator-decision no-recovery outcomes for rejected branches.
- The two local-model predicates remain distinct: local-extra-present/model-absent and stored-model-present/local-extra-absent have separate condition identities and evidence sets.
- A historical census at `47159712ba8d8505acc91c7bfea70e4754d5e9aa` found zero current provisioning candidates. Its initial ledger still carried 42 stale provisioning candidate dispositions, all for presentation/remediation constructs removed by this step.
- The guarded canonical census parser/renderer reconciliation accepted only that source revision and source SHA `ab7b737ce0ca54040d2ccaab54c8bd183bfd3a6def509f7d6085983549eaac79`; it refused nonzero current candidates, any count other than 42, and every off-path change.
- No S65 ownership handoff is required: S33 owns the retired provisioning source candidates; S65's later ledger scope concerns its own ancillary-core candidates.

## Outcome

The canonical ledger transitioned from SHA-256 `5d71d32187c8e1adb3f4278b92fbbc3d025d00cb94eb20d2509e7e8431795bff` to `b0c319e0613e607f8dbc09eb912649d7181ddeeedf8448213c36181c8d76730e` by removing exactly 42 provisioning rows, with zero additions, replacements, or off-path changes. Concurrent commit `a22319205e` records that exact postimage.

Current fixed-point validation at `HEAD` reports zero provisioning census candidates and zero provisioning disposition rows; canonical disposition validation accepts that empty pair. The full census validator is externally red (629 diagnostics) but has zero diagnostics for `src/cadrumo/application/provisioning.py`.

This execution remains open for independent re-review. The plan checkbox was not changed.

## Notes

- Direct recovery-rehoming validation is externally red on three fingerprint-multiset rows in the S38 ledger-evidence and S94 LLM clusters; its no-write migration replay is red with `E_REHOMING_MIGRATION_CHECK_CONTENT`.
- The exact live-source-join pytest lane was started separately to avoid conflating an execution-window timeout with a test result; its final state is recorded in the handoff evidence, not represented as a pass here.
- S89 remains the owner of the coordinated CLI schema and rendering consumer cutover.
