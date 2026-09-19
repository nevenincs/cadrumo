---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:e2499220cd49029c3a90d5147a8ca145794a1ed32eae198da00b4b41304a3824'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# `cli-action-envelope-hardening` audit: `S94 final producer-scope independent review`

## Scope

Independent current-tree review of `W05.P10.S94`, limited to the LLM package's producer-owned optional-extra wrappers, continuations, terminal verdict carriers, tests, and public facades. It separately checks the shared S114 consumer handoff without attributing its terminal emission to the LLM producer owner. The review is read-only apart from this audit record; S94 remains open for final ledger reconciliation.

## Findings

### s94-typed-producer-fixed-point | low | all current LLM refusal producers use one fact-only terminal-verdict authority

The current `src/cadrumo/llm` tree contains one closed `LLMPreconditionCondition` taxonomy and one `llm_no_recovery_verdict` constructor. Every migrated LLM configuration, consent, validation, extraction, mapping, and provider refusal passes the typed verdict through `LLMPreconditionErrorMixin`; the producer package has no action recovery renderer or free-form command bridge. Exact source scans found no direct CLI projection or `entrypoints.cli` import from production LLM code. The original S94 direct private CLI reach is absent. The producer-facing nested `LLMRequest` validation error retains its exact terminal verdict in Pydantic context.

### s94-installed-product-proofs | low | every current guarded LLM surface preserves registered machine identity in a genuine core-only install

The source-derived inventory identifies the complete exported LLM-extra guard set and refuses a new uncovered guard. The inventory proof passed separately with no workers. The complete LLM-extra core-only wheel cohort then passed separately in 188.12 seconds, and the independent Anthropic core-only wheel cohort passed separately in 190.50 seconds. Both use an installed product outside the checkout and real optional-probe absence, not import interception, fakes, patches, or test-only alternate implementations.

### s94-quality-and-import-boundary | low | the complete ordinary unit lane and owned structural lanes are clean

`uv run pytest -q -m unit src/cadrumo/llm/tests` passed 460 tests. `uv run ruff check src/cadrumo/llm` and `uv run ty check src/cadrumo/llm` both passed. The current repository-wide import-hygiene scan found zero production cross-package private imports, zero shims, zero shipped reaches into `dev`, and no S94 production import violation. The scan contains a test-only `cadrumo.llm._providers.base` reach, which is outside the producer runtime surface and unrelated to the retired CLI bridge.

### s114-terminal-consumer-handoff | low | S114's current terminal consumer now reads the nested producer, under its separate final review

The initial S94 review correctly isolated an S114 terminal traversal defect from the LLM producer scope. Current S114 routing instead sends the terminal path through the shared boundary discriminator. The independent terminal probe now preserves the nested registered LLM refusal and the exact no-recovery action, and the current S114 focused callback and terminal lanes pass. This confirms the consumer has caught up; it does not widen S94's producer-owned scope or close either plan row.

## Recommendations

Accept this audit as a PASS for S94's producer-owned migration and installed-product evidence only. Keep S94 open for the separately owned rehoming-ledger reconciliation and final plan lifecycle transition. Keep S114 under its own independent final review and ledger reconciliation; do not use this producer audit alone as whole-chain closure. The unrelated live Anthropic test requires explicit `CADRUMO_LIVE_TESTS_ENABLED=1` authority and was not used as S94 proof.
