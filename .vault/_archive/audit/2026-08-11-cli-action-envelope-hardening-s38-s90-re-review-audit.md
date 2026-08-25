---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:0084b32a10ee616ea75a8a5b0747ae0088f457ccd42b91f815aa270243697810'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-adr]]"
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# `cli-action-envelope-hardening` audit: `S38 and S90 typed ledger refusal re-review`

## Scope

Independent re-review of the completed S38 and S90 ledger refusal changes against the accepted action-envelope ADR and plan. The review covered typed condition consumption, CLI ownership, locale registration, the declared ledger consumer surface, focused real-behavior tests, and fixed-point/census checks.

## Findings

### s38-canonical-condition-redeclarations | high | S38 regression tests redeclare provisioning condition identities

The S38 tests added raw condition-id strings instead of importing the canonical provisioning condition enum: `test_batch_ingest_runner.py` asserts `provisioning.load_headroom.measurable` and `provisioning.runtime.reachable`, and `test_llm_vision_evidence.py` asserts `provisioning.runtime.reachable`. The production hand-off now carries the typed verdict correctly, but these literal assertions permit a canonical-condition rename to drift without an enum-bound test failure.

### s38-unregistered-reader-operation-key | high | S38 emits a reader-operation failure that is absent from every supported locale catalog

`_llm_classification.py` emits `ledger.evidence.reader.operation_failed` through `LLMClassifierError`, while the locale scaffold check reports that key missing in `ca`, `en`, `es`, and `hu`. This leaves an S38 failure path without the locale-complete renderer contract required by the envelope.

### s90-residual-ledger-command-prose | high | The declared S90 CLI surface still publishes direct command text

The broad ledger CLI surface retains raw action commands, including recovery/help text in `_ledger.py`, `_ledger_lifecycle_cli.py`, `_ledger_counterparty_cli.py`, and `_ledger_evidence_cli.py`. These are locally authored command instructions rather than projections of a registered operator action, so the visible next step can drift from the canonical action schema.

### s90-orphaned-llm-failure-locale-leaf | medium | The deleted S90 renderer leaves an obsolete locale leaf in every catalog

After the direct `LLMClassifierError` renderer was removed, `cli.ledger.classify.llm_failed` remains as an extra scaffold key in `ca`, `en`, `es`, and `hu`. The stale leaf preserves a second, unowned representation of an action/error surface and prevents a clean locale-contract check.

## Recommendations

Replace the S38 string assertions with `ProvisioningPreconditionCondition` members and register the reader-operation error through the canonical locale/catalog workflow before re-running the all-locale error-boundary suite.

Finish the S90 ledger-surface migration by removing direct command prose from all declared consumers, deriving every actionable continuation from `OperatorAction` schema data, and reconciling the orphaned `cli.ledger.classify.llm_failed` leaf through the locale tooling. Re-run the fixed-point action census and locale scaffold check after the producer/consumer inventory is empty.
