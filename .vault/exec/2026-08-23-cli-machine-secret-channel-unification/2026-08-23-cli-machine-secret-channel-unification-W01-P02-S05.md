---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:b2f82282e8574c31ab6800a26e6e7ff1ddf22f1203cb1fa98925b0a3b97ab83d'
step_id: 'S05'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

# Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and prove exact inventory membership, single identical flag declarations across help, Click, metadata, and schema, safe field types without values, and no outside adopters

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_machine_secret_metadata.py`

## Description

- Ground the closed inventory, live command tree, safe metadata projection, and governing decision through semantic code and ADR discovery, exact-symbol search, and current-HEAD inspection.
- Add one cross-surface conformance module for inventory membership, canonical option order and semantics where currently declared, value-free payload variants, restore conditions, and outsider exclusion.
- Make canonical `MachineSecretPayload` inheritance an enforced registration precondition while retaining the inventory module's import-light boundary.
- Prove noncanonical models refuse before registration and fresh-process metadata import does not load secure-input code.
- Preserve generated registration JSON and CLI-tree regeneration as the explicit later S15 obligation.

## Outcome

The five-command inventory now has a focused conformance gate over live help, materialized Click parameters, canonical command specifications, safe registration metadata, and verb-input payload schemas. Machine-secret payload registration can no longer accept a shape-compatible plain Pydantic model: every accepted model must derive from the shared strict frozen base. Conditional restore metadata exposes only public artifact presence and field/type structure; no value, default, example, or secret representation is projected.

## Notes

- Focused unit and integration tests pass: five inventory/registration tests and four cross-surface metadata tests.
- Scoped Ruff, `ty`, and import-smoke gates pass. Typer emits thirty-seven existing deprecation warnings while materializing the live command tree.
- Generated registration JSON still reflects the pre-migration missing descriptor flags for profile creation and certificate-secret mutation. This Step deliberately does not regenerate it or narrow S15's exact generated-parity obligation.
- Models owned by later migration Steps may leave declared registry slots absent until those handlers adopt the canonical contract; every registration that occurs is already inheritance-gated, and final exact-set closure remains required.
- The S04 execution record arrived in a later Vault refresh commit than its production projection. This attribution anomaly was accounted for as existing history and was not rewritten.
- Concurrent S06 closure reached the shared serialized plan before this commit. The mechanically inseparable S05 and S06 checkbox/hash update lands here by coordinator approval; no S06 code or execution record is attributed to S05.
- The formal-review audit scaffold remains uncommitted for the required post-landing reviewer because all collaboration slots were occupied during this Step.
